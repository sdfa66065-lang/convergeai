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
├─────────────┬───────────────────────┬───────────────┤
│  Upstream   │   Context Distiller   │   Internal    │
│  Intent     │       MCP Server      │   Constraint  │
│  (PR/commit │   (LLM-in-the-middle) │   (ticket     │
│   analysis) │                       │    lookup)    │
├─────────────┴───────────────────────┴───────────────┤
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

- **Context Distiller MCP (LLM-in-the-Middle)** — An MCP server intercepts context requests and uses a fast LLM to produce strict, bulleted business constraints (e.g., *"Must use PostgreSQL, no Redis"*). This prevents token exhaustion and hallucinations by feeding the agent only what it needs.

- **Dual Distillation** — For each conflict, the engine fetches both:
  - **Upstream Intent** — What the open-source PR/commit was trying to achieve
  - **Internal Constraint** — What business rules from local tickets (e.g., `PROJ-101`) must be preserved

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
Fetch upstream   Fetch internal
PR intent        ticket constraints
   │              │
   └──────┬───────┘
          ▼
   Semantic merge
   (AI agent resolves
    conflict with full
    context of both sides)
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

### Prerequisites

- Python 3.10+
- Git
- Docker (for containerized runs)

### Installation

```bash
git clone https://github.com/sdfa66065-lang/convergeai.git
cd convergeai
python3 -m venv .venv
source .venv/bin/activate
pip install -r demo/requirements.txt
```

### Run the Demo

```bash
# Phase 1: Set up workspace, attempt merge, emit conflict metadata
python3 demo/scripts/phase1.py \
  --config demo/config/hello_world.json \
  --workspace-root ./workspaces \
  --run-id demo-run

# Phase 2: AI-powered conflict resolution + validation loop
python3 demo/scripts/phase2.py --workspace ./workspaces/demo-run

# Inspect results
ls ./workspaces/demo-run/artifacts/phase2/
```

See [`demo/docs/hello_world.md`](demo/docs/hello_world.md) for a full walkthrough and [`demo/docs/demo_walkthrough.md`](demo/docs/demo_walkthrough.md) for a local conflict simulation.

---

## Project Structure

```
convergeai/
├── demo/
│   ├── config/          # JSON schema and run configurations
│   ├── docs/            # Walkthroughs and operator guides
│   ├── prompts/         # Prompt templates for the AI agent
│   ├── scripts/         # Phase runners and automation
│   ├── Dockerfile       # Containerized execution environment
│   └── requirements.txt
└── README.md
```

---

## Roadmap

- [x] Phase 0 — Single-file context distiller workflow
- [ ] Phase 1 — Multi-file orchestration
- [x] Phase 2(Delegated to Goose) — Validation loop (compile/test + self-correction) 
- [ ] Phase 3 — Blast radius analysis with `ast-grep`
- [ ] Phase 4 — LSP-based pre-flight dependency mapping
- [ ] Enterprise integrations (Jira, Linear, GitHub Enterprise)

---

## Contributing

This project is in active early development. If you're interested in contributing or have ideas for enterprise fork management, open an issue or reach out.

---

## License

MIT
