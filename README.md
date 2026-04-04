# ConvergeAI

**An autonomous AI engine that eliminates rebase hell for enterprise fork maintainers.**

ConvergeAI is a semantic fork-sync engine that uses AI coding agents to resolve merge conflicts between upstream open-source projects and internal enterprise forks. Instead of brute-force textual merging, it understands *why* code changed upstream and *what* business rules the fork must preserve — then synthesizes a resolution that satisfies both.

---

## The Problem

Enterprise teams maintaining custom forks of open-source projects face a recurring nightmare: **rebase hell**. Every upstream release brings hundreds of commits that collide with internal customizations. Standard `git rebase` only detects textual conflicts — it silently lets upstream architectural changes overwrite custom business logic, leading to:

- Production outages from silently lost internal patches
- Weeks of manual, error-prone conflict resolution per release cycle
- Developer burnout and mounting technical debt

## The Solution

ConvergeAI acts as an autonomous maintainer that:

1. **Understands both sides** — fetches upstream PR intent *and* internal ticket constraints
2. **Resolves semantically** — blends new upstream architecture with required business rules
3. **Validates automatically** — runs compilers and test suites, self-correcting on failure
4. **Handles blast radius** — traces API signature changes across the entire codebase

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   CLI Orchestrator                   │
│              (composes Goose as engine)              │
├─────────────────────────────────────────────────────┤
│            Context Distiller MCP Server              │
│     (single distill_context tool — fetches both     │
│      upstream PR intent & internal constraints,      │
│      then LLM-distills into structured guidance)     │
├─────────────────────────────────────────────────────┤
│               Conflict Resolution Agent             │
│         (semantic merge + self-correction)           │
├─────────────────────────────────────────────────────┤
│            Validation Loop (compile/test)            │
├─────────────────────────────────────────────────────┤
│          Blast Radius Analysis (ast-grep)            │
└─────────────────────────────────────────────────────┘
```

### Key Design Decisions

- **Goose as the engine** — We compose [Goose](https://github.com/block/goose) via a CLI wrapper rather than forking it, leveraging its native `bash` and file-editing tools while avoiding maintenance nightmares.

- **Context Distiller MCP (LLM-in-the-Middle)** — A single `distill_context` MCP tool fetches upstream PR metadata from GitHub and internal constraints from Jira, then uses a fast LLM (`claude-haiku-4-5-20251001` by default, configurable via `DISTILL_MODEL`) to produce structured plaintext guidance with semantic anchors (`[INTENT]`, `[MANDATORY_CONSTRAINTS]`, `[CONFLICT_GUIDANCE]`, `[RISK_ASSESSMENT]`, `[RECOMMENDED_STRATEGY]`). This prevents token exhaustion and hallucinations by feeding the agent only what it needs.

- **AST-first code navigation** — Tree-sitter / `ast-grep` for structural, context-aware search-and-replace. This handles repository-wide API signature changes without booting a language server on broken mid-rebase code.

---

## How It Works

```
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

- [x] Phase 0 — Single-file context distiller workflow
- [x] Phase 1 — Unified `distill_context` MCP tool (Jira + GitHub + LLM distillation)
- [x] Phase 2 ([Supported by Goose](https://block.github.io/goose/docs/guides/recipes/session-recipes/)) — Validation loop (compile/test + self-correction)
- [ ] Phase 3 — Blast radius analysis with `ast-grep`
- [ ] Phase 4 — LSP-based pre-flight dependency mapping
- [ ] Enterprise integrations (Jira, Linear, GitHub Enterprise)

---

## Contributing

This project is in active early development. If you're interested in contributing or have ideas for enterprise fork management, open an issue or reach out.

---

## License

MIT
