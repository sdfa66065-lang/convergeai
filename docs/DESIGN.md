# ConvergeAI Framework Design

**Status:** Draft v2 · July 2026
**Scope:** Complete framework architecture — every component through the Jan 2027 roadmap horizon is designed here. Phase 1 components (fork state model, fork-state MCP server) are frozen-schema, implementation-ready; later components are designed to the level needed to start their phase without a new doc, and may gain addenda as implementation teaches us things. Section §13 maps every component to its roadmap phase.

---

## 1. Overview

### 1.1 The division of labor

ConvergeAI is a framework that organizes fork-maintenance work. It does not merge code — the user's coding agent (Claude Code, Goose, Cursor, …) does. This split is deliberate:

- **What agents are good at (and getting better at):** reading an upstream PR and inferring architectural intent, writing the blended resolution, iterating on compile/test failures. This capability is commoditizing with every model generation. Building proprietary layers here is building on melting ice.
- **What agents cannot do on their own:** know *which* internal patches exist and why they're load-bearing, see internal ticket rationale, remember which of 300 upstream commits have already been processed, or resume a rebase that died at commit 147. This is durable framework territory.

ConvergeAI owns the second list.

### 1.2 Goals

1. **Persistent fork state** — a versioned record of internal patches (and why they exist) plus a ledger of upstream sync progress.
2. **Organized work** — decompose an upstream release into ordered, resumable rebase units instead of one monolithic rebase.
3. **Agent-agnostic context delivery** — expose fork state and upstream/internal context to any MCP-speaking agent.
4. **Trust boundaries** — every agent resolution passes validation gates; risky resolutions route to humans.
5. **Measurability** — every design claim is testable in the existing benchmark harness.

### 1.3 Non-goals

- Writing merge resolutions ourselves (no bespoke merge engine, no in-house resolution model).
- Replacing git. All state is git-native; a user can abandon ConvergeAI mid-rebase and finish with plain git.
- A UI. Integration surfaces are CLI, MCP, and (planned) a GitHub Action.

### 1.4 Design principles

- **Persist what the agent can't rediscover.** If an agent could infer it from the repo in one run, don't store it. If losing it costs a human hours to reconstruct (patch rationale, sync progress), store it.
- **Git-native, PR-reviewable state.** Fork state lives in versioned YAML inside the fork. Changes to the manifest are reviewed like code. Ephemeral session state stays out of git.
- **Bring your own agent.** Anything the framework tells an agent goes through MCP tools or the prompt contract — never through engine-specific APIs. Goose is an adapter, not a dependency.
- **Retrieval over distillation.** Fetching invisible context is essential; LLM-summarizing it is an optimization that agents need less each year. Distillation stays available but optional.

---

## 2. Concepts

| Term | Meaning |
|------|---------|
| **Fork** | The internal repository carrying customizations on top of an upstream project. |
| **Upstream** | The open-source project being tracked (`upstream` remote). |
| **Internal patch** | A logical unit of fork customization — one *reason* the fork differs (may span many commits/files). |
| **Constraint** | A MUST / MUST NOT rule an internal patch imposes on any future merge. |
| **Sync run** | One campaign of integrating a range of upstream commits (e.g. "rebase onto v2.9"). |
| **Rebase unit** | An ordered group of upstream commits processed and validated together; the checkpoint granularity. |
| **Session** | The resumable execution state of an in-progress sync run on one machine. |

---

## 3. Fork state model (Phase 1 — implementation-ready)

All durable state lives in `.convergeai/` at the fork root, committed to the fork. Ephemeral state lives under `.git/convergeai/`, never committed.

```
fork-repo/
├── .convergeai/
│   ├── manifest.yaml      # internal patches + constraints (committed, PR-reviewed)
│   └── ledger.yaml        # upstream sync progress (committed)
└── .git/convergeai/
    └── sessions/<id>.json # resumable session checkpoints (ephemeral)
```

### 3.1 Patch manifest — `.convergeai/manifest.yaml`

The manifest answers the question every conflict resolution starts with: *what customizations exist in this area, and what rules do they impose?*

