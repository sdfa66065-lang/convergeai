# Exporting Goose Chat History

After a ConvergeAI session resolves merge conflicts, the full chat history — every prompt, tool call, and agent response — is stored by Goose. Exporting it gives you an auditable record for reproducibility, cost tracking, and post-mortem analysis.

---

## 1. Finding Your Session ID

When you launch a session with `./converge.sh`, Goose prints the session ID at boot:

```
    __( O)>  ● new session · anthropic claude-sonnet-4-6
   \____)    20260403_20 · /path/to/convergeai
     L L     goose is ready
```

The session ID here is **`20260403_20`**. Copy it — you will need it for export.

---

## 2. Listing All Sessions

To see every session Goose has on record:

```bash
goose session list
```

This prints a table of session IDs, names, creation times, and token counts. Use it when you do not remember the exact session ID.

---

## 3. Exporting a Session

```bash
goose session export \
  --session-id <SESSION_ID> \
  -o ./output/chat_history.json \
  --format json
```

| Flag             | Description                                      |
|------------------|--------------------------------------------------|
| `--session-id`   | The session ID from step 1 or 2                  |
| `-o`             | Output file path (any writable location)         |
| `--format`       | Export format — `json` for structured data        |

### Example

```bash
goose session export \
  --session-id 20260403_20 \
  -o ./demo/single_file_blending/test1/goose_convergeai_chat_history.json \
  --format json
```

---

## 4. Export Formats

| Format | Use case                                                        |
|--------|-----------------------------------------------------------------|
| `json` | Machine-readable — parse with `jq`, load into dashboards, diff |

---

## 5. Interpreting the Exported JSON

A typical export contains these top-level fields:

```jsonc
{
  "id": "20260403_20",              // session ID
  "working_dir": "/path/to/repo",   // repo root at session time
  "name": "Git merge conflict resolution",
  "created_at": "2026-04-03T19:50:29Z",
  "updated_at": "2026-04-03T19:51:30Z",

  // --- Extensions & state ---
  "extension_data": {
    "todo.v0": { "content": "- [x] Read conflicted file ..." },
    "enabled_extensions.v0": { "extensions": [ /* ... */ ] }
  },

  // --- Token accounting ---
  "total_tokens": 12232,
  "input_tokens": 11859,
  "output_tokens": 373,
  "accumulated_total_tokens": 70587,
  "accumulated_input_tokens": 67481,
  "accumulated_output_tokens": 3106,

  // --- Conversation ---
  "conversation": [ /* array of message objects */ ]
}
```

### Key sections

**`extension_data`** — Captures which MCP servers and Goose extensions were active (e.g., `converge-ai`, `developer`, `todo`), plus the final state of the todo checklist.

**Token fields** — `total_tokens` / `input_tokens` / `output_tokens` are for the last turn. The `accumulated_*` fields are the running total across the entire session — useful for cost estimation.

**`conversation`** — An ordered array of message objects. Each message has:

| Field      | Description                                                                 |
|------------|-----------------------------------------------------------------------------|
| `id`       | Unique message ID                                                           |
| `role`     | `user` or `assistant`                                                       |
| `created`  | Unix timestamp                                                              |
| `content`  | Array of content blocks — `text`, `thinking`, `toolRequest`, `toolResult`   |
| `metadata` | Visibility flags (`userVisible`, `agentVisible`)                            |

Tool calls appear as `toolRequest` blocks containing the tool name and arguments; their results follow as `toolResult` blocks with status and output.

---

## 6. Demo Files

The `demo/single_file_blending/test1/` directory contains two reference exports:

| File                                    | Description                                          |
|-----------------------------------------|------------------------------------------------------|
| `goose_native__chat_history.json`       | Goose resolving the conflict without ConvergeAI MCP  |
| `goose_convergeai_chat_history.json`    | Goose resolving the conflict with ConvergeAI MCP     |

Compare the two to see how the ConvergeAI context distiller changes the agent's resolution strategy.
