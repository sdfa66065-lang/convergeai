#!/usr/bin/env bash
# Shared fixture utilities — sourced by every setup.sh
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