```yaml
schema_version: 1
fork:
  upstream_remote: upstream
  upstream_branch: main
patches:
  - id: sso-enforcement
    title: Enforce SAML SSO on all auth entry points
    rationale: >
      Compliance requirement SOC2-CC6.1: password auth is disabled for
      enterprise tenants. Upstream keeps adding new auth entry points;
      each one must route through our SSO middleware.
    owner: platform-security
    tickets: [SEC-4411, SEC-5102]
    load_bearing: true
    status: active            # active | retired | upstreamed
    touches:
      files:
        - src/auth/**
        - src/api/session.py
      symbols:
        - AuthRouter.login
        - create_session
    constraints:
      - rule: MUST
        text: All new auth entry points route through SSOMiddleware.
      - rule: MUST_NOT
        text: Re-enable password or magic-link auth paths for tenant accounts.

  - id: telemetry-strip
    title: Remove phone-home telemetry
    rationale: Legal requirement — no runtime data leaves customer VPCs (LEGAL-201).
    owner: platform-infra
    tickets: [LEGAL-201]
    load_bearing: true
    status: active
    touches:
      files: [src/telemetry/**]
    constraints:
      - rule: MUST_NOT
        text: Reintroduce any outbound telemetry call, including upstream's new endpoints.
```

Design notes:

- **`constraints` mirror the `[MANDATORY_CONSTRAINTS]` semantic anchor** already used by the Context Distiller prompt ([mcp/context_distiller/server.py](../mcp/context_distiller/server.py)), so existing agent behavior transfers unchanged — the constraints now come from durable reviewed state instead of a per-run LLM summary.
- **`touches.files` are glob patterns** matched against conflicted paths to select relevant patches; `symbols` are advisory hints for the agent, not used for matching in v1.
- **`status: upstreamed`** records patches that landed upstream — the ledger uses this to auto-drop them from future syncs.
- The schema deliberately echoes the existing benchmark `FixtureManifest` pattern ([benchmark/fixtures/registry.py](../benchmark/fixtures/registry.py)): a small dataclass loader, `from_dir`-style discovery, versioned with the code it describes.

### 3.2 Sync ledger — `.convergeai/ledger.yaml`

The ledger answers: *where are we relative to upstream, and what happened to each commit we've processed?*

```yaml
schema_version: 1
upstream_branch: main
last_synced_sha: 8f3a2e1c9b
sync_runs:
  - id: 2026-08-v2.9
    started: 2026-08-04
    target_sha: 4d77bca210
    status: in_progress       # in_progress | completed | abandoned
    commits:
      - sha: 9c01f4aa32
        status: processed     # pending | processed | conflicted | skipped
        strategy: ACCEPT_UPSTREAM
      - sha: b8e2d90c11
        status: processed
        strategy: BLEND
        patches: [sso-enforcement]
        resolution_commit: 77ac03d9ef
        notes: Upstream added OAuth device flow; routed through SSOMiddleware.
      - sha: 4d77bca210
        status: conflicted
        strategy: MANUAL_REVIEW
        patches: [telemetry-strip]
        session: 2026-08-05-a41f
```

Design notes:

- **`strategy` values reuse the existing distiller vocabulary** (`BLEND | ACCEPT_UPSTREAM | KEEP_OURS | MANUAL_REVIEW`), so the same enum flows from guidance → resolution → ledger.
- The ledger is append-mostly and committed at rebase-unit boundaries, giving reviewers a diffable audit trail of every sync run in the PR itself.
- Scale escape hatch: if per-commit entries grow unwieldy (thousands of commits per run), v2 may collapse `processed` runs to summaries and move detail to an ignored local store. Not needed for v1.

### 3.3 Session checkpoints — `.git/convergeai/sessions/<id>.json`

Ephemeral, machine-local, never committed (`.git/` contents are ignored by git automatically). Holds what's needed to resume: current rebase unit, per-commit attempt counts, last validation results, agent adapter in use. Losing a session file loses convenience, not correctness — the ledger plus git reflog is always enough to recover.

### 3.4 Bootstrap — `convergeai init`

