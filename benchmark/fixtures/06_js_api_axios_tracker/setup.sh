#!/usr/bin/env bash
# scenario_5.sh — upstream axios; fork tracker + node-fetch
set -euo pipefail
WORKDIR="${1:?Usage: setup.sh <workdir>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../base_fixture.sh"
init_fixture_repo "$WORKDIR"

echo 'const fetch = require("node-fetch");
function getUser() {
  return fetch("/api/user");
}' > api.js
commit_file api.js "chore: basic api fetcher"

git checkout --quiet -b internal-fork
echo 'const fetch = require("node-fetch");
const tracker = require("./internal-tracker"); // CUSTOM FORK

function getUser() {
  tracker.log("User data requested"); // CUSTOM FORK
  return fetch("/api/user");
}' > api.js
commit_file api.js "feat(PROJ-105): add internal telemetry to api calls"

git checkout --quiet main
echo 'const axios = require("axios");
function getUser() {
  return axios.get("/api/user");
}' > api.js
commit_file api.js "refactor: migrate from node-fetch to axios"

create_conflict_internal_fork
echo "FIXTURE READY: api.js"
