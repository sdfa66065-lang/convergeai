from __future__ import annotations

from pathlib import Path

from benchmark.config import BenchmarkConfig
from benchmark.fixtures.registry import FixtureRegistry
from benchmark.grader.grader import BenchmarkGrader
from benchmark.grader.result import BenchmarkReport, FixtureGradingResult, GateResult
from benchmark.runner.executor import TrackExecutor
from benchmark.runner.sandbox import SandboxManager
from benchmark.runner.track import Track, TrackResult


class BenchmarkOrchestrator:
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.sandbox_mgr = SandboxManager(config)
        self.executor = TrackExecutor(config)
        self.grader = BenchmarkGrader()

    def discover(self, names: list[str] | None = None):
        all_fixtures = FixtureRegistry.discover(self.config.fixtures_dir)
        if not names:
            return all_fixtures
        want = set(names)
        return [f for f in all_fixtures if f.name in want]

    def run_all(
        self,
        fixture_names: list[str] | None = None,
        tracks: list[Track] | None = None,
        runs: int = 1,
        dry_run: bool = False,
    ) -> BenchmarkReport:
        fixtures = self.discover(fixture_names)
        if tracks is None:
            tracks = [Track.CONTROL, Track.EXPERIMENT]

        self.config.temp_root.mkdir(parents=True, exist_ok=True)
        results: list[FixtureGradingResult] = []

        for fx in fixtures:
            for track in tracks:
                for run_idx in range(runs):
                    sandbox_dir = self.sandbox_mgr.create(fx.name, track.value, run_idx)
                    exec_result: TrackResult | None = None
                    try:
                        self.sandbox_mgr.run_setup(fx, sandbox_dir)
                        if dry_run:
                            results.append(
                                FixtureGradingResult(
                                    fixture_name=fx.name,
                                    track=track.value,
                                    run_index=run_idx,
                                    gates=[
                                        GateResult(
                                            gate="dry_run",
                                            passed=True,
                                            details=f"Sandbox ready at {sandbox_dir}",
                                        )
                                    ],
                                    overall_pass=True,
                                    elapsed_seconds=0.0,
                                )
                            )
                            continue

                        exec_result = self.executor.execute(fx, sandbox_dir, track)
                        graded = self.grader.grade(
                            fx,
                            sandbox_dir,
                            track.value,
                            run_idx,
                            executor_result=exec_result,
                        )
                        results.append(graded)
                    finally:
                        self.sandbox_mgr.cleanup_sandbox(sandbox_dir)

        passed = sum(1 for r in results if r.overall_pass)
        total = len(results)
        summary = f"{passed}/{total} runs passed overall"
        return BenchmarkReport(results=results, summary=summary)
