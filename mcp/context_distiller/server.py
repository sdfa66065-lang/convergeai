#!/usr/bin/env python3
"""
Context Distiller MCP Server (stdio-based)

An MCP server that provides tools for Goose to fetch upstream intent
(from GitHub PRs) and internal constraints (from Jira tickets), then
uses a fast LLM to distill both into structured, actionable context
for semantic conflict resolution.
"""

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

logger = logging.getLogger("context-distiller")

import anthropic
import httpx
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# ---------------------------------------------------------------------------
# Configuration (from environment variables)
# ---------------------------------------------------------------------------
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "")  # e.g. https://yourorg.atlassian.net
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

DISTILL_MODEL = os.environ.get("DISTILL_MODEL", "claude-haiku-4-5-20251001")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class JiraTicket:
    key: str
    summary: str
    description: str
    status: str
    priority: str
    labels: list[str] = field(default_factory=list)
    acceptance_criteria: str = ""


@dataclass
class PullRequest:
    repo: str
    pr_number: int
    title: str
    body: str
    author: str
    labels: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)


@dataclass
class DistilledContext:
    upstream_intent: str
    internal_constraints: list[str]
    conflict_guidance: str
    risk_assessment: str
    recommended_strategy: str
    jira_key: Optional[str] = None
    pr_ref: Optional[str] = None


# ---------------------------------------------------------------------------
# Jira client
# ---------------------------------------------------------------------------

async def fetch_jira_ticket(ticket_id: str) -> JiraTicket:
    """Fetch a Jira ticket by its key (e.g. PROJ-101)."""
    if not JIRA_BASE_URL or not JIRA_EMAIL or not JIRA_API_TOKEN:
        raise ValueError(
            "JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN must be set. "
            "Export them as environment variables."
        )

    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{ticket_id}"
    auth = httpx.BasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, auth=auth, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()

    fields = data.get("fields", {})

    # Jira description can be ADF (Atlassian Document Format) or plain text
    raw_desc = fields.get("description", "")
    if isinstance(raw_desc, dict):
        # Flatten ADF to plain text (simple extraction)
        description = _flatten_adf(raw_desc)
    else:
        description = raw_desc or ""

    # Try to extract acceptance criteria from a custom field or description
    acceptance = ""
    for key, val in fields.items():
        if "acceptance" in key.lower() and isinstance(val, str):
            acceptance = val
            break

    return JiraTicket(
        key=data["key"],
        summary=fields.get("summary", ""),
        description=description,
        status=fields.get("status", {}).get("name", ""),
        priority=fields.get("priority", {}).get("name", ""),
        labels=fields.get("labels", []),
        acceptance_criteria=acceptance,
    )


def _flatten_adf(node: dict) -> str:
    """Recursively extract text from Atlassian Document Format."""
    if node.get("type") == "text":
        return node.get("text", "")
    parts = []
    for child in node.get("content", []):
        parts.append(_flatten_adf(child))
    return " ".join(parts).strip()


# ---------------------------------------------------------------------------
# GitHub client
# ---------------------------------------------------------------------------

async def fetch_pull_request(repo: str, pr_number: int) -> PullRequest:
    """Fetch a GitHub pull request. repo format: owner/repo"""
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    async with httpx.AsyncClient() as client:
        # Fetch PR metadata
        pr_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
        resp = await client.get(pr_url, headers=headers)
        resp.raise_for_status()
        pr_data = resp.json()

        # Fetch changed files
        files_url = f"{pr_url}/files"
        files_resp = await client.get(files_url, headers=headers)
        files_resp.raise_for_status()
        files_data = files_resp.json()

    changed_files = [f["filename"] for f in files_data[:100]]  # cap at 100
    labels = [l["name"] for l in pr_data.get("labels", [])]

    return PullRequest(
        repo=repo,
        pr_number=pr_number,
        title=pr_data.get("title", ""),
        body=pr_data.get("body", "") or "",
        author=pr_data.get("user", {}).get("login", ""),
        labels=labels,
        changed_files=changed_files,
    )


# ---------------------------------------------------------------------------
# LLM distillation
# ---------------------------------------------------------------------------

DISTILL_SYSTEM_PROMPT = """\
You are a concise technical analyst for an AI fork-sync engine. Given upstream PR \
information and internal Jira ticket constraints, produce a structured analysis that \
will guide an AI agent resolving merge conflicts.

Be extremely precise and actionable. Use bullet points. Never be vague.\
"""

