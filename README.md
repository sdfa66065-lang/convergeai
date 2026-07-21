# ConvergeAI

**An open framework that organizes fork maintenance — bring your own AI agent.**

ConvergeAI structures the work of keeping a long-lived fork in sync with upstream. Modern coding agents (Claude Code, Goose, Cursor) are already good at reading an upstream PR and inferring *why* the code changed — so ConvergeAI doesn't try to out-think them. Instead, it provides everything the agent can't do on its own: a persistent record of your internal patches and why they're load-bearing, decomposition of an upstream release into resumable rebase units, retrieval of internal context the agent can't see (ticket rationale, constraints), and validation gates on every resolution.

---

## The Problem

Enterprise teams maintaining custom forks of open-source projects face a recurring nightmare: **rebase hell**. Every upstream release brings hundreds of commits that collide with internal customizations. Standard `git rebase` only detects textual conflicts — it silently lets upstream architectural changes overwrite custom business logic, leading to:

- Production outages from silently lost internal patches
- Weeks of manual, error-prone conflict resolution per release cycle
- Developer burnout and mounting technical debt

## The Solution

The division of labor is deliberate: **the agent does the merging; ConvergeAI organizes the work.** Intent analysis is a commoditizing capability — every model generation gets better at it. What doesn't commoditize is the scaffolding around a multi-hundred-commit rebase. ConvergeAI provides five pieces:

1. **Fork state model** *(planned)* — a versioned manifest of internal patches (what, why, owner, load-bearing constraints) plus an upstream sync ledger tracking which commits are processed, pending, or conflicted
2. **Work decomposition** *(planned)* — splits an upstream release into ordered, resumable rebase units with checkpoints, so a 300-commit rebase survives interruption
3. **Agent interface** *(today, evolving)* — hands each conflict to the agent of your choice with the context it can't infer: internal ticket constraints and patch rationale, exposed as MCP tools
4. **Validation gates** *(today: compile/test loop; planned: review queue)* — runs compilers and test suites with self-correction on failure, and routes risky merges to a human-review queue with blast-radius reporting
5. **Eval harness** *(today)* — a benchmark suite of real conflict fixtures with a grading pipeline, used to measure resolution quality across agents

Full architecture, state schemas, and phase-1 specs: [docs/DESIGN.md](docs/DESIGN.md).

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Integration Layer                    │
│      CLI (today) · GitHub Action (planned)           │
├─────────────────────────────────────────────────────┤
│           Fork State & Work Decomposition            │
│   patch manifest · upstream sync ledger · resumable  │
│              rebase units [planned]                  │
├─────────────────────────────────────────────────────┤
│           Fork-State MCP Server (today:              │
│    Context Distiller — fetches upstream PR intent    │
│      & internal constraints for the agent)           │
├─────────────────────────────────────────────────────┤
│         Your Agent (Claude Code · Goose · …)         │
│         (semantic merge + self-correction)           │
├─────────────────────────────────────────────────────┤
│    Validation Gates (compile/test today · review     │
│              queue planned)                          │
├─────────────────────────────────────────────────────┤
│        Blast Radius Analysis (ast-grep) [planned]    │
└─────────────────────────────────────────────────────┘
```

### Key Design Decisions

- **Bring your own agent** — Today we compose [Goose](https://github.com/block/goose) via a CLI wrapper, but the framework's state and context live behind MCP, which every major coding agent speaks. The roadmap's first milestone is proving the same flow end-to-end with Claude Code; the orchestration engine is an adapter, not the product.

- **Framework state over prompt engineering** — The durable value is what the agent *can't* rediscover on each run: which internal patches exist and why, which upstream commits have been processed, where the last rebase session left off. This state is versioned and exposed to the agent as MCP tools.

- **Context retrieval, optional distillation** — The current `distill_context` MCP tool fetches upstream PR metadata from GitHub and internal constraints from Jira. It can optionally distill them with a fast LLM (`claude-haiku-4-5-20251001` by default, configurable via `DISTILL_MODEL`) into structured guidance (`[INTENT]`, `[MANDATORY_CONSTRAINTS]`, `[CONFLICT_GUIDANCE]`, `[RISK_ASSESSMENT]`, `[RECOMMENDED_STRATEGY]`). As agents get better at raw intent analysis, the retrieval stays essential — the agent can't infer context it can't see — while the distillation step becomes optional.

- **AST-first code navigation** *(planned)* — Tree-sitter / `ast-grep` for structural, context-aware search-and-replace. This will handle repository-wide API signature changes without booting a language server on broken mid-rebase code.

---

## How It Works (current flow)

```
   ./converge.sh "<prompt>"
          │
          ▼
   git rebase upstream/main
          │
          ▼
     ┌─ CONFLICT ──┐
     │              │
     ▼              ▼
   distill_context(
     ticket_id, repo,
     pr_number | commit_sha,
     conflicted_files
   )
          │
          ▼
   Structured guidance
   ([INTENT], [MANDATORY_CONSTRAINTS],
    [CONFLICT_GUIDANCE], [RISK_ASSESSMENT],
    [RECOMMENDED_STRATEGY])
          │
          ▼
   Semantic merge
   (AI agent resolves
    conflict using guidance)
          │
          ▼
   Run compiler + tests
          │
     ┌────┴────┐
     │ PASS?   │
     ▼         ▼
   Yes ──→  Continue rebase
   No  ──→  Self-correct & retry (up to N attempts)
