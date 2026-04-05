from __future__ import annotations

from pathlib import Path


def _read() -> str:
    return (Path(__file__).resolve().parent.parent / "network.js").read_text(encoding="utf-8")


def test_no_markers():
    assert "<<<<<<<" not in _read()


def test_secure_request_and_proxy():
    t = _read()
    assert "performSecureRequest" in t
    assert "internal-proxy.com" in t
