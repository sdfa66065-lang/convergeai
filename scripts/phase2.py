#!/usr/bin/env python3

import argparse
import difflib
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
    is_binary: bool = False
    binary_policy: Optional[str] = None


@dataclass
class ConflictFile:
    file_path: str
    hunks: List[ConflictHunk]


@dataclass
class StepResult:
    status: str
    reason: Optional[str] = None
    code: Optional[str] = None


@dataclass
class DiffStats:
    touched_files: int
    changed_lines: int


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
                    is_binary=bool(hunk.get("is_binary", False)),
                    binary_policy=hunk.get("binary_policy"),
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


def build_unified_diff(
    original_lines: List[str],
    new_lines: List[str],
    file_path: str,
) -> str:
    diff = difflib.unified_diff(
        original_lines,
        new_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
    )
    return "\n".join(diff) + "\n"


def write_agent_request(step_dir: Path, payload: Dict[str, object]) -> None:
    write_json(step_dir / "agent_request.json", payload)


def write_agent_response(step_dir: Path, payload: Dict[str, object]) -> None:
    write_json(step_dir / "agent_response.json", payload)


def extract_context(file_path: Path, line_number: int, radius: int = 4) -> Dict[str, object]:
    if not file_path.exists():
        return {"file": file_path.as_posix(), "line": line_number, "lines": []}
    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    start = max(line_number - radius - 1, 0)
    end = min(line_number + radius, len(lines))
    return {
        "file": file_path.as_posix(),
        "line": line_number,
        "start_line": start + 1,
        "end_line": end,
        "lines": lines[start:end],
    }


def apply_conflict_resolution(
    repo_path: Path,
    conflict_file: ConflictFile,
    step_dir: Path,
    per_file_budget: int,
) -> StepResult:
    file_path = repo_path / conflict_file.file_path
    if not file_path.exists():
        return StepResult("failed", f"Missing file {conflict_file.file_path}", "missing_file")

    original_lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    new_lines: List[str] = []
    index = 0
    hunk_index = 0
    attempts = 0

    while index < len(original_lines):
        line = original_lines[index]
        if line.startswith(CONFLICT_START):
            if hunk_index >= len(conflict_file.hunks):
                return StepResult("failed", f"Hunk mismatch in {conflict_file.file_path}", "hunk_mismatch")
            hunk = conflict_file.hunks[hunk_index]
            hunk_index += 1
            attempts += 1
            if attempts > per_file_budget * len(conflict_file.hunks):
                return StepResult("failed", "conflict resolution budget exceeded", "budget_exceeded")
            index += 1
            ours_lines: List[str] = []
            base_lines: List[str] = []
            theirs_lines: List[str] = []
            while index < len(original_lines) and not original_lines[index].startswith(CONFLICT_BASE):
                ours_lines.append(original_lines[index])
                index += 1
            if index >= len(original_lines):
                return StepResult("failed", "malformed conflict (missing base)", "malformed_conflict")
            index += 1
            while index < len(original_lines) and not original_lines[index].startswith(CONFLICT_MID):
                base_lines.append(original_lines[index])
                index += 1
            if index >= len(original_lines):
                return StepResult("failed", "malformed conflict (missing mid)", "malformed_conflict")
            index += 1
            while index < len(original_lines) and not original_lines[index].startswith(CONFLICT_END):
                theirs_lines.append(original_lines[index])
                index += 1
            if index >= len(original_lines):
                return StepResult("failed", "malformed conflict (missing end)", "malformed_conflict")
            index += 1

            ours_text = "\n".join(ours_lines)
            base_text = "\n".join(base_lines)
            theirs_text = "\n".join(theirs_lines)
            request_payload = {
                "prompt_path": "prompts/conflict_resolver.md",
                "file_path": conflict_file.file_path,
                "hunk_id": hunk.hunk_id,
                "base": base_text,
                "ours": ours_text,
                "theirs": theirs_text,
                "context_before": hunk.context_before,
                "context_after": hunk.context_after,
            }
            hunk_dir = step_dir / f"hunk_{hunk.hunk_id}"
            hunk_dir.mkdir(parents=True, exist_ok=True)
            write_agent_request(hunk_dir, request_payload)

            resolved_text, resolved_confidence, reason = resolve_hunk(
                ConflictHunk(
                    hunk_id=hunk.hunk_id,
                    base=base_text,
                    ours=ours_text,
                    theirs=theirs_text,
                    context_before=hunk.context_before,
                    context_after=hunk.context_after,
                    confidence=hunk.confidence,
                )
            )
            resolved_lines = resolved_text.split("\n") if resolved_text else []
            new_lines.extend(resolved_lines)

            decision = {
                "file": conflict_file.file_path,
                "hunk_id": hunk.hunk_id,
                "resolution": reason,
                "confidence": resolved_confidence,
                "low_confidence": resolved_confidence < 0.6,
                "base": base_text,
                "ours": ours_text,
                "theirs": theirs_text,
            }
            write_agent_response(hunk_dir, decision)
        else:
            new_lines.append(line)
            index += 1

    patch_text = build_unified_diff(original_lines, new_lines, conflict_file.file_path)
    patch_path = step_dir / "patch.diff"
    patch_path.write_text(patch_text, encoding="utf-8")
    patch_result = apply_agent_patch(repo_path, patch_path)
    if patch_result.status != "ok":
        return StepResult("failed", patch_result.reason, "patch_apply_failed")
    return StepResult("ok")


