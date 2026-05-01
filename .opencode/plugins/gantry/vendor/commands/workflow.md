---
description: Create, inspect, or update Gantry workflow state.
argument-hint: workflow objective or workflow-id
---
Work this as a Gantry workflow operation.

If creating a workflow:
- Define clear `title`, `description`, and canonical `workstream_id`.
- Prefer a step DAG with explicit `depends_on` for non-trivial work.
- Keep steps independently completable where possible.

If updating an existing workflow:
- Inspect current step states and blockers.
- Update only what is necessary and preserve evidence lineage.
