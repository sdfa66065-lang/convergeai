from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

from benchmark.config import BenchmarkConfig
from benchmark.fixtures.registry import FixtureManifest


class FixtureSetupError(Exception):
    pass


class SandboxManager:
    def __init__(self, config: BenchmarkConfig):
        self.temp_root = config.temp_root
        self.cleanup = config.cleanup_sandboxes

    def create(self, fixture_name: str, track: str, run_idx: int) -> Path:
        """Create an isolated temp directory for one run."""
        dirname = f"{fixture_name}_{track}_run{run_idx}_{uuid.uuid4().hex[:8]}"
        sandbox = self.temp_root / dirname
        sandbox.mkdir(parents=True, exist_ok=True)
        return sandbox

    def run_setup(self, fixture: FixtureManifest, sandbox_dir: Path) -> None:
        """Execute the fixture's setup.sh to create a git repo with a conflict."""
        result = subprocess.run(
            ["bash", str(fixture.setup_script), str(sandbox_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise FixtureSetupError(
                f"Setup failed for {fixture.name}:\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        if fixture.verify_git_conflicts:
            self._verify_conflict_state(fixture, sandbox_dir)

    def _verify_conflict_state(
        self, fixture: FixtureManifest, sandbox_dir: Path
    ) -> None:
        """Verify git reports the expected files as conflicted."""
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=sandbox_dir,
            capture_output=True,
            text=True,
        )
        conflicted = set(result.stdout.strip().splitlines())
        expected = set(fixture.conflict_files)
        missing = expected - conflicted
        if missing:
            raise FixtureSetupError(
                f"Expected conflicts in {missing} but git reports: {conflicted}"
            )

    def collect_resolved_files(
        self, fixture: FixtureManifest, sandbox_dir: Path
    ) -> dict[str, Path]:
        """Return paths to the conflict files in the sandbox (post-resolution)."""
        return {
            name: sandbox_dir / name
            for name in fixture.conflict_files
            if (sandbox_dir / name).exists()
        }

    def cleanup_sandbox(self, sandbox_dir: Path) -> None:
        """Remove a sandbox directory."""
        if self.cleanup and sandbox_dir.exists():
            shutil.rmtree(sandbox_dir, ignore_errors=True)
