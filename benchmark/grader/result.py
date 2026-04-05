from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class GateResult:
    gate: str
    passed: bool
    details: str = ""
    error: str | None = None


@dataclass
class FixtureGradingResult:
    fixture_name: str
    track: str
    run_index: int
    gates: list[GateResult] = field(default_factory=list)
    overall_pass: bool = False
    token_usage: dict[str, Any] | None = None
    elapsed_seconds: float = 0.0


@dataclass
class BenchmarkReport:
    results: list[FixtureGradingResult] = field(default_factory=list)
    summary: str = ""
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
