from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BenchmarkConfig:
    repo_root: Path
    fixtures_dir: Path
    temp_root: Path
    goose_binary: str = "goose"
    converge_script: Path | None = None
    instructions_yaml: Path | None = None
    goose_profile: str = "ai-maintainer"
    default_timeout: int = 300
    cleanup_sandboxes: bool = True

    @classmethod
    def from_defaults(cls) -> BenchmarkConfig:
        repo_root = Path(__file__).resolve().parent.parent
        return cls(
            repo_root=repo_root,
            fixtures_dir=repo_root / "benchmark" / "fixtures",
            temp_root=Path(tempfile.gettempdir()) / "convergeai-bench",
            converge_script=repo_root / "converge.sh",
            instructions_yaml=repo_root / "goose" / "ai-maintainer.yaml",
        )
