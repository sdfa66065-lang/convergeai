#!/usr/bin/env bash
# scenario_9.sh — clean rebase; runtime mismatch (no git conflict)
set -euo pipefail
WORKDIR="${1:?Usage: setup.sh <workdir>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../base_fixture.sh"
init_fixture_repo "$WORKDIR"

cat > math.js <<'EOF'
function calculate(a, b) {
  return a + b;
}
module.exports = { calculate };
EOF
commit_file math.js "chore: add calculate(a, b)"

git checkout --quiet -b internal-fork
cat > enterprise-billing.js <<'EOF'
const { calculate } = require('./math.js');
console.log('Enterprise billing line item:', calculate(100, 50));
EOF
git add enterprise-billing.js
git commit --quiet -m "feat(PROJ-901): wire billing to shared math helper"

git checkout --quiet main
cat > math.js <<'EOF'
function calculate(options) {
  if (typeof options !== 'object' || options === null) {
    throw new Error('calculate expects an object: { a, b }');
  }
  return options.a + options.b;
}
module.exports = { calculate };
EOF
commit_file math.js "refactor!: calculate now takes an options object"

git checkout --quiet internal-fork
git rebase main

echo "FIXTURE READY: clean tree; fix enterprise-billing to use object API"
