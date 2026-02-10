# Hello World: Single-Run Demo

This walkthrough is a minimal "hello world" flow to show how Phase 0 wiring looks end-to-end. It uses a tiny input config, runs Phase 1 to create a workspace, and then runs Phase 2 against that workspace.

## 1) Create a minimal input config
Save the following JSON as `config/hello_world.json`:

```json
{
  "repository_url": "https://github.com/example/forked-repo.git",
  "base_ref": "main",
  "upstream_remote": "upstream",
  "upstream_url": "https://github.com/example/upstream-repo.git",
  "upstream_ref": "main",
  "binary_conflict_policy": "ours",
  "cherry_picks": [
    "a1b2c3d4e5f6g7h8i9j0"
  ],
  "config_path": "config/overrides.json"
}
```

Notes:
- Replace the repository URLs and commit hashes with real values you control.
- The `config_path` can point to a file you create later for overrides (or omit it if your workflow doesn’t need it).

## 2) Run Phase 1 (create the workspace)

```bash
python3 scripts/phase1.py \
  --config config/hello_world.json \
  --workspace-root ./workspaces \
  --run-id hello-world
```

Expected output artifacts (under `./workspaces/hello-world/`):
- `phase1_output.json`
- `workspace_metadata.json`

## 3) Run Phase 2 (operate on the workspace)

```bash
python3 scripts/phase2.py --workspace ./workspaces/hello-world
```

Expected output artifacts:
- `artifacts/phase2/` (step logs, structured results, or failure replay inputs)

## 4) How Phase 2 uses the “agent”
Phase 2 can run in two modes:

1. **Offline mode (default).** Phase 2 looks for a `patch.diff` file in each step
   directory (for example, `./workspaces/hello-world/artifacts/phase2/compile_step_1/patch.diff`).
   If a patch is present, Phase 2 applies it and continues the loop. If no patch is
   present, the loop fails with a “patch missing” reason.
2. **Online mode (optional).** Provide `--agent-endpoint` to call a real agent over
   HTTP. The agent receives the same JSON payload written to `agent_request.json`
   and can return a JSON response that includes a `patch` string (a unified diff).
   Phase 2 writes that patch to `patch.diff` and continues the loop. For conflict
   hunks, the agent can respond with `resolved_text` (and optional `confidence` or
   `resolution`) to override the default resolution heuristic.

### Example: OpenAI adapter (popular hosted model)
Phase 2 expects a simple HTTP endpoint that accepts the `agent_request.json` payload
and returns either a `patch` (compile/test loops) or `resolved_text` (conflict hunks).
Because the OpenAI API is a hosted model API, you’ll typically run a tiny adapter
service that translates the Phase 2 payload into an OpenAI request and then returns
the expected JSON shape.

This repo includes a working OpenAI-backed adapter at
`scripts/openai_agent_adapter.py`.

Run the adapter locally and point Phase 2 at it:

```bash
pip install fastapi uvicorn openai

export OPENAI_API_KEY=your-key
export OPENAI_MODEL=gpt-4.1-mini
python3 scripts/openai_agent_adapter.py --host 0.0.0.0 --port 8000

python3 scripts/phase2.py \
  --workspace ./workspaces/hello-world \
  --agent-endpoint http://localhost:8000/v1/resolve
```

If you prefer a free/popular hosted model, swap the OpenAI client call for another
provider (for example, OpenRouter or a local inference server) and keep the same
response shape (`resolved_text`/`patch`).

### Example: Mock adapter (local wiring)
If you just need a lightweight endpoint to validate wiring, use the mock adapter
script included in this repo. It resolves conflict hunks by choosing `ours` and
returns an error for compile/test patches (so those steps still require a real
fixer when they fail).

```bash
python3 scripts/mock_agent_adapter.py --port 8001

python3 scripts/phase2.py \
  --workspace ./workspaces/hello-world \
  --agent-endpoint http://localhost:8001/v1/resolve
```

Phase 2 emits structured request/response artifacts for each step to make the
agent interface deterministic. For compile/test steps, look for
`agent_request.json` and `agent_response.json` alongside `patch.diff`. Conflict
steps additionally create per-hunk subdirectories (for example,
`artifacts/phase2/conflict_step_1/hunk_<id>/`) that capture the request payload and
decision summary for each conflict hunk.

## 5) Optional configuration
No additional configuration is required to run the Phase 2 demo. You can optionally
specify a Gradle test task with `--test-task` if you want to run something other than
the default `test` task.

## 6) What this demo proves
- The container can ingest a simple config input.
- Phase 1 can build a workspace with structured outputs.
- Phase 2 can iterate over the workspace and emit deterministic artifacts.

## 7) Optional cleanup

```bash
rm -rf ./workspaces/hello-world
```