A fork adopting the framework runs `convergeai init`, which diffs the fork against upstream, clusters the differences into candidate patches, and drafts `manifest.yaml` — using the configured agent to propose `rationale` text from commit messages and linked tickets. The human then edits and lands the manifest through normal PR review. This is the payoff of in-repo YAML: the fork's tribal knowledge gets captured once, reviewed by the people who hold it, and versioned forever after.

### 3.5 Alternatives considered

- **SQLite (`.convergeai.db`)** — better querying at scale, but opaque to `git diff` and PR review, and requires export tooling before an agent can read it. Rejected: reviewability *is* the product here.
- **Hybrid (YAML manifest + SQLite ledger)** — deferred until a real ledger outgrows YAML (see §3.2 escape hatch).

---

## 4. Fork-state MCP server (Phase 1 — implementation-ready)

An evolution of the existing Context Distiller ([mcp/context_distiller/server.py](../mcp/context_distiller/server.py)), not a rewrite. The stdio server scaffolding, GitHub/Jira clients (`fetch_pull_request`, `fetch_commit`, `fetch_jira_ticket`), and dataclasses carry over. The module moves to `mcp/fork_state/` with `context_distiller` kept as a deprecated alias for one release.

### 4.1 Tool surface

| Tool | Kind | Description |
|------|------|-------------|
| `get_internal_context(conflicted_files, ticket_ids?)` | pure retrieval | Match conflicted paths against `manifest.yaml` `touches.files` globs; return the relevant patches — rationale, constraints, owner, tickets — formatted under the existing `[MANDATORY_CONSTRAINTS]` anchor. Optional `ticket_ids` adds explicit Jira tickets to the result (and is the sole constraint source in manifest-less fallback, §4.3). No LLM call. |
| `fetch_upstream_context(repo, pr_number \| commit_sha)` | pure retrieval | Raw PR / commit / linked-ticket metadata via the existing GitHub/Jira clients. No LLM call; the agent does its own intent analysis. |
| `get_sync_status()` | ledger read | Current sync run, last synced SHA, pending/conflicted commit counts, active session if any. |
| `record_resolution(sha, strategy, patches, notes)` | ledger write | Append the outcome of a resolution to `ledger.yaml`. The framework CLI also calls this; exposing it as a tool lets the agent self-report in supervised flows. |
| `distill_context(...)` | optional LLM | Unchanged from today (Haiku-backed synthesis with semantic anchors). Kept for backward compatibility and for weaker agents; expected to become opt-in. |

### 4.2 Why this decomposition

Today's `distill_context` bundles three things: retrieval of upstream metadata, retrieval of internal constraints, and LLM synthesis. The refactor splits them so each degrades independently: a frontier agent calls the two retrieval tools and reasons directly over raw context; a weaker agent (or a token-constrained run) still gets the distilled version. The benchmark harness will measure whether distillation still pays for itself per agent (§8).

### 4.3 Compatibility

- `distill_context` keeps its exact input schema and output format — existing Goose profiles and demo sessions keep working.
- New tools fail soft when no `.convergeai/` directory exists: `get_internal_context` falls back to fetching the caller-supplied `ticket_ids` from Jira (the same explicit-key path the current `distill_context` uses — there is no manifest to infer tickets from), and returns an empty constraints block with a "no manifest found" notice when no `ticket_ids` are given either. The server thus remains useful on forks that haven't adopted the manifest yet, without silently dropping internal constraints.

---

## 5. Work decomposition (Sep)

Input: the upstream commit range for a sync run (`last_synced_sha..target_sha`). Output: an ordered list of rebase units written to the session file before any resolution starts, so the whole plan is inspectable via `converge plan` before execution.

### 5.1 Algorithm

1. **Annotate** — for each upstream commit, list touched paths (`git diff-tree`); match paths against manifest `touches.files` globs and attach patch ids.
2. **Group by upstream PR** — commits that landed in one upstream PR (via `fetch_upstream_context` merge-commit lookup, falling back to `(#\d+)` message parsing) stay in one unit; a PR is upstream's own statement that these commits are one logical change.
3. **Cluster** — union-find on touched paths merges PR-groups that overlap on files, subject to a unit size budget (default 15 commits; configurable). Oversized clusters split at PR boundaries, never inside one.
4. **Order** — units execute in upstream commit order (correctness requires it — later commits may depend on earlier ones); within the plan, units touching no manifest paths are flagged `low-risk` so status output shows early signal, but they are not reordered.

