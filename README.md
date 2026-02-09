# ConvergeAI Phase 0

## One-sentence system definition
This system automatically attempts to apply upstream changes to a fork inside a containerized environment using bulk cherry-picks, iterates compile and test runs via modular actions (including integrations with internal services), and produces either a passing result or a replayable failure history.

## Execution Environment Contract
The system runs entirely inside a container to guarantee determinism and reproducibility.

**Base image**
- Eclipse Temurin 17 JDK (Jammy)

**Installed tools**
- Git
- Bash and coreutils

**Contractual guarantees**
- Builds and tests must use repository-provided tooling (for example, `./gradlew`).
- The container does not assume a global Gradle installation.

## Repository input contract
See `config/schema.json` for the formal schema and the example below for a valid input.

```json
{
  "repository_url": "https://github.com/example/forked-repo.git",
  "base_ref": "main",
  "upstream_remote": "upstream",
  "upstream_url": "https://github.com/example/upstream-repo.git",
  "upstream_ref": "main",
  "binary_conflict_policy": "ours",
  "cherry_picks": [
    "a1b2c3d4e5f6g7h8i9j0",
    "deadbeefcafebabe1234"
  ],
  "config_path": "config/overrides.json"
}
```

## Phase 1 runner
Phase 1 creates an isolated workspace, attempts the upstream merge, and emits structured
conflict JSON for Phase 2 consumption.

```bash
python3 scripts/phase1.py \\
  --config path/to/input.json \\
  --workspace-root ./workspaces \\
  --run-id run-20240101
```

Outputs are written into the workspace directory, including `phase1_output.json` and
`workspace_metadata.json`.

## Phase 2 runner
Phase 2 consumes the Phase 1 workspace, attempts automated conflict resolution, runs
compile and test loops, and writes step artifacts into `artifacts/phase2`.

```bash
python3 scripts/phase2.py --workspace ./workspaces/run-20240101
```

## Hello world demo
For a minimal end-to-end walkthrough, see `docs/hello_world.md`.

## Repository layout
- `config/`: JSON schema and default configuration inputs for runs.
- `docs/`: End-to-end walkthroughs and operator notes.
- `prompts/`: Prompt templates used by the automation flow.
- `scripts/`: Phase runners and supporting automation.
- `Dockerfile`: Container specification for the execution environment.

## Quick start
1. Create or copy a valid config JSON (see `config/schema.json` and the example above).
2. Run Phase 1 to prepare the workspace and emit conflict metadata.
3. Run Phase 2 to resolve conflicts and execute compile/test loops.

```bash
python3 scripts/phase1.py --config path/to/input.json --workspace-root ./workspaces --run-id run-20240101
python3 scripts/phase2.py --workspace ./workspaces/run-20240101
```
