---
name: reactor-wake-default
event: gantry.wake
source: reactor
no-reply: true
---
Gantry reactor wakeup detected.

Reason: {event.properties.reason}
Priority: {event.properties.priority}
Summary: {event.properties.summary}
Refs: {event.properties.refs}
Origin: {event.properties.origin}
Idempotency key: {event.properties.idempotency_key}

Respond to this wakeup using Gantry workflow protocol. Start by checking
mailbox/task/workflow state relevant to the references.
