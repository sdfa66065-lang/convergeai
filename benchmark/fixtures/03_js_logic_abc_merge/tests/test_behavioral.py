from __future__ import annotations

from pathlib import Path


def _read() -> str:
    return (Path(__file__).resolve().parent.parent / "logic.js").read_text(encoding="utf-8")


def test_no_markers():
    t = _read()
    assert "<<<<<<<" not in t


def test_merged_string_order():
    t = _read()
    assert "a1b2c" in t
