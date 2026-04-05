#!/usr/bin/env bash
# Shared fixture utilities — sourced by every setup.sh
#
# To port external scenarios (see context-distiller-mcp/conflict_scenario/*.sh):
#   - Add benchmark/fixtures/<id>_<slug>/ with manifest.json + setup.sh
#   - Replace "mkdir test-repo && cd" with: WORKDIR="${1:?...}"; init_fixture_repo "$WORKDIR"
#   - Same rebase story as your scripts:
#       * Python-style: internal/fork vs upstream/main → create_conflict
#       * JS-style:     internal-fork vs main           → create_conflict_internal_fork
set -euo pipefail

init_fixture_repo() {
    local workdir="$1"
    mkdir -p "$workdir"
    cd "$workdir"
    git init --quiet
    git config user.email "benchmark@convergeai.test"
    git config user.name "ConvergeAI Benchmark"
}

commit_file() {
    local filepath="$1"
    local message="$2"
    git add "$filepath"
    git commit --quiet -m "$message"
}

create_conflict() {
    # Rebase internal branch onto upstream — expects conflict
    git checkout --quiet internal/fork
    if git rebase upstream/main 2>/dev/null; then
        echo "ERROR: Expected conflict but rebase succeeded cleanly" >&2
        exit 1
    fi

    # Verify conflict state
    if ! git diff --name-only --diff-filter=U | grep -q .; then
        echo "ERROR: No conflicted files detected after rebase" >&2
        exit 1
    fi

    echo "CONFLICT CREATED: $(git diff --name-only --diff-filter=U | tr '\n' ' ')"
}

# Matches scenario_*.sh pattern: branch "internal-fork", upstream line on "main".
create_conflict_internal_fork() {
    git checkout --quiet internal-fork
    if git rebase main 2>/dev/null; then
        echo "ERROR: Expected conflict but rebase succeeded cleanly" >&2
        exit 1
    fi
    if ! git diff --name-only --diff-filter=U | grep -q .; then
        echo "ERROR: No conflicted files detected after rebase" >&2
        exit 1
    fi
    echo "CONFLICT CREATED: $(git diff --name-only --diff-filter=U | tr '\n' ' ')"
}
