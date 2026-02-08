#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


CONFLICT_START = "<<<<<<<"
CONFLICT_BASE = "|||||||"
CONFLICT_MID = "======="
CONFLICT_END = ">>>>>>>"


@dataclass
class WorkspaceInfo:
    path: Path
    repo_path: Path
    base_sha: str


@dataclass
class MergeResult:
    status: str
    head_sha: Optional[str]
    conflicted_files: List[str]


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


def run_git(repo_path: Path, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_path), *args],
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def load_config(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def create_workspace(workspace_root: Path, run_id: str) -> Path:
    workspace_path = workspace_root / run_id
    workspace_path.mkdir(parents=True, exist_ok=False)
    return workspace_path


def clone_repo(repository_url: str, repo_path: Path, clone_depth: Optional[int]) -> None:
    cmd = ["git", "clone"]
    if clone_depth:
        cmd.extend(["--depth", str(clone_depth)])
    cmd.extend([repository_url, str(repo_path)])
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def ensure_remote(repo_path: Path, remote_name: str, remote_url: Optional[str]) -> None:
    remotes = run_git(repo_path, ["remote"], check=True).stdout.split()
    if remote_name in remotes:
        return
    if not remote_url:
        raise RuntimeError(
            f"Remote '{remote_name}' is missing and no upstream_url was provided."
        )
    run_git(repo_path, ["remote", "add", remote_name, remote_url], check=True)


def fetch_remote(repo_path: Path, remote_name: str) -> None:
    run_git(repo_path, ["fetch", "--prune", remote_name], check=True)


def checkout_base(repo_path: Path, base_ref: str) -> str:
    run_git(repo_path, ["checkout", base_ref], check=True)
    return run_git(repo_path, ["rev-parse", "HEAD"], check=True).stdout.strip()


def attempt_merge(repo_path: Path, upstream_remote: str, upstream_ref: str) -> MergeResult:
    try:
        run_git(
            repo_path,
            [
                "-c",
                "merge.conflictstyle=diff3",
                "merge",
                f"{upstream_remote}/{upstream_ref}",
            ],
            check=True,
        )
        head_sha = run_git(repo_path, ["rev-parse", "HEAD"], check=True).stdout.strip()
        return MergeResult("clean", head_sha, [])
    except subprocess.CalledProcessError as error:
        if "CONFLICT" not in error.stderr and "Automatic merge failed" not in error.stderr:
            raise
        conflicted_files = (
            run_git(repo_path, ["diff", "--name-only", "--diff-filter=U"], check=True)
            .stdout.strip()
            .splitlines()
        )
        return MergeResult("conflicted", None, conflicted_files)


def scan_for_conflicts(repo_path: Path) -> List[str]:
    conflicted_files: List[str] = []
    for path in repo_path.rglob("*"):
        if not path.is_file() or "/.git/" in str(path):
            continue
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if line.startswith(CONFLICT_START):
                    conflicted_files.append(str(path.relative_to(repo_path)))
                    break
    return conflicted_files


def parse_conflicts(file_path: Path, context_lines: int) -> List[ConflictHunk]:
    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    hunks: List[ConflictHunk] = []
    index = 0
    hunk_count = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith(CONFLICT_START):
            hunk_count += 1
            start_index = index
            ours_lines = []
            base_lines = []
            theirs_lines = []
            index += 1
            while index < len(lines) and not lines[index].startswith(CONFLICT_BASE):
                ours_lines.append(lines[index])
                index += 1
            if index >= len(lines):
                raise ValueError(f"Malformed conflict in {file_path} (missing base marker)")
            index += 1
            while index < len(lines) and not lines[index].startswith(CONFLICT_MID):
                base_lines.append(lines[index])
                index += 1
            if index >= len(lines):
                raise ValueError(f"Malformed conflict in {file_path} (missing mid marker)")
            index += 1
            while index < len(lines) and not lines[index].startswith(CONFLICT_END):
                theirs_lines.append(lines[index])
                index += 1
            if index >= len(lines):
                raise ValueError(f"Malformed conflict in {file_path} (missing end marker)")
            end_index = index
            index += 1
            context_before = lines[max(0, start_index - context_lines) : start_index]
            context_after = lines[end_index + 1 : end_index + 1 + context_lines]
            confidence = score_confidence(ours_lines, base_lines, theirs_lines)
            hunks.append(
                ConflictHunk(
                    hunk_id=f"hunk-{hunk_count}",
                    base="\n".join(base_lines),
                    ours="\n".join(ours_lines),
                    theirs="\n".join(theirs_lines),
                    context_before=context_before,
                    context_after=context_after,
                    confidence=confidence,
                )
            )
        else:
            index += 1
    return hunks


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def only_comments_or_imports(lines: List[str]) -> bool:
    content_lines = [line.strip() for line in lines if line.strip()]
    if not content_lines:
        return True
    for line in content_lines:
        if re.match(r"^(#|//|/\*|\*|--)", line):
            continue
        if re.match(r"^(import\s|from\s|using\s|require\(|include\s)", line):
            continue
        return False
    return True


def score_confidence(ours: List[str], base: List[str], theirs: List[str]) -> float:
    ours_text = "\n".join(ours)
    theirs_text = "\n".join(theirs)
    if ours_text == theirs_text:
        return 0.95
    if normalize_whitespace(ours_text) == normalize_whitespace(theirs_text):
        return 0.85
    if only_comments_or_imports(ours) and only_comments_or_imports(theirs):
        return 0.8
    if len(ours) > 20 or len(theirs) > 20:
        return 0.2
    signature_patterns = [r"\bclass\b", r"\bdef\b", r"\bfunction\b", r"\bpublic\b"]
    for pattern in signature_patterns:
        if re.search(pattern, ours_text) and re.search(pattern, theirs_text):
            if normalize_whitespace(ours_text) != normalize_whitespace(theirs_text):
                return 0.2
    if len(base) > 10 and (len(ours) != len(theirs)):
        return 0.3
    return 0.5


def write_conflict_json(
    output_path: Path,
    workspace_info: WorkspaceInfo,
    merge_result: MergeResult,
    conflicts: List[ConflictFile],
) -> None:
    payload = {
        "workspace_path": str(workspace_info.path),
        "base_sha": workspace_info.base_sha,
        "merge_status": merge_result.status,
        "head_sha": merge_result.head_sha,
        "conflicted_files": merge_result.conflicted_files,
        "conflicts": [
            {
                "file_path": conflict.file_path,
                "hunks": [
                    {
                        "hunk_id": hunk.hunk_id,
                        "base": hunk.base,
                        "ours": hunk.ours,
                        "theirs": hunk.theirs,
                        "context": {
                            "before": hunk.context_before,
                            "after": hunk.context_after,
                        },
                        "confidence": hunk.confidence,
                    }
                    for hunk in conflict.hunks
                ],
            }
            for conflict in conflicts
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def commit_checkpoint(repo_path: Path, message: str) -> None:
    run_git(repo_path, ["add", "-A"], check=True)
    run_git(repo_path, ["commit", "--allow-empty", "-m", message], check=True)


def determine_run_id(run_id: Optional[str]) -> str:
    if run_id:
        return run_id
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"run-{timestamp}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1 workspace and merge runner")
    parser.add_argument("--config", required=True, help="Path to input JSON config")
    parser.add_argument(
        "--workspace-root",
        default="./workspaces",
        help="Root directory for workspace runs",
    )
    parser.add_argument("--run-id", default=None, help="Optional run identifier")
    parser.add_argument(
        "--clone-depth", type=int, default=None, help="Optional git clone depth"
    )
    parser.add_argument(
        "--context-lines",
        type=int,
        default=3,
        help="Number of context lines around each conflict",
    )
    parser.add_argument(
        "--output",
        default="phase1_output.json",
        help="Filename for phase1 JSON output",
    )

    args = parser.parse_args()

    config = load_config(Path(args.config))
    repository_url = str(config["repository_url"])
    base_ref = str(config["base_ref"])
    upstream_remote = str(config["upstream_remote"])
    upstream_ref = str(config["upstream_ref"])
    upstream_url = config.get("upstream_url")

    workspace_root = Path(args.workspace_root).resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    run_id = determine_run_id(args.run_id)
    workspace_path = create_workspace(workspace_root, run_id)
    repo_path = workspace_path / "repo"

    clone_repo(repository_url, repo_path, args.clone_depth)
    run_git(repo_path, ["fetch", "--all", "--prune"], check=True)

    ensure_remote(repo_path, upstream_remote, upstream_url)
    fetch_remote(repo_path, upstream_remote)

    base_sha = checkout_base(repo_path, base_ref)
    workspace_info = WorkspaceInfo(path=workspace_path, repo_path=repo_path, base_sha=base_sha)

    merge_result = attempt_merge(repo_path, upstream_remote, upstream_ref)

    conflicted_files = scan_for_conflicts(repo_path)
    if merge_result.status == "conflicted" and not conflicted_files:
        raise RuntimeError("Merge reported conflicts but no conflict markers were found.")

    conflicts: List[ConflictFile] = []
    for file_path in conflicted_files:
        full_path = repo_path / file_path
        hunks = parse_conflicts(full_path, args.context_lines)
        conflicts.append(ConflictFile(file_path=file_path, hunks=hunks))

    output_path = workspace_path / args.output
    write_conflict_json(output_path, workspace_info, merge_result, conflicts)

    commit_checkpoint(repo_path, "Checkpoint after upstream merge attempt")

    metadata_path = workspace_path / "workspace_metadata.json"
    metadata = {
        "workspace_path": str(workspace_info.path),
        "repo_path": str(workspace_info.repo_path),
        "base_sha": workspace_info.base_sha,
        "merge_status": merge_result.status,
        "conflict_output": str(output_path),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
