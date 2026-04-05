from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

from benchmark.config import BenchmarkConfig
from benchmark.fixtures.registry import FixtureManifest
from benchmark.runner.track import Track, TrackResult


_SESSION_ID_PATTERNS = (
    re.compile(r"session[_\s-]*id[:\s]+([^\s]+)", re.I),
    re.compile(r"Session[:\s]+([0-9a-f-]{8,})", re.I),
)


class TrackExecutor:
    """Subprocess Goose (control) or converge.sh (experiment / ConvergeAI)."""

    def __init__(self, config: BenchmarkConfig):
        self.config = config

    def _prompt(self, fixture: FixtureManifest, track: Track) -> str:
        if track is Track.CONTROL:
            return fixture.goose_prompt_control
        return fixture.goose_prompt_experiment

    def _build_control_command(self, prompt: str) -> list[str]:
        return [self.config.goose_binary, "run", "-t", prompt]

    def _build_experiment_command(self, prompt: str) -> list[str]:
        """Mirror converge.sh: MCP + ai-maintainer instructions live in the wrapper."""
        script = self.config.converge_script
        if not script or not script.is_file():
            raise FileNotFoundError(
                f"converge_script not found: {script}. Set BenchmarkConfig.converge_script."
            )
        return ["bash", str(script), prompt]

    def _parse_session_id(self, blob: str) -> str | None:
        for pat in _SESSION_ID_PATTERNS:
            m = pat.search(blob)
            if m:
                return m.group(1).strip()
        return None

    def _maybe_token_usage(self, session_id: str | None) -> dict | None:
        if not session_id:
            return None
        try:
            proc = subprocess.run(
                [
                    self.config.goose_binary,
                    "session",
                    "export",
                    "--session-id",
                    session_id,
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        try:
            data = json.loads(proc.stdout)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return {"raw_export_chars": len(proc.stdout)}

    def execute(
        self,
        fixture: FixtureManifest,
        sandbox_dir: Path,
        track: Track,
    ) -> TrackResult:
        prompt = self._prompt(fixture, track)
        if track is Track.CONTROL:
            cmd = self._build_control_command(prompt)
        else:
            cmd = self._build_experiment_command(prompt)

        env = os.environ.copy()
        env["CONVERGEAI_ROOT"] = str(self.config.repo_root)

        timeout = max(30, fixture.timeout_seconds or self.config.default_timeout)
        start = time.perf_counter()
        proc = subprocess.run(
            cmd,
            cwd=str(sandbox_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.perf_counter() - start
        blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
        sid = self._parse_session_id(blob)
        tokens = self._maybe_token_usage(sid) if sid else None

        return TrackResult(
            track=track,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            returncode=proc.returncode,
            elapsed_seconds=elapsed,
            session_id=sid,
            token_usage=tokens,
            command=cmd,
        )
