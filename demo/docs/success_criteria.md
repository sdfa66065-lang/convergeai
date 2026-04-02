# Success and Failure Semantics

## Success
The system reports success only when all of the following are true:
- The upstream merge completes.
- No merge conflicts remain.
- Build and test commands pass.

## Acceptable failure
The system may stop with a failure state if any of the following are true:
- The iteration budget is exhausted (default: 5 loops).
- The resulting state is replayable from logs and artifacts.
- Logs clearly explain the failure and stopping reason.

## Unacceptable failure
The system must never enter any of the following states:
- Silent exit without explanation.
- Mutations that cannot be replayed from logs/artifacts.
- Unclear stopping reasons or missing failure context.
