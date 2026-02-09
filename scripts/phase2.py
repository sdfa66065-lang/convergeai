#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CONFLICT_START = "<<<<<<<"
CONFLICT_BASE = "|||||||"
CONFLICT_MID = "======="
CONFLICT_END = ">>>>>>>"

DEFAULT_CONFLICT_BUDGET_PER_FILE = 3
DEFAULT_COMPILE_ITERATIONS = 5
DEFAULT_TEST_ITERATIONS = 3
MAX_TOUCHED_FILES = 50
MAX_CHANGED_LINES = 2000


@dataclass
class ConflictHunk:
    hunk_id: str
    base: str
    ours: str
    theirs: str
    context_before: List[str]
    context_after: List[str]
    confidence: float


@dataclass
class ConflictFile:
    file_path: str
    hunks: List[ConflictHunk]


@dataclass
class StepResult:
    status: str
    reason: Optional[str] = None


def run_cmd(args: List[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(cwd),
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def run_git(repo_path: Path, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return run_cmd(["git", *args], cwd=repo_path, check=check)


def load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_conflicts(payload: Dict[str, object]) -> List[ConflictFile]:
    conflicts: List[ConflictFile] = []
    for conflict in payload.get("conflicts", []):
        hunks = []
        for hunk in conflict.get("hunks", []):
            context = hunk.get("context", {})
            hunks.append(
                ConflictHunk(
                    hunk_id=str(hunk["hunk_id"]),
                    base=str(hunk.get("base", "")),
                    ours=str(hunk.get("ours", "")),
                    theirs=str(hunk.get("theirs", "")),
                    context_before=list(context.get("before", [])),
                    context_after=list(context.get("after", [])),
                    confidence=float(hunk.get("confidence", 0.0)),
                )
            )
        conflicts.append(ConflictFile(file_path=str(conflict["file_path"]), hunks=hunks))
    return conflicts


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def resolve_hunk(hunk: ConflictHunk) -> Tuple[str, float, str]:
    ours_text = hunk.ours
    theirs_text = hunk.theirs
    if ours_text == theirs_text:
        return ours_text, 0.95, "identical"
    if normalize_whitespace(ours_text) == normalize_whitespace(theirs_text):
        return ours_text, 0.85, "whitespace"
    if hunk.confidence >= 0.8:
        return ours_text, hunk.confidence, "high-confidence-ours"
    return ours_text, max(0.4, hunk.confidence), "default-ours"


def apply_conflict_resolution(
    repo_path: Path,
    conflict_file: ConflictFile,
    step_dir: Path,
    per_file_budget: int,
) -> StepResult:
    file_path = repo_path / conflict_file.file_path
    if not file_path.exists():
        return StepResult("failed", f"Missing file {conflict_file.file_path}")

    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    new_lines: List[str] = []
    index = 0
    hunk_index = 0
    attempts = 0

    while index < len(lines):
        line = lines[index]
        if line.startswith(CONFLICT_START):
            if hunk_index >= len(conflict_file.hunks):
                return StepResult("failed", f"Hunk mismatch in {conflict_file.file_path}")
            hunk = conflict_file.hunks[hunk_index]
            hunk_index += 1
            attempts += 1
            if attempts > per_file_budget * len(conflict_file.hunks):
                return StepResult("failed", "conflict resolution budget exceeded")
            index += 1
            ours_lines: List[str] = []
            base_lines: List[str] = []
            theirs_lines: List[str] = []
            while index < len(lines) and not lines[index].startswith(CONFLICT_BASE):
                ours_lines.append(lines[index])
                index += 1
            if index >= len(lines):
                return StepResult("failed", "malformed conflict (missing base)")
            index += 1
            while index < len(lines) and not lines[index].startswith(CONFLICT_MID):
                base_lines.append(lines[index])
                index += 1
            if index >= len(lines):
                return StepResult("failed", "malformed conflict (missing mid)")
            index += 1
            while index < len(lines) and not lines[index].startswith(CONFLICT_END):
                theirs_lines.append(lines[index])
                index += 1
            if index >= len(lines):
                return StepResult("failed", "malformed conflict (missing end)")
            index += 1

            resolved_text, resolved_confidence, reason = resolve_hunk(hunk)
            resolved_lines = resolved_text.split("\n") if resolved_text else []
            new_lines.extend(resolved_lines)

            decision = {
                "file": conflict_file.file_path,
                "hunk_id": hunk.hunk_id,
                "resolution": reason,
                "confidence": resolved_confidence,
                "base": hunk.base,
                "ours": hunk.ours,
                "theirs": hunk.theirs,
            }
            decision_path = step_dir / f"conflict_{conflict_file.file_path.replace('/', '_')}_{hunk.hunk_id}.json"
            write_json(decision_path, decision)
        else:
            new_lines.append(line)
            index += 1

    file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return StepResult("ok")


def file_has_conflict_markers(file_path: Path) -> bool:
    with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith(CONFLICT_START):
                return True
    return False


def ensure_clean_conflicts(repo_path: Path, conflict_files: List[ConflictFile]) -> StepResult:
    for conflict in conflict_files:
        file_path = repo_path / conflict.file_path
        if file_path.exists() and file_has_conflict_markers(file_path):
            return StepResult("failed", f"conflict markers remain in {conflict.file_path}")
    return StepResult("ok")


def commit_checkpoint(repo_path: Path, message: str) -> None:
    run_git(repo_path, ["add", "-A"], check=True)
    run_git(repo_path, ["commit", "--allow-empty", "-m", message], check=True)


def collect_diff_stats(repo_path: Path) -> Tuple[int, int]:
    result = run_git(repo_path, ["diff", "--numstat"], check=True)
    touched_files = 0
    changed_lines = 0
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added = 0 if parts[0] == "-" else int(parts[0])
        deleted = 0 if parts[1] == "-" else int(parts[1])
        touched_files += 1
        changed_lines += added + deleted
    return touched_files, changed_lines


def enforce_safety_bounds(repo_path: Path) -> StepResult:
    touched_files, changed_lines = collect_diff_stats(repo_path)
    if touched_files > MAX_TOUCHED_FILES:
        return StepResult("failed", "touched files limit exceeded")
    if changed_lines > MAX_CHANGED_LINES:
        return StepResult("failed", "changed lines limit exceeded")
    return StepResult("ok")


def run_compile(repo_path: Path) -> subprocess.CompletedProcess:
    return run_cmd(["./gradlew", "compileJava"], cwd=repo_path, check=False)


def parse_compile_errors(output: str) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    pattern = re.compile(r"^(.*\.java):(\d+):\s+error:\s+(.*)$")
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if match:
            errors.append(
                {
                    "file": match.group(1),
                    "line": match.group(2),
                    "message": match.group(3),
                }
            )
    return errors


def run_tests(repo_path: Path, test_task: Optional[str]) -> subprocess.CompletedProcess:
    task = test_task or "test"
    return run_cmd(["./gradlew", task], cwd=repo_path, check=False)


def parse_test_failures(output: str) -> List[Dict[str, str]]:
    failures: List[Dict[str, str]] = []
    for line in output.splitlines():
        if line.startswith("FAILED"):
            failures.append({"test": line.strip(), "details": ""})
    return failures


def write_step_artifacts(step_dir: Path, payload: Dict[str, object]) -> None:
    step_dir.mkdir(parents=True, exist_ok=True)
    write_json(step_dir / "summary.json", payload)


def apply_agent_patch(repo_path: Path, patch_path: Path) -> StepResult:
    if not patch_path.exists():
        return StepResult("failed", f"missing patch {patch_path}")
    patch = patch_path.read_text(encoding="utf-8")
    if not patch.strip():
        return StepResult("failed", "empty patch")
    try:
        run_git(repo_path, ["apply", patch_path.as_posix()], check=True)
    except subprocess.CalledProcessError as error:
        return StepResult("failed", f"patch apply failed: {error.stderr.strip()}")
    return StepResult("ok")


def resolve_conflicts(
    repo_path: Path,
    conflict_files: List[ConflictFile],
    artifacts_dir: Path,
    per_file_budget: int,
) -> StepResult:
    step_index = 1
    for conflict_file in conflict_files:
        step_dir = artifacts_dir / f"conflict_step_{step_index}"
        step_dir.mkdir(parents=True, exist_ok=True)
        result = apply_conflict_resolution(repo_path, conflict_file, step_dir, per_file_budget)
        if result.status != "ok":
            write_step_artifacts(
                step_dir,
                {"status": "failed", "reason": result.reason, "file": conflict_file.file_path},
            )
            return result
        safety = enforce_safety_bounds(repo_path)
        if safety.status != "ok":
            write_step_artifacts(step_dir, {"status": "failed", "reason": safety.reason})
            return safety
        commit_checkpoint(repo_path, f"merge-agent: resolve conflicts step {step_index}")
        write_step_artifacts(step_dir, {"status": "ok", "file": conflict_file.file_path})
        step_index += 1

    return ensure_clean_conflicts(repo_path, conflict_files)


def compile_loop(
    repo_path: Path,
    artifacts_dir: Path,
    max_iterations: int,
) -> StepResult:
    previous_error_count: Optional[int] = None
    stagnation = 0
    for iteration in range(1, max_iterations + 1):
        step_dir = artifacts_dir / f"compile_step_{iteration}"
        result = run_compile(repo_path)
        output = f"{result.stdout}\n{result.stderr}"
        errors = parse_compile_errors(output)
        write_step_artifacts(
            step_dir,
            {
                "status": "ok" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "errors": errors,
            },
        )
        (step_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
        (step_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")

        if result.returncode == 0:
            return StepResult("ok")

        error_count = len(errors)
        if previous_error_count is not None and error_count >= previous_error_count:
            stagnation += 1
        else:
            stagnation = 0
        previous_error_count = error_count
        if stagnation >= 2:
            return StepResult("failed", "compile errors stagnated")

        patch_path = step_dir / "patch.diff"
        patch_result = apply_agent_patch(repo_path, patch_path)
        if patch_result.status != "ok":
            return StepResult("failed", "compile fix patch missing")

        safety = enforce_safety_bounds(repo_path)
        if safety.status != "ok":
            return safety
        commit_checkpoint(repo_path, f"merge-agent: compile fix step {iteration}")

    return StepResult("failed", "compile iteration budget exceeded")


def test_loop(
    repo_path: Path,
    artifacts_dir: Path,
    max_iterations: int,
    test_task: Optional[str],
) -> StepResult:
    previous_failure_count: Optional[int] = None
    stagnation = 0
    for iteration in range(1, max_iterations + 1):
        step_dir = artifacts_dir / f"test_step_{iteration}"
        result = run_tests(repo_path, test_task)
        output = f"{result.stdout}\n{result.stderr}"
        failures = parse_test_failures(output)
        write_step_artifacts(
            step_dir,
            {
                "status": "ok" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "failures": failures,
            },
        )
        (step_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
        (step_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")

        if result.returncode == 0:
            return StepResult("ok")

        failure_count = len(failures)
        if previous_failure_count is not None and failure_count >= previous_failure_count:
            stagnation += 1
        else:
            stagnation = 0
        previous_failure_count = failure_count
        if stagnation >= 2:
            return StepResult("failed", "test failures stagnated")

        patch_path = step_dir / "patch.diff"
        patch_result = apply_agent_patch(repo_path, patch_path)
        if patch_result.status != "ok":
            return StepResult("failed", "test fix patch missing")

        safety = enforce_safety_bounds(repo_path)
        if safety.status != "ok":
            return safety
        commit_checkpoint(repo_path, f"merge-agent: test fix step {iteration}")

    return StepResult("failed", "test iteration budget exceeded")


def load_workspace_metadata(workspace_path: Path) -> Dict[str, object]:
    metadata_path = workspace_path / "workspace_metadata.json"
    if not metadata_path.exists():
        raise RuntimeError(f"Missing workspace metadata at {metadata_path}")
    return load_json(metadata_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2 automated resolution loop")
    parser.add_argument(
        "--workspace",
        required=True,
        help="Path to the Phase 1 workspace containing workspace_metadata.json",
    )
    parser.add_argument(
        "--conflict-budget-per-file",
        type=int,
        default=DEFAULT_CONFLICT_BUDGET_PER_FILE,
    )
    parser.add_argument(
        "--compile-iterations",
        type=int,
        default=DEFAULT_COMPILE_ITERATIONS,
    )
    parser.add_argument(
        "--test-iterations",
        type=int,
        default=DEFAULT_TEST_ITERATIONS,
    )
    parser.add_argument(
        "--test-task",
        default=None,
        help="Optional Gradle test task to run",
    )

    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()
    metadata = load_workspace_metadata(workspace_path)
    repo_path = Path(metadata["repo_path"]).resolve()
    conflict_output = Path(metadata["conflict_output"]).resolve()

    phase1_payload = load_json(conflict_output)
    conflict_files = parse_conflicts(phase1_payload)

    artifacts_dir = workspace_path / "artifacts" / "phase2"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    phase2_summary = {
        "started_at": datetime.utcnow().isoformat() + "Z",
        "conflicts": len(conflict_files),
    }

    if conflict_files:
        conflict_result = resolve_conflicts(
            repo_path, conflict_files, artifacts_dir, args.conflict_budget_per_file
        )
        phase2_summary["conflict_resolution"] = conflict_result.__dict__
        if conflict_result.status != "ok":
            write_json(artifacts_dir / "phase2_summary.json", phase2_summary)
            return

    compile_result = compile_loop(repo_path, artifacts_dir, args.compile_iterations)
    phase2_summary["compile"] = compile_result.__dict__
    if compile_result.status != "ok":
        write_json(artifacts_dir / "phase2_summary.json", phase2_summary)
        return

    test_result = test_loop(
        repo_path, artifacts_dir, args.test_iterations, args.test_task
    )
    phase2_summary["tests"] = test_result.__dict__

    write_json(artifacts_dir / "phase2_summary.json", phase2_summary)


if __name__ == "__main__":
    main()
