#!/usr/bin/env bash
# scenario_6.sh — fork customAuth; upstream logger
set -euo pipefail
WORKDIR="${1:?Usage: setup.sh <workdir>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../base_fixture.sh"
init_fixture_repo "$WORKDIR"

echo 'const { helper } = require("./utils");

function run() {
  return helper();
}' > index.js
commit_file index.js "chore: initial setup"

git checkout --quiet -b internal-fork
echo 'const { customAuth } = require("./enterprise-security"); // FORK
const { helper } = require("./utils");

function run() {
  customAuth.verify();
  return helper();
}' > index.js
commit_file index.js "feat(PROJ-106): require enterprise auth before running"

git checkout --quiet main
echo 'const { logger } = require("./logger"); // UPSTREAM
const { helper } = require("./utils");

function run() {
  logger.info("Running system...");
  return helper();
}' > index.js
commit_file index.js "feat: add system logging"

create_conflict_internal_fork
echo "FIXTURE READY: index.js"
