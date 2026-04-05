#!/usr/bin/env bash
# scenario_10.sh — cherry-pick + upstream rename → rebase conflict (setup exits 0)
set -euo pipefail
WORKDIR="${1:?Usage: setup.sh <workdir>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../base_fixture.sh"
init_fixture_repo "$WORKDIR"

echo 'const port = 8080;' > server.js
commit_file server.js "chore: initial server port"

git checkout --quiet -b upstream-beta
cat > server.js <<'EOF'
const port = process.env.PORT || 8080;
const secure = true;
EOF
commit_file server.js "feat(beta): env-based port and secure flag"

BETA_HASH="$(git rev-parse HEAD)"

git checkout --quiet main
git checkout --quiet -b internal-fork
git cherry-pick --quiet "${BETA_HASH}"

cat > server.js <<'EOF'
const port = process.env.PORT || 8080;
const secure = true;
console.log("fork: smoke test assumes upstream beta 'secure' flag name");
EOF
commit_file server.js "chore(fork): smoke test after early cherry-pick of beta"

git checkout --quiet upstream-beta
cat > server.js <<'EOF'
const port = process.env.PORT || 8080;
const isSecureMode = true;
EOF
commit_file server.js "refactor(beta): rename secure -> isSecureMode for clarity"

git checkout --quiet main
git merge --quiet upstream-beta -m "release: merge upstream-beta into main"

git checkout --quiet internal-fork
set +e
git rebase main
_rebase_st=$?
set -e
if [[ "${_rebase_st}" -eq 0 ]]; then
  echo "ERROR: expected rebase to stop with conflicts" >&2
  exit 1
fi
if ! git diff --name-only --diff-filter=U | grep -q .; then
  echo "ERROR: expected conflicted paths" >&2
  exit 1
fi
echo "FIXTURE READY: server.js (rebase in progress)"
