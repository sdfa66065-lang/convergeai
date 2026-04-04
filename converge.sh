#!/bin/bash
# ──────────────────────────────────────────────────────────────────────
# converge.sh — Run the ConvergeAI agent
# ──────────────────────────────────────────────────────────────────────
# Usage:
#   ./converge.sh "There is a merge conflict in test_conflict.py.
#   The cherrypick commit sha is abc123 in repository owner/repo.
#   Please call distill_context and resolve it."
# ──────────────────────────────────────────────────────────────────────
set -e

# Resolve the directory this script lives in
CONVERGEAI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CONVERGEAI_ROOT

ENV_FILE="${CONVERGEAI_ROOT}/.env"

# ─── Preflight checks ────────────────────────────────────────────────

if [ ! -d "${CONVERGEAI_ROOT}/.venv" ]; then
    echo "ERROR: Virtual environment not found."
    echo "  Run ./setup.sh first."
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: API keys not configured."
    echo "  Run ./setup.sh first."
    exit 1
fi

if ! command -v goose &> /dev/null; then
    echo "ERROR: Goose CLI not found."
    echo "  Run ./setup.sh first."
    exit 1
fi

if [ -z "$1" ]; then
    echo "Usage: ./converge.sh \"<describe the merge conflict>\""
    echo ""
    echo "Example:"
    echo '  ./converge.sh "There is a merge conflict in main.py.'
    echo '  The cherrypick commit sha is abc123 in repository owner/repo.'
    echo '  Please call distill_context and resolve it."'
    exit 1
fi

# ─── Load environment ────────────────────────────────────────────────

# Export all variables from .env
set -a
source "$ENV_FILE"
set +a

# Prevent proxy collisions with Anthropic client
unset ANTHROPIC_BASE_URL 2>/dev/null || true

# Activate venv so 'python3' resolves to the venv Python
# (the ai-maintainer.yaml MCP config uses 'python3' as the command)
source "${CONVERGEAI_ROOT}/.venv/bin/activate"

USER_PROMPT="$1"

# ─── Launch the agent ─────────────────────────────────────────────────

echo ""
echo "ConvergeAI Agent starting..."
echo ""

echo "$USER_PROMPT" | goose run \
    --instructions "${CONVERGEAI_ROOT}/goose/ai-maintainer.yaml" \
    -i -