### 5.2 Checkpointing and resume

- After each unit passes validation gates: resolutions are committed, `ledger.yaml` is updated and committed, and the session file snapshots position. An interruption loses at most one unit of work.
- `converge resume` continues from the last checkpoint; with the session file missing, position is reconstructed from the ledger (last `processed` sha) plus `git status`. The session file is convenience, never the source of truth.
- A unit that exhausts its attempt budget is marked `conflicted` in the ledger; the run continues with the next unit unless the failed unit's files overlap a later unit (then the run pauses for review, since continuing would compound a bad base).

## 6. Agent interface (Phase 1 proof: Aug · full adapters: Sep)

### 6.1 Prompt contract

The framework injects, per unit, an engine-neutral prompt assembled from a template:

```
You are resolving merge conflicts for a maintained fork.

[CONFLICT_INVENTORY]
Applying upstream {sha} ({upstream_repo}). Conflicted files: {files}

[MANDATORY_CONSTRAINTS]
{output of get_internal_context(files)}

[UPSTREAM_CONTEXT]
Call fetch_upstream_context(repo="{upstream_repo}", commit_sha="{sha}")
if you need the upstream rationale; you may also inspect the diff directly.

[VALIDATION]
Your resolution must pass: {gate_commands}
You have {attempts_remaining} attempts. On failure you will receive the
gate output and should revise.

[REPORTING]
When done, call record_resolution(sha, strategy, patches, notes).
```

The agent owns intent analysis, resolution, and iteration. Nothing in the contract is engine-specific; the anchors reuse the vocabulary agents already see from `distill_context`.

### 6.2 Adapter contract

An adapter is a small shim responsible for exactly four things: (1) register the fork-state MCP server with the engine, (2) submit the prompt, (3) surface the engine's transcript to the session log, (4) map engine exit to `resolved | failed | timeout`. Adapters live in `adapters/<engine>/` and are selected by `--agent` or `CONVERGEAI_AGENT`.

- **Goose (today):** [converge.sh](../converge.sh) + [goose/ai-maintainer.yaml](../goose/ai-maintainer.yaml), refactored into `adapters/goose/` with unchanged behavior.
- **Claude Code (Phase 1 proof):** headless `claude -p "<prompt>" --mcp-config adapters/claude-code/mcp.json --permission-mode acceptEdits`, working directory = the rebase checkout. The **Phase 1 exit test** is Claude Code resolving an existing benchmark fixture end-to-end using `get_internal_context` (manifest-backed) instead of `distill_context`.
- **Cursor / others:** same shape — register MCP server, pass prompt. Added when demand appears; the contract is the spec.

## 7. Validation gates (Sep)

A gate pipeline runs after each unit's resolution, configured in `.convergeai/gates.yaml` (defaults shown):

```yaml
schema_version: 1
attempt_budget: 3
gates:
  - name: syntax        # built-in: no conflict markers; parse/compile check per language
  - name: constraints   # built-in: mechanical checks derived from manifest constraints
  - name: tests
    command: npm test   # fork-defined; any command, non-zero exit = fail
    timeout_seconds: 600
```