def resolve_binary_conflict(
    repo_path: Path,
    conflict_file: ConflictFile,
    step_dir: Path,
) -> StepResult:
    policy = conflict_file.hunks[0].binary_policy or "skip"
    if policy == "skip":
        return StepResult("failed", "binary conflict policy set to skip", "binary_skip")
    if policy not in {"ours", "theirs"}:
        return StepResult(
            "failed",
            f"unsupported binary conflict policy: {policy}",
            "binary_unsupported",
        )
    try:
        run_git(repo_path, ["checkout", f"--{policy}", "--", conflict_file.file_path], check=True)
        run_git(repo_path, ["add", conflict_file.file_path], check=True)
    except subprocess.CalledProcessError as error:
        return StepResult(
            "failed",
            f"binary conflict checkout failed: {error.stderr.strip()}",
            "binary_checkout_failed",
        )
    decision = {
        "file": conflict_file.file_path,
        "resolution": policy,
        "confidence": conflict_file.hunks[0].confidence,
        "binary": True,
    }
    decision_path = step_dir / f"binary_{conflict_file.file_path.replace('/', '_')}.json"
    write_json(decision_path, decision)
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
            return StepResult(
                "failed",
                f"conflict markers remain in {conflict.file_path}",
                "conflict_markers_remain",
            )
    return StepResult("ok")


def commit_checkpoint(repo_path: Path, message: str) -> None:
    run_git(repo_path, ["add", "-A"], check=True)
    run_git(repo_path, ["commit", "--allow-empty", "-m", message], check=True)


def collect_diff_stats(repo_path: Path) -> DiffStats:
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
    return DiffStats(touched_files=touched_files, changed_lines=changed_lines)


def enforce_safety_bounds(repo_path: Path) -> StepResult:
    stats = collect_diff_stats(repo_path)
    if stats.touched_files > MAX_TOUCHED_FILES:
        return StepResult("failed", "touched files limit exceeded", "touched_files_limit")
    if stats.changed_lines > MAX_CHANGED_LINES:
        return StepResult("failed", "changed lines limit exceeded", "changed_lines_limit")
    return StepResult("ok")


def run_compile(repo_path: Path) -> subprocess.CompletedProcess:
    return run_cmd(["./gradlew", "compileJava"], cwd=repo_path, check=False)


def parse_compile_errors(output: str) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    pattern = re.compile(r"^(.*\.java):(\d+):\s+error:\s+(.*)$")
    symbol_pattern = re.compile(r"^\s*symbol:\s+(.*)$")
    location_pattern = re.compile(r"^\s*location:\s+(.*)$")
    lines = output.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        match = pattern.match(line)
        if match:
            error = {
                "file": match.group(1),
                "line": match.group(2),
                "message": match.group(3),
            }
            lookahead = index + 1
            while lookahead < len(lines):
                next_line = lines[lookahead].strip()
                symbol_match = symbol_pattern.match(next_line)
                if symbol_match:
                    error["symbol"] = symbol_match.group(1)
                    lookahead += 1
                    continue
                location_match = location_pattern.match(next_line)
                if location_match:
                    error["location"] = location_match.group(1)
                    lookahead += 1
                    continue
                break
            errors.append(error)
        index += 1
    return errors


