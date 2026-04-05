from __future__ import annotations

import ast
from pathlib import Path


def _fixture_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _distill_path() -> Path:
    return _fixture_root() / "distill_context.py"


def test_no_conflict_markers():
    text = _distill_path().read_text(encoding="utf-8")
    for m in ("<<<<<<<", "=======", ">>>>>>>"):
        assert m not in text, f"unexpected conflict marker {m!r}"


def test_distill_context_keeps_both_parameters():
    tree = ast.parse(_distill_path().read_text(encoding="utf-8"))
    fn = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "distill_context"
    )
    params = {a.arg for a in fn.args.args}
    assert "ticket_id" in params
    assert "target_ref" in params


def test_blended_implementation_symbols():
    text = _distill_path().read_text(encoding="utf-8")
    for needle in (
        "log_telemetry",
        "cache.exists",
        "cache.get",
        "fetch_jira_payload",
        "fetch_github_payload",
    ):
        assert needle in text
