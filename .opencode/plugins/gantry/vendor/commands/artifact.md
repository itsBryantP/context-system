---
description: Write/publish Gantry artifacts and attach artifact-backed evidence.
argument-hint: artifact path, workflow, or evidence request
---
Use Gantry artifact flow when evidence must be durable.

Required sequence:
1. Write artifact content to session artifact FS.
2. Publish artifact to workflow artifact store.
3. Attach `artifact://` URI in task evidence updates.
4. Confirm references are stable and reviewable.

Do not claim artifact evidence if publish fails.
