from __future__ import annotations

from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_no_markers():
    for p in _root().glob("*.js"):
        t = p.read_text(encoding="utf-8")
        assert "<<<<<<<" not in t


def test_math_uses_options_object():
    t = (_root() / "math.js").read_text(encoding="utf-8")
    assert "options" in t
    assert "options.a" in t or "options?.a" in t


def test_billing_calls_with_object():
    t = (_root() / "enterprise-billing.js").read_text(encoding="utf-8")
    assert "calculate(100, 50)" not in t
    assert "calculate({" in t or "calculate({ " in t
