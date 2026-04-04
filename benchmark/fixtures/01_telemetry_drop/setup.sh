#!/usr/bin/env bash
# Fixture: Telemetry Drop
#
# Scenario: Upstream renames function param (ticket_id -> target_ref) and swaps
# data source (Jira -> GitHub). Internal fork has added telemetry logging and
# a cache layer on top of the original signature.
#
# Conflict: parameter rename collides with enterprise customizations.
# Expected resolution: BLEND — unified signature supporting both params.
set -euo pipefail

WORKDIR="${1:?Usage: setup.sh <workdir>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../base_fixture.sh"

init_fixture_repo "$WORKDIR"

# --- Step 1: Base commit (the shared starting point) ---
cat > distill_context.py << 'PYEOF'
def distill_context(ticket_id: str):
    """Fetch context for a given Jira ticket."""
    return fetch_jira_payload(ticket_id)
PYEOF
commit_file distill_context.py "initial: distill_context with ticket_id param"

# --- Step 2: Create upstream branch with architectural change ---
git checkout --quiet -b upstream/main

cat > distill_context.py << 'PYEOF'
def distill_context(target_ref: str):
    """Fetch context for a given commit reference."""
    return fetch_github_payload(target_ref)
PYEOF
commit_file distill_context.py "upstream: rename param to target_ref, switch to github payload"

# --- Step 3: Create internal fork branch from original main ---
git checkout --quiet main
git checkout --quiet -b internal/fork

cat > distill_context.py << 'PYEOF'
def distill_context(ticket_id: str):
    """Fetch context for a given Jira ticket with telemetry and caching."""
    log_telemetry("distill_context_called", ticket_id)
    if cache.exists(ticket_id):
        return cache.get(ticket_id)
    return fetch_jira_payload(ticket_id)
PYEOF
commit_file distill_context.py "internal: add telemetry logging and cache layer"

# --- Step 4: Trigger the conflict ---
create_conflict

echo "FIXTURE READY: conflict in distill_context.py"
echo "Run 'git diff distill_context.py' to see the conflict markers."