```

---

## Quick Start

One-command setup. The script installs Goose (via Homebrew), builds the Python environment, and securely prompts for your API keys.

```bash
git clone https://github.com/sdfa66065-lang/convergeai.git
cd convergeai

# Interactive setup (installs deps, prompts for keys)
chmod +x setup.sh && ./setup.sh

# Resolve your first merge conflict
./converge.sh "There is a merge conflict in main.py. \
The cherrypick commit sha is abc123 in repository owner/repo. \
Please call distill_context and resolve it."
```

`setup.sh` is idempotent — run it again any time and it safely skips steps already completed.

### Manual Configuration (alternative to setup.sh)

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
# Edit .env with your JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN,
# GITHUB_TOKEN, and ANTHROPIC_API_KEY
```

See [`mcp/README.md`](mcp/README.md) for testing the MCP server (MCP Inspector, JSON-RPC, direct Python).

### Try the Demo

The `demo/single_file_blending/test1/` directory contains a pre-built merge conflict (`test_conflict.py`) and recorded Goose session logs showing ConvergeAI resolving it. See [`demo/single_file_blending/test1/commands.md`](demo/single_file_blending/test1/commands.md) for the exact commands used.

Two session exports are provided for comparison:

- **With ConvergeAI MCP** — the agent uses `distill_context` to get structured guidance before resolving
- **Without ConvergeAI** — native Goose resolves the same conflict without external context

See [`demo/exporting_chat_history.md`](demo/exporting_chat_history.md) for how to export your own sessions.

---

## Project Structure

```
convergeai/
├── setup.sh                         # One-command bootstrap (install deps + configure keys)
├── converge.sh                      # CLI wrapper to run the AI Maintainer agent
├── .env.example                     # Environment variable template
├── .gitignore                       # Protects .env secrets from being committed
├── goose/
│   └── ai-maintainer.yaml          # Goose profile for the AI Maintainer agent
├── mcp/
│   ├── README.md                    # MCP server setup, testing, and usage docs
│   └── context_distiller/
│       ├── server.py                # Context Distiller MCP server (stdio)
│       └── requirements.txt         # Python dependencies
├── benchmark/                       # Evaluation framework for merge-conflict fixtures
│   ├── config.py
│   ├── fixtures/
│   └── runner/
├── demo/
│   ├── exporting_chat_history.md    # Guide to exporting Goose session logs
│   └── single_file_blending/test1/  # Working conflict example with session logs
├── README.md
└── LICENSE
```

---

## Roadmap

**Status as of July 2026.** Shipped so far: the Context Distiller MCP server, one-command setup and CLI, a working demo, and a benchmark framework with 10 JS conflict fixtures and a grading pipeline. This roadmap resets the previous (Apr–Sep 2026) plan around a repositioning: agents are already good at intent analysis and getting better, so bespoke distillation is not where the durable value is — the workflow scaffolding around fork maintenance is. Two deliberate cuts from the old plan: the VS Code extension (meet users where agents already run — MCP registry, GitHub Action, CLI — before building UI surfaces) and the Linear integration (deferred until a design partner asks for it).

| Date | Phase | Milestone |
|------|-------|-----------|
| Aug 2026 | Phase 1 — Re-architecture | [Design doc](docs/DESIGN.md) + fork-manifest & sync-ledger formats · Refactor MCP server: context distiller → fork-state server (manifest, ledger, constraints as tools) · Prove end-to-end with Claude Code as the agent on existing fixtures |
| Sep 2026 | Phase 1 — Framework MVP | Work decomposition + resumable rebase sessions + validation gates · Benchmark suite runs the framework with 2+ agents (Claude Code, Goose) · Published comparison results |
| Oct 2026 | Phase 2 — Distribution | v0.1 release + pipx/Homebrew packaging · MCP registry listing · GitHub Action beta (scheduled upstream-sync job that opens resolved PRs) |
| Nov 2026 | Phase 2 — Launch | Show HN backed by benchmark data + one real OSS-fork case study · Fast issue triage · v0.2 from launch feedback |
| Dec 2026 | Phase 3 — Depth & partners | Blast-radius analysis MVP (ast-grep) · GitLab support · 2–3 design partners with real fork pain running pilots · Success metrics instrumented (auto-resolve rate, human-review rate) |
| Jan 2027 | Phase 4 — Decide | 50+ WAU · Paid tier vs. open-core decision driven by pilot data · Roadmap v3 |

---

## Contributing

This project is in active early development. If you're interested in contributing or have ideas for enterprise fork management, open an issue or reach out.

---

## License

MIT
