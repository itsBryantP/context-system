---
name: mailbox-wake-default
event: gantry.wake
source: mailbox
no-reply: true
---
<gantry-context version="1">
Wake signal received from Gantry mailbox.

Wake reason: {event.properties.reason}
Priority: {event.properties.priority}
Summary: {event.properties.summary}
References: {event.properties.refs}
Origin: {event.properties.origin}
Idempotency key: {event.properties.idempotency_key}

If work is required, use Gantry lifecycle discipline:
- claim task before substantive work
- keep notes and evidence concise
- complete with outcome-focused summary and changed files
</gantry-context>
