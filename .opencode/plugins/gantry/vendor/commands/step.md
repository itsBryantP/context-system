---
description: Inspect/update Gantry workflow step status and gate transitions.
argument-hint: workflow step-id or transition intent
---
Treat this as a workflow-step operation.

Guidelines:
- Prefer DAG dependencies as ordering source of truth.
- Move steps to terminal states only with acceptance evidence.
- Use `waiting-for-operator` only for explicit policy/risk approvals.
- Keep task/step state transitions consistent and auditable.
