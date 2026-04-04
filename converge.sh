#!/bin/bash

# 1. Set the root directory dynamically
export CONVERGEAI_ROOT=$(pwd)

# 2. Load environment variables from .env
if [ -f .env ]; then
    set -a; source .env; set +a
fi

# 3. Check if the virtual environment exists
if [ ! -d ".venv" ]; then
    echo "⚙️  First run detected: Setting up ConvergeAI environment..."
    python3 -m venv .venv

    # Use the specific pip inside the new venv to install dependencies
    .venv/bin/pip install mcp httpx anthropic --quiet
    echo "✅ Environment ready."
fi

# 4. Grab the user's prompt (passed as an argument)
USER_PROMPT=$1

# 5. Execute Goose using the guaranteed Python path
echo "🚀 Booting ConvergeAI Agent..."
goose run \
  --with-extension "${CONVERGEAI_ROOT}/.venv/bin/python ${CONVERGEAI_ROOT}/mcp/context_distiller/server.py" \
  --text "$USER_PROMPT"
