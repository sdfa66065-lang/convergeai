# ConvergeAI Framework Design

**Status:** Draft v1 · July 2026
**Scope:** Full framework architecture. Phase 1 components (fork state model, fork-state MCP server) are specified in implementation-ready detail; later components are sketched and will be refined in follow-up docs as they enter their roadmap phase.

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
| `get_internal_context(conflicted_files)` | pure retrieval | Match conflicted paths against `manifest.yaml` `touches.files` globs; return the relevant patches — rationale, constraints, owner, tickets — formatted under the existing `[MANDATORY_CONSTRAINTS]` anchor. No LLM call. |
| `fetch_upstream_context(repo, pr_number \| commit_sha)` | pure retrieval | Raw PR / commit / linked-ticket metadata via the existing GitHub/Jira clients. No LLM call; the agent does its own intent analysis. |
| `get_sync_status()` | ledger read | Current sync run, last synced SHA, pending/conflicted commit counts, active session if any. |
| `record_resolution(sha, strategy, patches, notes)` | ledger write | Append the outcome of a resolution to `ledger.yaml`. The framework CLI also calls this; exposing it as a tool lets the agent self-report in supervised flows. |
| `distill_context(...)` | optional LLM | Unchanged from today (Haiku-backed synthesis with semantic anchors). Kept for backward compatibility and for weaker agents; expected to become opt-in. |

### 4.2 Why this decomposition

Today's `distill_context` bundles three things: retrieval of upstream metadata, retrieval of internal constraints, and LLM synthesis. The refactor splits them so each degrades independently: a frontier agent calls the two retrieval tools and reasons directly over raw context; a weaker agent (or a token-constrained run) still gets the distilled version. The benchmark harness will measure whether distillation still pays for itself per agent (§8).

### 4.3 Compatibility

- `distill_context` keeps its exact input schema and output format — existing Goose profiles and demo sessions keep working.
- New tools fail soft when no `.convergeai/` directory exists (`get_internal_context` falls back to Jira-only retrieval), so the server remains useful on forks that haven't adopted the manifest yet.

---

## 5. Work decomposition (sketch — Phase 1/Sep)

Input: the upstream commit range for a sync run. Output: an ordered list of rebase units.

- **Clustering:** group commits by file-overlap (union-find on touched paths), keeping each unit under a size budget. Commits touching manifest-matched paths get their patch ids attached up front.
- **Ordering:** topological by commit order within upstream; units that touch no manifest paths are scheduled first (cheap wins, early validation signal).
- **Checkpointing:** after each unit passes validation gates, the framework commits the resolutions, updates the ledger, and snapshots the session. Interrupting at any point loses at most one unit of work.
- **Resume:** `converge resume <session-id>` replays from the last checkpoint using the session file; if the session file is missing, it reconstructs position from the ledger.

Open question for the Sep design pass: whether clustering should also consult upstream PR groupings (commits from one PR stay in one unit) — likely yes, using `fetch_upstream_context`.

## 6. Agent interface (sketch + Phase 1 proof)

### 6.1 Prompt contract

The framework injects, per conflict:

1. The conflict inventory (files, markers present, upstream SHA being applied)
2. `get_internal_context` output — patches + constraints (the invisible half)
3. A pointer to `fetch_upstream_context` for the visible half (the agent decides whether to call it)
4. The validation command(s) the resolution must pass and the attempt budget

The agent owns everything else: intent analysis, resolution, and iteration on failures. The contract is engine-neutral text + MCP tools; no engine-specific instructions.

### 6.2 Adapters

- **Goose (today):** [converge.sh](../converge.sh) + [goose/ai-maintainer.yaml](../goose/ai-maintainer.yaml), unchanged in behavior.
- **Claude Code (Phase 1 proof):** headless invocation (`claude -p`) with the fork-state server registered via MCP config. The **Phase 1 exit test** is Claude Code resolving an existing benchmark fixture end-to-end using `get_internal_context` (manifest-backed) instead of `distill_context`.
- Cursor and others follow the same shape: register the MCP server, pass the prompt contract.

## 7. Validation gates (sketch — Sep)

Reuses the gate concepts already built in the benchmark grader ([benchmark/grader/](../benchmark/grader/)):

1. **Syntax gate** — no conflict markers, parse/compile passes
2. **Behavioral gate** — the fork's test suite (or fixture tests) passes
3. **Constraint gate** *(new)* — `must_not_contain`-style checks generated from manifest constraints where they're mechanically checkable

Failures feed back to the agent with the gate output, up to the attempt budget; exhausted budgets or `MANUAL_REVIEW` strategies land in the review queue (v1: a `conflicted` ledger entry + generated summary comment on the sync PR; richer queue tooling later).

## 8. Eval harness (existing, extended — Sep)

The benchmark's control/experiment track machinery ([benchmark/runner/orchestrator.py](../benchmark/runner/orchestrator.py)) generalizes to a matrix: **agent (Goose, Claude Code, …) × context mode (none, raw retrieval, distilled, manifest-backed)**. Fixture manifests gain optional `.convergeai/` state so manifest-backed runs are testable. The Sep milestone publishes this matrix — it is both the launch credibility artifact and the ongoing regression suite for every design claim in this doc.

---

## 9. Failure modes & open questions

- **Manifest drift** — patches evolve but nobody updates YAML. Mitigations: `convergeai init --refresh` re-diff proposing manifest updates; constraint-gate failures referencing retired patches flag staleness. Open: should CI warn when a commit touches manifest-matched paths without a manifest change?
- **Upstream force-pushes / history rewrites** — ledger SHAs go stale. v1 detects (SHA no longer reachable) and requires a new sync run; smarter remapping is out of scope.
- **Secrets** — unchanged from today: `.env` at repo root, never in fork state. Manifest/ledger must never contain tokens; `record_resolution` sanitizes notes.
- **When does distillation still pay?** — empirical, per-agent; answered by the §8 matrix rather than by assumption.
- **Monorepo forks with multiple upstreams** — out of scope for v1 (`schema_version` gives us room).

## 10. Phase 1 exit criteria (Aug 2026)

1. `manifest.yaml` and `ledger.yaml` schemas frozen at `schema_version: 1` (this doc §3).
2. Fork-state MCP server exposes `get_internal_context`, `fetch_upstream_context`, `get_sync_status`, `record_resolution`; `distill_context` unchanged and passing existing demo flows.
3. One benchmark fixture resolved end-to-end by **Claude Code** using manifest-backed context, gates passing.
4. Benchmark harness can run that flow repeatably (foundation for the Sep matrix).
