#!/usr/bin/env bash
# scenario_8.sh — upstream replaces makeNetworkRequest with performSecureRequest
set -euo pipefail
WORKDIR="${1:?Usage: setup.sh <workdir>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../base_fixture.sh"
init_fixture_repo "$WORKDIR"

echo 'function makeNetworkRequest(url) {
  return fetch(url);
}' > network.js
commit_file network.js "chore: simple network fetcher"

git checkout --quiet -b internal-fork
echo 'function makeNetworkRequest(url) {
  // FORK: Route everything through internal proxy
  const proxyUrl = "http://internal-proxy.com/?url=" + url;
  return fetch(proxyUrl);
}' > network.js
commit_file network.js "feat(PROJ-108): force all traffic through corporate proxy"

git checkout --quiet main
echo 'function performSecureRequest(requestData) { // UPSTREAM REPLACED IT
  console.log("Securing request...");
  return fetch(requestData.endpoint);
}' > network.js
commit_file network.js "refactor: replace makeNetworkRequest with performSecureRequest"

create_conflict_internal_fork
echo "FIXTURE READY: network.js"