1. **Syntax gate** — no conflict markers anywhere; parse/compile passes (per-language check, reusing the benchmark grader's syntax gate — [benchmark/grader/syntax_gate.py](../benchmark/grader/syntax_gate.py)).
2. **Constraint gate** — mechanically checkable manifest constraints, compiled at plan time: `MUST_NOT` rules with a `pattern:` field become must-not-match greps/ast-grep queries over resolved files; constraints without patterns are prompt-only. (Manifest schema addition: optional `pattern` per constraint.)
3. **Test gate** — the fork's own command (benchmark fixtures: the behavioral gate — [benchmark/grader/behavioral_gate.py](../benchmark/grader/behavioral_gate.py)).

Failure output feeds back to the agent verbatim, up to `attempt_budget`. Exhausted budgets or agent-chosen `MANUAL_REVIEW` land in the review flow: ledger entry `conflicted`, a generated summary (what was attempted, which gate failed, relevant constraints) posted as a comment on the sync PR. Richer queue tooling waits for design-partner feedback (Dec).

## 8. Eval harness (existing, extended — Sep)

The benchmark's control/experiment track machinery ([benchmark/runner/orchestrator.py](../benchmark/runner/orchestrator.py)) generalizes from two tracks to a matrix:

- **Agent axis:** Goose, Claude Code (others as adapters land)
- **Context-mode axis:** `none` (agent alone — today's control), `raw` (retrieval tools only), `distilled` (today's experiment), `manifest` (manifest-backed `get_internal_context`)

Mechanics: `Track` ([benchmark/runner/track.py](../benchmark/runner/track.py)) becomes a `(agent, context_mode)` pair; fixtures gain an optional `.convergeai/` directory (manifest + ledger seeded by `setup.sh`) so manifest-backed cells are testable; per-fixture prompts stay in the fixture manifest as today. The published artifact is a pass-rate table over `runs=N` repetitions per cell (reusing `BenchmarkOrchestrator.run_all(runs=N)`), with per-fixture gate breakdowns and session transcripts linked. This matrix is both the launch credibility artifact and the ongoing regression suite for every design claim in this doc — including the empirical answer to "when does distillation still pay?" (§12).

---

## 9. CLI specification (Sep–Oct)

One binary, `converge`, installed by pipx/Homebrew (Oct). Today's [converge.sh](../converge.sh) becomes a thin legacy entry point delegating to `converge run`.

| Command | Does |
|---------|------|
| `convergeai init [--refresh]` | Diff fork vs. upstream, cluster differences, draft (or propose updates to) `manifest.yaml` with agent assistance; human lands it via PR (§3.4). |
| `converge plan [<range>]` | Decompose `last_synced_sha..<range or upstream HEAD>` into rebase units (§5), write the session plan, print it. No execution. |
| `converge run [--units N] [--dry-run]` | Execute the plan: per unit, invoke the agent adapter, run gates, checkpoint. `--units` bounds work per invocation (the Action's time-budget lever); `--dry-run` prints prompts without invoking the agent. |
| `converge resume [<session-id>]` | Continue from the last checkpoint; reconstructs position from the ledger if the session file is gone (§5.2). |
| `converge status` | Ledger + session summary: current run, processed/pending/conflicted counts, last synced SHA. |
| `converge review` | List `conflicted` entries with their generated summaries; `--open` jumps to the sync PR comment. |

Global: `--agent goose\|claude-code` (or `CONVERGEAI_AGENT`) selects the adapter (§6.2); `--repo-root` defaults to cwd; `--ticket <id>` (repeatable) forwards Jira ticket keys into `get_internal_context` — the constraint source for manifest-less forks (§4.3). Exit codes: `0` all units clean, `1` completed with `conflicted` entries remaining, `2` framework error. Everything the CLI knows it reads from `.convergeai/` + `.git/convergeai/` — no hidden state, so the Action (§10) and a laptop can hand a sync run back and forth through git alone.

## 10. GitHub Action (Oct)

A published action (`convergeai/sync-action`) wrapping the CLI for unattended, incremental syncs.

- **Triggers:** `schedule` (e.g. nightly) and `workflow_dispatch` (manual, with optional target ref input).
- **Flow per run:** checkout fork → fetch upstream → `converge plan` → `converge run --units <budget>` sized to the job time budget → commit resolutions + ledger to the sync branch → open or update **one sync PR per sync run** (`convergeai/sync-<run-id>` branch). The PR body carries `converge status` output; review summaries for conflicted units are posted as PR comments; the committed ledger diff is the audit trail.
- **Incremental by construction:** each scheduled run resumes from the ledger committed on the sync branch (§5.2 — the ledger, not the session file, is the source of truth), so a large upstream release completes across as many nightly runs as it needs.
- **Permissions:** `contents: write`, `pull-requests: write`. **Secrets:** repo/org secrets with the same names as `.env.example` (`ANTHROPIC_API_KEY`; `JIRA_*` optional — tools fail soft without them, §4.3).
- **Guardrails:** the Action never merges the sync PR — a human does; job timeout mid-unit is safe (§12); concurrency group prevents overlapping runs on the same sync branch.
- Marketplace packaging is deferred until after the Nov launch; until then, users reference the action by repo path.

## 11. Blast-radius analysis (Dec)

The answer to conflicts git never reports: upstream changes an API signature cleanly, but fork-only call sites — files upstream doesn't know exist — silently break. AST-based (`ast-grep` / tree-sitter) because mid-rebase code doesn't compile, so a language server can't boot; structural matching works on broken trees. Language scope v1: JS/TS + Python (matching the benchmark fixtures).

Two integration points:

1. **Pre-resolution context:** at plan time, diff each unit's upstream changes for exported-symbol signature changes (function/method arity, name, parameter renames); query the fork for call sites of changed symbols *outside* the unit's conflicted files; attach the call-site report to the unit's prompt under a `[BLAST_RADIUS]` anchor so the agent fixes callers in the same unit.
2. **Post-resolution warning gate:** after gates pass, re-run the call-site query; a changed signature with untouched call sites raises a **warning** (not a failure, in v1 — dynamic-dispatch false positives are expected, §12) that lands in the review summary and PR comment.

Signature extraction and call-site queries are per-language rule packs in `blast_radius/rules/<lang>/` — the extension point for community language support.

---

## 12. Failure modes & open questions

- **Manifest drift** — patches evolve but nobody updates YAML. Mitigations: `convergeai init --refresh` re-diff proposing manifest updates; constraint-gate failures referencing retired patches flag staleness. Open: should CI warn when a commit touches manifest-matched paths without a manifest change?
- **Upstream force-pushes / history rewrites** — ledger SHAs go stale. v1 detects (SHA no longer reachable) and requires a new sync run; smarter remapping is out of scope.
- **Secrets** — unchanged from today: `.env` at repo root, never in fork state. Manifest/ledger must never contain tokens; `record_resolution` sanitizes notes.
- **When does distillation still pay?** — empirical, per-agent; answered by the §8 matrix rather than by assumption.
- **Action job timeout mid-unit** — safe by design: checkpoints are per-unit (§5.2), so a killed job loses at most the in-flight unit, and the next scheduled run resumes from the committed ledger.
- **Blast-radius false positives** — dynamic dispatch, reflection, and string-based imports evade AST call-site queries; this is why §11's post-resolution check warns rather than fails in v1.
- **Monorepo forks with multiple upstreams** — out of scope for v1 (`schema_version` gives us room).

## 13. Phase map & exit criteria

Every component's home phase (mirrors the [README roadmap](../README.md#roadmap)):

| Doc section | Component | Roadmap phase |
|-------------|-----------|---------------|
| §3 | Fork state model (schemas frozen) | Aug 2026 — Phase 1 |
| §4 | Fork-state MCP server | Aug 2026 — Phase 1 |
| §6.2 | Claude Code adapter proof | Aug 2026 — Phase 1 |
| §5 | Work decomposition | Sep 2026 — Phase 1 |
| §7 | Validation gates | Sep 2026 — Phase 1 |
| §8 | Eval matrix, published | Sep 2026 — Phase 1 |
| §9 | CLI + packaging | Sep–Oct 2026 — Phase 2 |
| §10 | GitHub Action | Oct 2026 — Phase 2 |
| §11 | Blast-radius analysis | Dec 2026 — Phase 3 |

### Phase 1 exit criteria (Aug 2026)

1. `manifest.yaml` and `ledger.yaml` schemas frozen at `schema_version: 1` (this doc §3).
2. Fork-state MCP server exposes `get_internal_context`, `fetch_upstream_context`, `get_sync_status`, `record_resolution`; `distill_context` unchanged and passing existing demo flows.
3. One benchmark fixture resolved end-to-end by **Claude Code** using manifest-backed context, gates passing.
4. Benchmark harness can run that flow repeatably (foundation for the Sep matrix).
