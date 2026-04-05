#!/usr/bin/env bash
# scenario_2 — same-line return edit forces conflict (a1bc vs ab2c → a1b2c)
set -euo pipefail
WORKDIR="${1:?Usage: setup.sh <workdir>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../base_fixture.sh"
init_fixture_repo "$WORKDIR"

echo 'function generateCode() {
  return "abc";
}' > logic.js
commit_file logic.js "chore: initial base setup (abc)"

git checkout --quiet -b internal-fork
echo 'function generateCode() {
  return "ab2c"; // CUSTOM FORK
}' > logic.js
commit_file logic.js "feat(PROJ-102): fork string ab2c"

git checkout --quiet main
echo 'function generateCode() {
  return "a1bc"; // UPSTREAM
}' > logic.js
commit_file logic.js "refactor: upstream string a1bc"

create_conflict_internal_fork
echo "FIXTURE READY: logic.js"
