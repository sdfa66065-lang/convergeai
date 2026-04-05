from __future__ import annotations

from pathlib import Path

import pytest

from benchmark.fixtures.registry import FixtureManifest
from benchmark.grader.grader import BenchmarkGrader
from benchmark.runner.track import Track, TrackResult

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "01_telemetry_drop"

GOOD_RESOLUTION = '''\
def distill_context(ticket_id: str, target_ref: str):
    """Blend: support Jira tickets and GitHub refs with fork telemetry/cache."""
    log_telemetry("distill_context_called", ticket_id, target_ref)
    key = ticket_id or target_ref
    if cache.exists(key):
        return cache.get(key)
    if ticket_id:
        return fetch_jira_payload(ticket_id)
    return fetch_github_payload(target_ref)
'''

BAD_UPSTREAM_ONLY = '''\
def distill_context(target_ref: str):
    return fetch_github_payload(target_ref)
'''


@pytest.fixture
def manifest() -> FixtureManifest:
    return FixtureManifest.from_dir(FIXTURE_DIR)


def test_grader_passes_good_resolution(tmp_path: Path, manifest: FixtureManifest):
    (tmp_path / "distill_context.py").write_text(GOOD_RESOLUTION, encoding="utf-8")
    g = BenchmarkGrader()
    r = g.grade(
        manifest,
        tmp_path,
        track="control",
        run_index=0,
        executor_result=TrackResult(track=Track.CONTROL),
    )
    assert r.overall_pass
    assert {x.gate for x in r.gates} == {"syntax", "behavioral", "semantic"}


def test_grader_fails_bad_resolution_semantic(tmp_path: Path, manifest: FixtureManifest):
    (tmp_path / "distill_context.py").write_text(BAD_UPSTREAM_ONLY, encoding="utf-8")
    g = BenchmarkGrader()
    r = g.grade(
        manifest,
        tmp_path,
        track="control",
        run_index=0,
        executor_result=None,
    )
    assert not r.overall_pass
    semantic = next(x for x in r.gates if x.gate == "semantic")
    assert not semantic.passed
