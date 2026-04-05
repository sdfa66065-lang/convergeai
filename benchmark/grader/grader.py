from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from benchmark.fixtures.registry import FixtureManifest
from benchmark.grader.behavioral_gate import run_behavioral_gate
from benchmark.grader.result import FixtureGradingResult, GateResult
from benchmark.grader.semantic_gate import run_semantic_gate
from benchmark.grader.syntax_gate import run_syntax_gate
from benchmark.runner.track import TrackResult


class BenchmarkGrader:
    def grade(
        self,
        fixture: FixtureManifest,
        sandbox_dir: Path,
        track: str,
        run_index: int,
        executor_result: TrackResult | None = None,
    ) -> FixtureGradingResult:
        syntax = run_syntax_gate(fixture, sandbox_dir)
        gates: list[GateResult] = [syntax]
        if not syntax.passed:
            return FixtureGradingResult(
                fixture_name=fixture.name,
                track=track,
                run_index=run_index,
                gates=gates,
                overall_pass=False,
                token_usage=executor_result.token_usage if executor_result else None,
                elapsed_seconds=executor_result.elapsed_seconds if executor_result else 0.0,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(run_behavioral_gate, fixture, sandbox_dir)
            f2 = pool.submit(run_semantic_gate, fixture, sandbox_dir)
            behavioral = f1.result()
            semantic = f2.result()

        gates.extend([behavioral, semantic])
        overall = behavioral.passed and semantic.passed

        return FixtureGradingResult(
            fixture_name=fixture.name,
            track=track,
            run_index=run_index,
            gates=gates,
            overall_pass=overall,
            token_usage=executor_result.token_usage if executor_result else None,
            elapsed_seconds=executor_result.elapsed_seconds if executor_result else 0.0,
        )
