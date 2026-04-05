from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from benchmark.fixtures.registry import FixtureManifest
from benchmark.grader.result import GateResult


def run_behavioral_gate(
    fixture: FixtureManifest, sandbox_dir: Path
) -> GateResult:
    tests_src = fixture.base_dir / "tests"
    if not tests_src.is_dir():
        return GateResult(
            gate="behavioral",
            passed=True,
            details="No tests/ directory on fixture; skipped",
            error=None,
        )

    dest = sandbox_dir / "tests"
    shutil.copytree(tests_src, dest, dirs_exist_ok=True)

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(dest), "-v", "--tb=short"],
        cwd=str(sandbox_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        return GateResult(
            gate="behavioral",
            passed=False,
            details=out[-8000:],
            error=f"pytest exited {proc.returncode}",
        )
    return GateResult(
        gate="behavioral",
        passed=True,
        details=out[-4000:] if len(out) > 4000 else out,
        error=None,
    )
