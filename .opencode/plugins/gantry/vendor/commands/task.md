---
description: Claim, execute, and complete a Gantry task with evidence.
argument-hint: task-id or natural-language task intent
---
Use Gantry task lifecycle discipline for this request.

Required flow:
1. Resolve target task (or list and choose a ready task).
2. Claim the task.
3. Execute requested work and validate outcomes.
4. Add concise notes and evidence as work progresses.
5. Complete the task with outcome-focused summary, changed files, and commit reference when code changed.

Enforce required IDs (`workflow_id`, `workstream_id`, and `step_id` when DAG-based).
