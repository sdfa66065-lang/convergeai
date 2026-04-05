#!/usr/bin/env bash
# scenario_7.sh — array tail: sso-saml vs dark-mode
set -euo pipefail
WORKDIR="${1:?Usage: setup.sh <workdir>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../base_fixture.sh"
init_fixture_repo "$WORKDIR"

echo 'const activeFeatures = [
  "dashboard",
  "profile"
];' > features.js
commit_file features.js "chore: default features"

git checkout --quiet -b internal-fork
echo 'const activeFeatures = [
  "dashboard",
  "profile",
  "sso-saml" // FORK CUSTOM FEATURE
];' > features.js
commit_file features.js "feat(PROJ-107): enable SAML Single Sign-On"

git checkout --quiet main
echo 'const activeFeatures = [
  "dashboard",
  "profile",
  "dark-mode" // UPSTREAM NEW FEATURE
];' > features.js
commit_file features.js "feat: release dark mode feature"

create_conflict_internal_fork
echo "FIXTURE READY: features.js"
