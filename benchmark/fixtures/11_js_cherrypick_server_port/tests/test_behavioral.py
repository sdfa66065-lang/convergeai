from __future__ import annotations

from pathlib import Path


def _read() -> str:
    return (Path(__file__).resolve().parent.parent / "server.js").read_text(encoding="utf-8")


def test_no_markers():
    assert "<<<<<<<" not in _read()


def test_merged_server_flags():
    t = _read()
    assert "process.env.PORT" in t
    assert "isSecureMode" in t
    assert "fork: smoke test" in t
