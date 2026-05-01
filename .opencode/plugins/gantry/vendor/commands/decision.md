---
description: Handle Gantry operator decision gates for workflow steps.
argument-hint: decision-id or step awaiting operator
---
Work this as an operator decision flow.

Required behavior:
1. Find pending decision payload (type/options/required_role/default/timeout).
2. Confirm current session role satisfies `required_role`.
3. Evaluate consequences of each option briefly.
4. Respond with selected option and rationale.
5. Summarize resulting step/workflow state.
