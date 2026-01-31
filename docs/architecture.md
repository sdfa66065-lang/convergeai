# Control Plane vs Execution Plane

## Purpose
This document defines the strict boundary between the control plane and the execution plane to avoid architectural ambiguity.

## Execution plane
The execution plane is responsible for interacting with the repository and running commands.

**Responsibilities**
- Own the working filesystem inside the container.
- Run Git commands.
- Run build and test commands.
- Return artifacts, logs, and exit codes.

**Allowed actions**
- `checkout_repo`
- `merge_upstream`
- `run_build`
- `run_tests`
- `apply_patch`
- `commit_checkpoint`

## Control plane
The control plane decides what to do but never performs the actions directly.

**Responsibilities**
- Decide which execution-plane action to run.
- Record decisions and reasoning.
- Track iteration budget and stopping criteria.

**Constraints**
- Never edits files directly.
- Never runs shell commands directly.
- Only requests actions from the execution plane.
