# Conflict Fixture / Rebase Trap (Track C)

This fixture creates a **predictable git rebase conflict** between an upstream branch and an internal customization branch.

Goal: let a new contributor set up and reproduce the conflict in under 5 minutes.

---

## Scenario summary

The trap simulates a realistic maintenance problem:

- **Upstream** modifies shared policy behavior and schema fields.
- **Internal customization** modifies the same lines to enforce local defaults.
- During `git rebase`, both branches touch the same hunk, causing a conflict that must be resolved with intent (not just `--ours` / `--theirs`).

---

## Branch model

Use these branch names consistently:

- `main` — base repository state
- `upstream/main` — represents incoming upstream changes
- `internal/customized` — local branch with product-specific customization

If you do not use a remote named `upstream`, create local stand-ins:

- `fixture/upstream-main`
- `fixture/internal-customized`

The setup script can map whichever naming scheme is available.

---

## Files intentionally put in conflict

Primary conflict target:

- `ai-maintainer.yaml`

Optional secondary conflict target (if included in your trap implementation):

- `mcp_context_distiller/fixtures/rules.json`

The fixture should ensure at least one conflict in `ai-maintainer.yaml`.

---

## Quick start (recommended path)

Run from repo root:

```bash
bash scripts/setup_rebase_trap.sh
```

Expected script behavior:

1. Verifies clean working tree.
2. Creates/reset fixture branches.
3. Applies upstream edits on upstream branch.
4. Applies internal edits on internal branch.
5. Attempts rebase of internal branch onto upstream branch.
6. Stops with conflict markers in target file(s).

Time target: **< 5 minutes** for first-time contributor.

---

## Manual setup (fallback)

If the setup script is unavailable, follow these steps.

### 1) Confirm clean state

```bash
git status --porcelain
```

Output must be empty.

### 2) Create upstream fixture branch

```bash
git checkout -B fixture/upstream-main main
# edit ai-maintainer.yaml with upstream policy changes
git add ai-maintainer.yaml
git commit -m "fixture: upstream maintenance policy update"
```

### 3) Create internal fixture branch from same base

```bash
git checkout -B fixture/internal-customized main
# edit ai-maintainer.yaml with internal customization changes
git add ai-maintainer.yaml
git commit -m "fixture: internal customization defaults"
```

### 4) Trigger trap via rebase

```bash
git rebase fixture/upstream-main
```

Expected: rebase stops with conflict in `ai-maintainer.yaml`.

---

## Expected terminal signals

During trap execution, you should see output similar to:

- `CONFLICT (content): Merge conflict in ai-maintainer.yaml`
- `error: could not apply ...`

And `git status` should show:

- `both modified: ai-maintainer.yaml`
- `You are currently rebasing...`

---

## Resolution workflow (for demo users)

1. Open conflicted file and reconcile according to `fixtures/expected_outcome.md`.
2. Stage resolved files.
3. Continue rebase.

```bash
git add ai-maintainer.yaml
git rebase --continue
```

4. Run fixture validator (if available):

```bash
bash scripts/validate_demo.sh
```

---

## Reset and rerun

```bash
git rebase --abort || true
git checkout main
git branch -D fixture/upstream-main fixture/internal-customized 2>/dev/null || true
bash scripts/setup_rebase_trap.sh
```

---

## Success criteria

A new contributor succeeds when they can:

- run setup script with no manual git surgery,
- observe a deterministic conflict,
- resolve it using documented intent,
- pass validation checks,
- complete end-to-end in under 5 minutes.
