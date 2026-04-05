from __future__ import annotations

from pathlib import Path


def _read() -> str:
    return (Path(__file__).resolve().parent.parent / "features.js").read_text(encoding="utf-8")


def test_no_markers():
    assert "<<<<<<<" not in _read()


def test_both_features():
    t = _read()
    assert "sso-saml" in t
    assert "dark-mode" in t
