#!/usr/bin/env bash
# scenario_4.sh — upstream nests connection; fork added sslCert flat
set -euo pipefail
WORKDIR="${1:?Usage: setup.sh <workdir>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../base_fixture.sh"
init_fixture_repo "$WORKDIR"

echo 'const dbConfig = {
  host: "localhost",
  port: 5432
};' > database.js
commit_file database.js "chore: setup database config"

git checkout --quiet -b internal-fork
echo 'const dbConfig = {
  host: "localhost",
  port: 5432,
  sslCert: "/var/internal/cert.pem" // CUSTOM FORK LOGIC
};' > database.js
commit_file database.js "feat(PROJ-104): add internal SSL cert requirement"

git checkout --quiet main
echo 'const dbConfig = {
  connection: {
    host: "localhost",
    port: 5432
  }
};' > database.js
commit_file database.js "refactor: group db settings into connection object"

create_conflict_internal_fork
echo "FIXTURE READY: database.js"
