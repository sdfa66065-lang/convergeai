from __future__ import annotations

import py_compile
import shutil
import subprocess
from pathlib import Path

from benchmark.fixtures.registry import FixtureManifest
from benchmark.grader.result import GateResult

CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


def _marker_check(content: str) -> str | None:
    for m in CONFLICT_MARKERS:
        if m in content:
            return f"Conflict marker {m!r} still present"
    return None


def _py_compile_file(path: Path) -> str | None:
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as e:
        return str(e)
    return None


def run_syntax_gate(
    fixture: FixtureManifest, sandbox_dir: Path
) -> GateResult:
    """Conflict-marker check + optional Python compile per conflict file."""
    details_parts: list[str] = []
    for rel in fixture.conflict_files:
        fp = sandbox_dir / rel
        if not fp.is_file():
            return GateResult(
                gate="syntax",
                passed=False,
                details="",
                error=f"Expected file missing: {rel}",
            )
        text = fp.read_text(encoding="utf-8", errors="replace")
        err = _marker_check(text)
        if err:
            return GateResult(
                gate="syntax",
                passed=False,
                details=text[:500],
                error=err,
            )
        if fixture.language == "python":
            cerr = _py_compile_file(fp)
            if cerr:
                return GateResult(
                    gate="syntax",
                    passed=False,
                    details=cerr,
                    error=f"py_compile failed for {rel}",
                )
        elif fixture.language == "javascript" and shutil.which("node"):
            check = subprocess.run(
                ["node", "--check", str(fp)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if check.returncode != 0:
                return GateResult(
                    gate="syntax",
                    passed=False,
                    details=check.stderr or check.stdout,
                    error=f"node --check failed for {rel}",
                )
        details_parts.append(f"{rel}: ok")

    return GateResult(
        gate="syntax",
        passed=True,
        details="; ".join(details_parts),
        error=None,
    )
