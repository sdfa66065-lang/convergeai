# Expected Outcome — Conflict Fixture / Rebase Trap

This document defines **pass/fail semantics** for resolving the Track C rebase trap.
Validation scripts should map checks directly to the IDs below.

---

## Resolution intent

The final resolved state must preserve:

1. **Upstream maintenance guarantees** (security, compatibility, schema progression).
2. **Internal customization guarantees** (local defaults, model routing, org constraints).

A valid merge is not pure upstream and not pure internal; it is an intentional composition.

---

## Must keep from upstream

### UP-1: Schema/version progression
- Keep upstream schema or config version bump(s).
- Keep new required keys introduced by upstream.
- Do not revert structural migrations made upstream.

### UP-2: Safety/guardrail hardening
- Keep stricter upstream safety and validation settings.
- Keep any upstream deny/allow rule updates tied to policy hardening.

### UP-3: Operational compatibility
- Keep upstream compatibility fields used by newer tooling.
- Keep upstream key names if they replaced deprecated names.

### UP-4: Deterministic behavior additions
- Keep upstream deterministic defaults (timeouts, retry caps, ordering rules) when newly introduced.

---

## Must keep from internal customization

### IN-1: Organization-specific defaults
- Keep internal default model/provider selections where explicitly customized.
- Keep internal runtime defaults required by the organization environment.

### IN-2: Internal policy overlays
- Keep internal policy constraints that are additive (not conflicting with upstream safety requirements).
- Keep internal allow/deny entries needed for local governance.

### IN-3: Integration wiring
- Keep internal endpoint identifiers, tenant references, and environment bindings.
- Keep internal hooks/scripts references used by local automation.

### IN-4: Local documentation/comments with operational value
- Keep concise internal comments that explain non-obvious local behavior.

---

## Conflict resolution rules

### CR-1: Safety precedence
If upstream and internal values conflict on safety strictness, choose the **stricter** effective behavior.

### CR-2: Naming precedence
If upstream renamed a key and internal changed the old key, migrate internal intent onto the new upstream key.

### CR-3: No marker leakage
Final files must contain no conflict markers:
- `<<<<<<<`
- `=======`
- `>>>>>>>`

### CR-4: Semantic preservation over textual preservation
Equivalent refactors are acceptable if both upstream and internal intents remain true.

---

## Validation mapping (for `scripts/validate_demo.sh`)

The validator should emit one result per check ID.

### Required checks

- `CHK-UP-1` → verifies UP-1
- `CHK-UP-2` → verifies UP-2
- `CHK-UP-3` → verifies UP-3
- `CHK-IN-1` → verifies IN-1
- `CHK-IN-2` → verifies IN-2
- `CHK-IN-3` → verifies IN-3
- `CHK-CR-3` → verifies CR-3

### Optional checks

- `CHK-UP-4` → verifies UP-4 when present in fixture
- `CHK-IN-4` → verifies IN-4 when comments are part of fixture
- `CHK-CR-1` / `CHK-CR-2` / `CHK-CR-4` → semantic checks when detectable

---

## Pass/fail semantics

## PASS
A submission is **PASS** only if:

- all required checks pass,
- no conflict markers remain,
- resolution includes at least one preserved upstream intent and one preserved internal intent.

## FAIL
A submission is **FAIL** if any of the following is true:

- any required check fails,
- conflict markers remain,
- result is effectively `--ours` or `--theirs` with one side's intent dropped,
- schema/version regression introduced.

---

## Reviewer quick rubric

Use this quick rubric for manual confirmation:

- Upstream hardening preserved? **Yes/No**
- Internal customization preserved? **Yes/No**
- Conflict markers removed? **Yes/No**
- Validator required checks all green? **Yes/No**

All must be **Yes**.
