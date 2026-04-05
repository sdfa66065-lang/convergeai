#!/usr/bin/env bash
# scenario_3.sh — upstream maxRetries=3 vs fork retryLimit rename
set -euo pipefail
WORKDIR="${1:?Usage: setup.sh <workdir>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../base_fixture.sh"
init_fixture_repo "$WORKDIR"

echo 'function getConfig() {
  let maxRetries = 1;
  return maxRetries;
}' > config.js
commit_file config.js "chore: initial base setup"

git checkout --quiet -b internal-fork
echo 'function getConfig() {
  // CUSTOM FORK LOGIC: rename to match internal terminology
  let retryLimit = 1;
  return retryLimit;
}' > config.js
commit_file config.js "feat(PROJ-103): update terminology to retryLimit"

git checkout --quiet main
echo 'function getConfig() {
  let maxRetries = 3; // UPSTREAM UPGRADE: 1 was too low
  return maxRetries;
}' > config.js
commit_file config.js "fix: increase maxRetries to 3 for better stability"

create_conflict_internal_fork
echo "FIXTURE READY: config.js"
