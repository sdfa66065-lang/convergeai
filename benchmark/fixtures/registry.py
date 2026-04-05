from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SemanticChecks:
    must_contain: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)


@dataclass
class FixtureManifest:
    name: str
    description: str
    base_dir: Path
    setup_script: Path
    conflict_files: list[str]
    language: str
    semantic_checks: SemanticChecks
    goose_prompt_control: str
    goose_prompt_experiment: str
    timeout_seconds: int
    tags: list[str] = field(default_factory=list)
    #: If False, skip git unmerged-path check (e.g. clean rebase + logical breakage).
    verify_git_conflicts: bool = True

    @classmethod
    def from_dir(cls, fixture_dir: Path) -> FixtureManifest:
        manifest_path = fixture_dir / "manifest.json"
        data = json.loads(manifest_path.read_text())
        return cls(
            name=data["name"],
            description=data["description"],
            base_dir=fixture_dir,
            setup_script=fixture_dir / "setup.sh",
            conflict_files=data["conflict_files"],
            language=data["language"],
            semantic_checks=SemanticChecks(**data["semantic_checks"]),
            goose_prompt_control=data["goose_prompt_control"],
            goose_prompt_experiment=data["goose_prompt_experiment"],
            timeout_seconds=data.get("timeout_seconds", 300),
            tags=data.get("tags", []),
            verify_git_conflicts=data.get("verify_git_conflicts", True),
        )


class FixtureRegistry:
    @staticmethod
    def discover(fixtures_dir: Path) -> list[FixtureManifest]:
        """Discover all fixture directories containing a manifest.json."""
        fixtures = []
        for subdir in sorted(fixtures_dir.iterdir()):
            if subdir.is_dir() and (subdir / "manifest.json").exists():
                fixtures.append(FixtureManifest.from_dir(subdir))
        return fixtures
