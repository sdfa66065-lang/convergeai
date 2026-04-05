from __future__ import annotations

from pathlib import Path


def _read(name: str) -> str:
    return (Path(__file__).resolve().parent.parent / name).read_text(encoding="utf-8")


def test_no_markers():
    t = _read("auth.js")
    for m in ("<<<<<<<", "=======", ">>>>>>>"):
        assert m not in t


def test_blended_auth():
    t = _read("auth.js")
    assert "@internal.com" in t
    assert "requestObject" in t
    assert "user" in t and "pass" in t
