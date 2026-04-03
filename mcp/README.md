# Context Distiller MCP Server

A stdio-based Python MCP server that acts as the "LLM-in-the-middle" for Goose during semantic conflict resolution. It exposes a single `distill_context` tool that internally fetches from Jira and GitHub APIs, then calls a fast LLM to produce structured merge guidance.

## Setup

### Install dependencies

```bash
pip install -r mcp/context_distiller/requirements.txt
```

### Configure environment variables

Copy the example and fill in your credentials:

```bash
cp mcp/context_distiller/.env.example mcp/context_distiller/.env
source mcp/context_distiller/.env
```

Required variables:

| Variable | Description |
|---|---|
| `JIRA_BASE_URL` | e.g. `https://yourorg.atlassian.net` |
| `JIRA_EMAIL` | Your Jira account email |
| `JIRA_API_TOKEN` | Jira API token |
| `GITHUB_TOKEN` | GitHub personal access token |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `DISTILL_MODEL` | *(optional)* Defaults to `claude-haiku-4-5-20251001` |

## Testing

### 1. MCP Inspector (recommended for interactive testing)

```bash
npx @modelcontextprotocol/inspector python3 mcp/context_distiller/server.py
```

This opens a web UI where you can see your tools, call `distill_context` with test inputs, and inspect the JSON responses.

### 2. Pipe raw JSON-RPC to stdin

Quick sanity check that the server starts and lists tools:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"},"protocolVersion":"2024-11-05"}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | python3 mcp/context_distiller/server.py
```

You should see two JSON-RPC responses: one for the initialization handshake, and one listing the `distill_context` tool with its schema.

### 3. Python test script (direct function calls)

Bypass the MCP protocol and test the internal functions directly. Useful for debugging Jira/GitHub/LLM individually:

```python
import asyncio
from mcp.context_distiller.server import (
    fetch_jira_ticket,
    fetch_pull_request,
    distill_context,
)

async def main():
    # Test Jira fetch
    ticket = await fetch_jira_ticket("PROJ-101")
    print(ticket)

    # Test GitHub PR fetch
    pr = await fetch_pull_request("owner/repo", 42)
    print(pr)

    # Test full distillation
    result = await distill_context(pr, ticket, ["src/config.py"])
    print(result)

asyncio.run(main())
```

## Usage with Goose

Add the MCP server to your Goose profile (`~/.config/goose/profiles.yaml`):

```yaml
mcpServers:
  context-distiller:
    command: python3
    args:
      - mcp/context_distiller/server.py
    env:
      JIRA_BASE_URL: ${JIRA_BASE_URL}
      JIRA_EMAIL: ${JIRA_EMAIL}
      JIRA_API_TOKEN: ${JIRA_API_TOKEN}
      GITHUB_TOKEN: ${GITHUB_TOKEN}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
```

Goose will then have access to the `distill_context` tool during conflict resolution sessions.
