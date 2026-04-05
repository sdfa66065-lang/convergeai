#!/usr/bin/env bash
# Ported from context-distiller-mcp conflict_scenario/scenario_1.sh
set -euo pipefail
WORKDIR="${1:?Usage: setup.sh <workdir>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../base_fixture.sh"
init_fixture_repo "$WORKDIR"

echo 'function authenticate(username, password) {
  return username === "admin" && password === "secret";
}' > auth.js
commit_file auth.js "chore: initial auth setup"

git checkout --quiet -b internal-fork
echo 'function authenticate(username, password) {
  // CUSTOM QA BYPASS
  if (username.endsWith("@internal.com")) return true;
  return username === "admin" && password === "secret";
}' > auth.js
commit_file auth.js "feat(PROJ-101): add QA bypass for internal testing"

git checkout --quiet main
echo 'function authenticate(requestObject) {
  const { user, pass } = requestObject.body;
  return user === "admin" && pass === "secret";
}' > auth.js
commit_file auth.js "refactor: switch auth to use request objects"

create_conflict_internal_fork
echo "FIXTURE READY: auth.js"
