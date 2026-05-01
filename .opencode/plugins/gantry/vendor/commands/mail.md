---
description: Check/read/send Gantry mailbox messages and summarize required follow-up.
argument-hint: role/session mailbox operation
---
Handle this as a Gantry mail operation.

Flow:
1. Resolve target inbox scope (session/role).
2. Check unread/recent messages.
3. Read relevant message bodies.
4. If action is requested, execute with task/workflow discipline.
5. Optionally send concise acknowledgment or handoff mail.

Return a compact mailbox summary and next action.
