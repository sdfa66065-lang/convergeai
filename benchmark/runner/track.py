from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Track(Enum):
    CONTROL = "control"
    EXPERIMENT = "experiment"


@dataclass
class TrackResult:
    track: Track
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    elapsed_seconds: float = 0.0
    session_id: str | None = None
    token_usage: dict[str, Any] | None = None
    command: list[str] = field(default_factory=list)
