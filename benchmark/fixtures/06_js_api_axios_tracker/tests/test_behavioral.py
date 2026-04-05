from __future__ import annotations

from pathlib import Path


def _read() -> str:
    return (Path(__file__).resolve().parent.parent / "api.js").read_text(encoding="utf-8")


def test_no_markers():
    assert "<<<<<<<" not in _read()


def test_axios_and_tracker():
    t = _read()
    assert "axios" in t
    assert "tracker" in t