DISTILL_USER_TEMPLATE = """\
## Upstream PR Context
{pr_context}

## Internal Ticket Constraints
{jira_context}

## Conflicted Files
{conflicted_files}

---

Produce a JSON object with these exact keys:
- "upstream_intent": One paragraph explaining what the upstream change is trying to achieve.
- "internal_constraints": A list of strings, each a specific business rule or constraint \
  that the fork MUST preserve.
- "conflict_guidance": Specific instructions for resolving the conflict — which parts of \
  upstream to accept, which internal logic to keep, and how to blend them.
- "risk_assessment": What could go wrong if the merge is done incorrectly.
- "recommended_strategy": One of "accept_upstream", "keep_ours", "blend", or "manual_review" \
  with a brief justification.

Return ONLY valid JSON, no markdown fences.\
"""


async def distill_context(
    pr_info: Optional[PullRequest],
    jira_info: Optional[JiraTicket],
    conflicted_files: list[str] | None = None,
) -> DistilledContext:
    """Use a fast LLM to distill PR + Jira context into actionable merge guidance."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY must be set.")

    pr_context = "No PR information provided."
    if pr_info:
        pr_context = (
            f"**{pr_info.title}** (#{pr_info.pr_number} in {pr_info.repo})\n"
            f"Author: {pr_info.author}\n"
            f"Labels: {', '.join(pr_info.labels) or 'none'}\n\n"
            f"{pr_info.body}\n\n"
            f"Changed files: {', '.join(pr_info.changed_files[:20])}"
        )

    jira_context = "No Jira ticket provided."
    if jira_info:
        jira_context = (
            f"**{jira_info.key}: {jira_info.summary}**\n"
            f"Status: {jira_info.status} | Priority: {jira_info.priority}\n"
            f"Labels: {', '.join(jira_info.labels) or 'none'}\n\n"
            f"{jira_info.description}\n\n"
        )
        if jira_info.acceptance_criteria:
            jira_context += f"Acceptance Criteria:\n{jira_info.acceptance_criteria}"

    files_str = ", ".join(conflicted_files) if conflicted_files else "Not specified"

    user_msg = DISTILL_USER_TEMPLATE.format(
        pr_context=pr_context,
        jira_context=jira_context,
        conflicted_files=files_str,
    )

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model=DISTILL_MODEL,
        max_tokens=1024,
        system=DISTILL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw_text = response.content[0].text.strip()

    # Parse the LLM JSON response
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown fences
        import re
        match = re.search(r"\{[\s\S]*\}", raw_text)
        if match:
            parsed = json.loads(match.group())
        else:
            raise ValueError(f"LLM returned non-JSON response: {raw_text[:200]}")

    return DistilledContext(
        upstream_intent=parsed.get("upstream_intent", ""),
        internal_constraints=parsed.get("internal_constraints", []),
        conflict_guidance=parsed.get("conflict_guidance", ""),
        risk_assessment=parsed.get("risk_assessment", ""),
        recommended_strategy=parsed.get("recommended_strategy", ""),
        jira_key=jira_info.key if jira_info else None,
        pr_ref=f"{pr_info.repo}#{pr_info.pr_number}" if pr_info else None,
    )


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

app = Server("context-distiller")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="distill_context",
            description=(
                "Single entry point for context distillation. Provide a Jira ticket "
                "key and/or a GitHub PR reference (repo + pr_number). Internally "
                "fetches from Jira and GitHub APIs, then uses a fast LLM to produce "
                "structured merge-conflict guidance: upstream intent, internal "
                "constraints, conflict resolution guidance, risk assessment, and "
                "recommended strategy. Returns structured JSON suitable for display "
                "in a review UI to assist decision-making during user intervention."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Jira ticket key (e.g. PROJ-101). Optional.",
                    },
                    "repo": {
                        "type": "string",
                        "description": "GitHub repo in owner/repo format. Optional.",
                    },
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number. Required if repo is provided.",
                    },
                    "conflicted_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file paths with merge conflicts.",
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "distill_context":
            # Fetch sources as needed
            jira_info = None
            pr_info = None

            ticket_id = arguments.get("ticket_id")
            repo = arguments.get("repo")
            pr_number = arguments.get("pr_number")
            conflicted_files = arguments.get("conflicted_files", [])

            if ticket_id:
                jira_info = await fetch_jira_ticket(ticket_id)
            else:
                logger.warning("No ticket_id provided — distilling without internal constraints")

            if repo and not pr_number:
                logger.warning("repo=%s provided without pr_number — skipping upstream PR fetch", repo)
            elif pr_number and not repo:
                logger.warning("pr_number=%s provided without repo — skipping upstream PR fetch", pr_number)
            elif repo and pr_number:
                pr_info = await fetch_pull_request(repo, pr_number)

            if not jira_info and not pr_info:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": "Provide at least a ticket_id or repo+pr_number."}),
                )]

            result = await distill_context(pr_info, jira_info, conflicted_files)
            return [TextContent(type="text", text=json.dumps(asdict(result), indent=2))]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
