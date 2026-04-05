from __future__ import annotations

from pathlib import Path


def _read() -> str:
    return (Path(__file__).resolve().parent.parent / "config.js").read_text(encoding="utf-8")


def test_no_markers():
    assert "<<<<<<<" not in _read()


def test_retry_limit_and_three():
    t = _read()
    assert "retryLimit" in t
    assert "3" in t