def run_tests(repo_path: Path, test_task: Optional[str]) -> subprocess.CompletedProcess:
    task = test_task or "test"
    return run_cmd(["./gradlew", task], cwd=repo_path, check=False)


def parse_test_failures(output: str) -> List[Dict[str, str]]:
    failures: List[Dict[str, str]] = []
    header_pattern = re.compile(r"^(.+?) > (.+?) FAILED$")
    current: Optional[Dict[str, object]] = None
    for line in output.splitlines():
        header_match = header_pattern.match(line.strip())
        if header_match:
            if current:
                failures.append(current)
            current = {
                "test": header_match.group(0),
                "suite": header_match.group(1),
                "name": header_match.group(2),
                "details": [],
                "assertion_diff": [],
            }
            continue
        if current and (line.startswith(" ") or line.startswith("\t")):
            stripped = line.strip()
            current["details"].append(stripped)
            if stripped.lower().startswith("expected") or stripped.lower().startswith("but was"):
                current["assertion_diff"].append(stripped)
            continue
        if current and line.strip() == "":
            continue
        if current and line.strip().endswith("FAILED"):
            continue
    if current:
        failures.append(current)
    formatted: List[Dict[str, str]] = []
    for failure in failures:
        formatted.append(
            {
                "test": failure["test"],
                "suite": failure["suite"],
                "name": failure["name"],
                "details": "\n".join(failure["details"]),
                "assertion_diff": "\n".join(failure["assertion_diff"]),
            }
        )
    return formatted


def write_step_artifacts(step_dir: Path, payload: Dict[str, object]) -> None:
    step_dir.mkdir(parents=True, exist_ok=True)
    write_json(step_dir / "summary.json", payload)


def apply_agent_patch(repo_path: Path, patch_path: Path) -> StepResult:
    if not patch_path.exists():
        return StepResult("failed", f"missing patch {patch_path}", "patch_missing")
    patch = patch_path.read_text(encoding="utf-8")
    if not patch.strip():
        return StepResult("failed", "empty patch", "empty_patch")
    try:
        run_git(repo_path, ["apply", patch_path.as_posix()], check=True)
    except subprocess.CalledProcessError as error:
        return StepResult(
            "failed",
            f"patch apply failed: {error.stderr.strip()}",
            "patch_apply_failed",
        )
    return StepResult("ok")


def build_compile_agent_input(
    repo_path: Path,
    errors: List[Dict[str, str]],
) -> Dict[str, object]:
    contexts = []
    for error in errors:
        line = int(error.get("line", "1"))
        contexts.append(extract_context(repo_path / error["file"], line))
    return {
        "prompt_path": "prompts/compile_fixer.md",
        "errors": errors,
        "contexts": contexts,
    }


def build_test_agent_input(
    repo_path: Path,
    failures: List[Dict[str, str]],
) -> Dict[str, object]:
    contexts = []
    for failure in failures:
        details = failure.get("details", "")
        match = re.search(r"\(([^:]+\.java):(\d+)\)", details)
        if match:
            file_path = repo_path / match.group(1)
            line = int(match.group(2))
            contexts.append(extract_context(file_path, line))
    return {
        "prompt_path": "prompts/test_fixer.md",
        "failures": failures,
        "contexts": contexts,
    }


