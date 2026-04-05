from __future__ import annotations

from pathlib import Path

from benchmark.fixtures.registry import FixtureManifest
from benchmark.grader.result import GateResult


def run_semantic_gate(
    fixture: FixtureManifest, sandbox_dir: Path
) -> GateResult:
    checks = fixture.semantic_checks
    combined: list[str] = []
    for rel in fixture.conflict_files:
        fp = sandbox_dir / rel
        if not fp.is_file():
            return GateResult(
                gate="semantic",
                passed=False,
                details="",
                error=f"Missing file for semantic check: {rel}",
            )
        combined.append(fp.read_text(encoding="utf-8", errors="replace"))
    blob = "\n".join(combined)

    for needle in checks.must_contain:
        if needle not in blob:
            return GateResult(
                gate="semantic",
                passed=False,
                details=f"Missing required substring: {needle!r}",
                error="must_contain failed",
            )

    for needle in checks.must_not_contain:
        if needle in blob:
            return GateResult(
                gate="semantic",
                passed=False,
                details=f"Forbidden substring present: {needle!r}",
                error="must_not_contain failed",
            )

    return GateResult(
        gate="semantic",
        passed=True,
        details=f"All {len(checks.must_contain)} must_contain and "
        f"{len(checks.must_not_contain)} must_not_contain checks passed",
        error=None,
    )