def auto_fix_compile_errors(
    repo_path: Path,
    errors: List[Dict[str, str]],
    step_dir: Path,
) -> Optional[Path]:
    patches_applied = False
    updated_files: Dict[Path, List[str]] = {}
    removals: Dict[Path, List[int]] = {}
    for error in errors:
        message = error.get("message", "")
        if "package" in message and "does not exist" in message:
            file_path = repo_path / error["file"]
            line_number = int(error.get("line", "1"))
            if not file_path.exists():
                continue
            removals.setdefault(file_path, []).append(line_number)
    for file_path, lines_to_remove in removals.items():
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        file_changed = False
        for line_number in sorted(lines_to_remove, reverse=True):
            if 1 <= line_number <= len(lines):
                candidate = lines[line_number - 1].strip()
                if candidate.startswith("import ") and candidate.endswith(";"):
                    lines.pop(line_number - 1)
                    patches_applied = True
                    file_changed = True
        if file_changed:
            updated_files[file_path] = lines
    if not patches_applied:
        return None
    patch_chunks: List[str] = []
    for file_path, new_lines in updated_files.items():
        original_lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        patch_chunks.append(build_unified_diff(original_lines, new_lines, file_path.relative_to(repo_path).as_posix()))
    patch_text = "".join(patch_chunks)
    patch_path = step_dir / "patch.diff"
    patch_path.write_text(patch_text, encoding="utf-8")
    response = {
        "patch": patch_text,
        "touched_files": [path.relative_to(repo_path).as_posix() for path in updated_files.keys()],
        "rationale": "Removed import lines for missing packages reported by the compiler.",
        "confidence": 0.35,
    }
    write_agent_response(step_dir, response)
    return patch_path


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
        if any(hunk.is_binary for hunk in conflict_file.hunks):
            result = resolve_binary_conflict(repo_path, conflict_file, step_dir)
        else:
            result = apply_conflict_resolution(repo_path, conflict_file, step_dir, per_file_budget)
        if result.status != "ok":
            write_step_artifacts(
                step_dir,
                {
                    "status": "failed",
                    "reason": result.reason,
                    "code": result.code,
                    "file": conflict_file.file_path,
                },
            )
            return result
        safety = enforce_safety_bounds(repo_path)
        if safety.status != "ok":
            write_step_artifacts(
                step_dir,
                {"status": "failed", "reason": safety.reason, "code": safety.code},
            )
            return safety
        diff_stats = collect_diff_stats(repo_path)
        commit_checkpoint(repo_path, f"merge-agent: resolve conflicts step {step_index}")
        write_step_artifacts(
            step_dir,
            {
                "status": "ok",
                "file": conflict_file.file_path,
                "touched_files": diff_stats.touched_files,
                "changed_lines": diff_stats.changed_lines,
            },
        )
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
        step_dir.mkdir(parents=True, exist_ok=True)
        result = run_compile(repo_path)
        output = f"{result.stdout}\n{result.stderr}"
        errors = parse_compile_errors(output)
        request_payload = build_compile_agent_input(repo_path, errors)
        write_agent_request(step_dir, request_payload)
        summary = {
            "status": "ok" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "errors": errors,
            "error_count": len(errors),
            "stdout_path": "stdout.txt",
            "stderr_path": "stderr.txt",
        }
        write_step_artifacts(step_dir, summary)
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
            return StepResult("failed", "compile errors stagnated", "compile_stagnation")

        patch_path = step_dir / "patch.diff"
        if not patch_path.exists():
            patch_path = auto_fix_compile_errors(repo_path, errors, step_dir) or patch_path
        patch_result = apply_agent_patch(repo_path, patch_path)
        if patch_result.status != "ok":
            return StepResult("failed", "compile fix patch missing", "compile_patch_missing")

        safety = enforce_safety_bounds(repo_path)
        if safety.status != "ok":
            return safety
        diff_stats = collect_diff_stats(repo_path)
        summary["touched_files"] = diff_stats.touched_files
        summary["changed_lines"] = diff_stats.changed_lines
        write_step_artifacts(step_dir, summary)
        commit_checkpoint(repo_path, f"merge-agent: compile fix step {iteration}")

    return StepResult("failed", "compile iteration budget exceeded", "compile_budget_exceeded")


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
        step_dir.mkdir(parents=True, exist_ok=True)
        result = run_tests(repo_path, test_task)
        output = f"{result.stdout}\n{result.stderr}"
        failures = parse_test_failures(output)
        request_payload = build_test_agent_input(repo_path, failures)
        write_agent_request(step_dir, request_payload)
        summary = {
            "status": "ok" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "failures": failures,
            "failure_count": len(failures),
            "stdout_path": "stdout.txt",
            "stderr_path": "stderr.txt",
        }
        write_step_artifacts(step_dir, summary)
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
            return StepResult("failed", "test failures stagnated", "test_stagnation")

        patch_path = step_dir / "patch.diff"
        patch_result = apply_agent_patch(repo_path, patch_path)
        if patch_result.status != "ok":
            return StepResult("failed", "test fix patch missing", "test_patch_missing")

        safety = enforce_safety_bounds(repo_path)
        if safety.status != "ok":
            return safety
        diff_stats = collect_diff_stats(repo_path)
        summary["touched_files"] = diff_stats.touched_files
        summary["changed_lines"] = diff_stats.changed_lines
        write_step_artifacts(step_dir, summary)
        commit_checkpoint(repo_path, f"merge-agent: test fix step {iteration}")

    return StepResult("failed", "test iteration budget exceeded", "test_budget_exceeded")


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
