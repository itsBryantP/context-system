import test from "node:test";
import assert from "node:assert/strict";
import * as fs from "node:fs/promises";
import * as os from "node:os";
import * as path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createHash, createVerify, X509Certificate } from "node:crypto";

import {
  buildReactionPromptPayload,
  collectPendingWakeQueue,
  allowsEventSensitivity,
  defaultEventSensitivity,
  mergeEventSensitivity,
  parseSessionControls,
  parseWakeEnvelope,
} from "./plugin.ts";
import {
  selectAutoHubTargetFromConfig,
  buildHubAuthHeaders,
  formatTemplate,
  matchReaction,
  type ReactionRule,
} from "./vendor.ts";

// ── formatTemplate ──

test("formatTemplate substitutes top-level keys", () => {
  assert.equal(
    formatTemplate("hello {name}", { name: "world" }),
    "hello world"
  );
});

test("formatTemplate substitutes nested path keys", () => {
  assert.equal(
    formatTemplate("{event.properties.idempotency_key}", {
      event: { properties: { idempotency_key: "mail:msg-1" } },
    }),
    "mail:msg-1"
  );
});

test("formatTemplate substitutes array values as JSON", () => {
  assert.equal(
    formatTemplate("refs={event.properties.refs}", {
      event: { properties: { refs: ["a", "b"] } },
    }),
    'refs=["a","b"]'
  );
});

test("formatTemplate substitutes number values", () => {
  assert.equal(
    formatTemplate("priority={event.properties.priority}", {
      event: { properties: { priority: 42 } },
    }),
    "priority=42"
  );
});

test("formatTemplate substitutes boolean values", () => {
  assert.equal(
    formatTemplate("flag={event.properties.enabled}", {
      event: { properties: { enabled: true } },
    }),
    "flag=true"
  );
});

test("formatTemplate returns empty string for null values", () => {
  assert.equal(
    formatTemplate("value={event.properties.missing}", {
      event: { properties: { missing: null } },
    }),
    "value="
  );
});

test("formatTemplate returns empty string for undefined keypath", () => {
  assert.equal(
    formatTemplate("value={event.nonexistent.deep.path}", {
      event: { properties: {} },
    }),
    "value="
  );
});

test("formatTemplate handles nested objects as JSON", () => {
  assert.equal(
    formatTemplate("inline={event.properties.inline_data}", {
      event: {
        properties: {
          inline_data: { message_id: "msg-1", from: "sender" },
        },
      },
    }),
    'inline={"message_id":"msg-1","from":"sender"}'
  );
});

test("formatTemplate handles multiple placeholders in one template", () => {
  assert.equal(
    formatTemplate("[{event.properties.priority}] {event.properties.source}: {event.properties.summary}", {
      event: { properties: { priority: "high", source: "mailbox", summary: "new message from sender" } },
    }),
    "[high] mailbox: new message from sender"
  );
});

test("formatTemplate dot-separated key lookup handles missing intermediate objects", () => {
  assert.equal(
    formatTemplate("{a.b.c}", { a: null }),
    ""
  );
});

// ── matchReaction ──

test("matchReaction matches exact event type", () => {
  const rule: ReactionRule = {
    name: "test",
    event: "gantry.wake",
    template: "hello",
    noReply: false,
  };
  assert.equal(matchReaction(rule, "gantry.wake"), true);
  assert.equal(matchReaction(rule, "task.created"), false);
});

test("matchReaction gates on source when rule has source filter", () => {
  const rule: ReactionRule = {
    name: "mailbox-only",
    event: "gantry.wake",
    source: "mailbox",
    template: "hello",
    noReply: true,
  };
  assert.equal(matchReaction(rule, "gantry.wake", "mailbox"), true);
  assert.equal(matchReaction(rule, "gantry.wake", "reactor"), false);
  assert.equal(matchReaction(rule, "gantry.wake"), false); // missing source → no match when rule has source
});

test("matchReaction matches any source when rule has no source filter", () => {
  const rule: ReactionRule = {
    name: "any-source",
    event: "gantry.wake",
    template: "hello",
    noReply: false,
  };
  assert.equal(matchReaction(rule, "gantry.wake", "mailbox"), true);
  assert.equal(matchReaction(rule, "gantry.wake", "reactor"), true);
  assert.equal(matchReaction(rule, "gantry.wake"), true);
});

test("matchReaction rejects different event type regardless of source", () => {
  const rule: ReactionRule = {
    name: "wake-only",
    event: "gantry.wake",
    template: "hello",
    noReply: false,
  };
  assert.equal(matchReaction(rule, "task.completed", "mailbox"), false);
});

// ── parseSessionControls ──

test("parseSessionControls returns null for non-matching text", () => {
  assert.equal(parseSessionControls("no controls here"), null);
  assert.equal(parseSessionControls('<gantry-session-controls>'), null);
});

test("parseSessionControls returns null for invalid JSON", () => {
  assert.equal(
    parseSessionControls("<gantry-session-controls>not json</gantry-session-controls>"),
    null
  );
});

test("parseSessionControls handles case-insensitive tags", () => {
  const controls = parseSessionControls(
    '<Gantry-Session-Controls>{"event_sensitivity":{"mailbox":true}}</Gantry-Session-Controls>'
  );
  assert.deepEqual(controls, {
    event_sensitivity: {
      mailbox: true,
    },
  });
});

test("parseSessionControls handles multiline JSON body", () => {
  const controls = parseSessionControls(
    `<gantry-session-controls>
{
  "event_sensitivity": {
    "mailbox": false
  }
}
</gantry-session-controls>`
  );
  assert.deepEqual(controls, {
    event_sensitivity: {
      mailbox: false,
    },
  });
});

test("parseSessionControls returns null for empty JSON after trim", () => {
  assert.equal(
    parseSessionControls(`<gantry-session-controls>

</gantry-session-controls>`),
    null
  );
});

test("parseSessionControls extracts only first controls block", () => {
  const controls = parseSessionControls(
    `<gantry-session-controls>{"event_sensitivity":{"mailbox":true,"tasks":true}}</gantry-session-controls>
<gantry-session-controls>{"event_sensitivity":{"broadcasts":true}}</gantry-session-controls>`
  );
  assert.deepEqual(controls, {
    event_sensitivity: {
      mailbox: true,
      tasks: true,
    },
  });
});

// ── parseWakeEnvelope ──

test("parseWakeEnvelope returns null for non-matching text", () => {
  assert.equal(parseWakeEnvelope("no wake here"), null);
  assert.equal(parseWakeEnvelope("<gantry-wake>"), null);
});

test("parseWakeEnvelope returns null for non-JSON body", () => {
  assert.equal(
    parseWakeEnvelope("<gantry-wake>not json</gantry-wake>"),
    null
  );
});

test("parseWakeEnvelope returns null for empty type", () => {
  assert.equal(
    parseWakeEnvelope('<gantry-wake>{"type":"","properties":{}}</gantry-wake>'),
    null
  );
});

test("parseWakeEnvelope returns null when type field is missing", () => {
  assert.equal(
    parseWakeEnvelope('<gantry-wake>{"properties":{"x":1}}</gantry-wake>'),
    null
  );
});

test("parseWakeEnvelope handles version attribute on envelope tag", () => {
  assert.deepEqual(
    parseWakeEnvelope(
      '<gantry-wake version="1" priority="high">{"type":"gantry.wake","properties":{"source":"reactor"}}</gantry-wake>'
    ),
    {
      type: "gantry.wake",
      properties: { source: "reactor" },
    }
  );
});

test("parseWakeEnvelope defaults properties to empty object", () => {
  assert.deepEqual(
    parseWakeEnvelope('<gantry-wake>{"type":"gantry.wake"}</gantry-wake>'),
    { type: "gantry.wake", properties: {} }
  );
});

// ── collectPendingWakeQueue ──

test("collectPendingWakeQueue returns empty queue for messages without wake envelopes", () => {
  const queue = collectPendingWakeQueue(
    [{ parts: [{ id: "p1", type: "text", text: "hello" }] }],
    "sess-1",
    new Set<string>()
  );
  assert.equal(queue.length, 0);
});

test("collectPendingWakeQueue returns empty queue for empty messages array", () => {
  const queue = collectPendingWakeQueue([], "sess-1", new Set<string>());
  assert.equal(queue.length, 0);
});

test("collectPendingWakeQueue skips messages with no text parts", () => {
  const queue = collectPendingWakeQueue(
    [{ parts: [{ id: "p1", type: "image" }] }],
    "sess-1",
    new Set<string>()
  );
  assert.equal(queue.length, 0);
});

test("collectPendingWakeQueue skips items already in processed set", () => {
  const queue = collectPendingWakeQueue(
    [
      {
        parts: [
          {
            id: "p1",
            type: "text",
            text: '<gantry-wake>{"type":"gantry.wake","properties":{"idempotency_key":"mail:a"}}</gantry-wake>',
          },
        ],
      },
    ],
    "sess-1",
    new Set<string>(["sess-1|gantry.wake|mail:a"])
  );
  assert.equal(queue.length, 0);
});

test("collectPendingWakeQueue skips items with no dedupe token (no idempotency key, no part id)", () => {
  const queue = collectPendingWakeQueue(
    [
      {
        parts: [
          {
            type: "text",
            text: '<gantry-wake>{"type":"gantry.wake","properties":{}}</gantry-wake>',
          },
        ],
      },
    ],
    "sess-1",
    new Set<string>()
  );
  assert.equal(queue.length, 0);
});

test("collectPendingWakeQueue queues multiple wake envelopes from same message", () => {
  const queue = collectPendingWakeQueue(
    [
      {
        parts: [
          {
            id: "p1",
            type: "text",
            text: '<gantry-wake>{"type":"gantry.wake","properties":{"idempotency_key":"mail:a"}}</gantry-wake>',
          },
          {
            id: "p2",
            type: "text",
            text: '<gantry-wake>{"type":"gantry.wake","properties":{"idempotency_key":"mail:b"}}</gantry-wake>',
          },
        ],
      },
    ],
    "sess-1",
    new Set<string>()
  );
  assert.equal(queue.length, 2);
  assert.equal(queue[0]?.dedupeKey, "sess-1|gantry.wake|mail:a");
  assert.equal(queue[1]?.dedupeKey, "sess-1|gantry.wake|mail:b");
});

test("collectPendingWakeQueue handles Map as processed keys container", () => {
  const processed = new Map<string, number>();
  processed.set("sess-1|gantry.wake|mail:old", Date.now());
  const queue = collectPendingWakeQueue(
    [
      {
        parts: [
          {
            id: "p1",
            type: "text",
            text: '<gantry-wake>{"type":"gantry.wake","properties":{"idempotency_key":"mail:new"}}</gantry-wake>',
          },
        ],
      },
    ],
    "sess-1",
    processed
  );
  assert.equal(queue.length, 1);
  assert.equal(queue[0]?.dedupeKey, "sess-1|gantry.wake|mail:new");
});

test("collectPendingWakeQueue ignores non-text and text-less parts", () => {
  const queue = collectPendingWakeQueue(
    [
      {
        parts: [
          { id: "p1", type: "image" },
          { id: "p2", type: "text" },
          {
            id: "p3",
            type: "text",
            text: '<gantry-wake>{"type":"gantry.wake","properties":{"idempotency_key":"mail:x"}}</gantry-wake>',
          },
        ],
      },
    ],
    "sess-1",
    new Set<string>()
  );
  assert.equal(queue.length, 1);
  assert.equal(queue[0]?.dedupeKey, "sess-1|gantry.wake|mail:x");
});

// ── buildReactionPromptPayload ──

test("buildReactionPromptPayload handles undefined source", () => {
  const payload = buildReactionPromptPayload(
    { type: "gantry.wake", properties: { sessionID: "s1" } },
    undefined,
    "s1",
    {},
    "test-reaction"
  );
  assert.equal(payload.event.source, undefined);
  assert.equal(payload.reaction.name, "test-reaction");
});

test("buildReactionPromptPayload handles missing model context", () => {
  const payload = buildReactionPromptPayload(
    { type: "gantry.wake", properties: {} },
    "mailbox",
    "s1",
    {},
    "test-reaction"
  );
  assert.equal(payload.session.modelProvider, undefined);
  assert.equal(payload.session.modelID, undefined);
  assert.equal(payload.session.agent, undefined);
});

// ── mergeEventSensitivity ──

test("mergeEventSensitivity returns defaults when input is undefined", () => {
  assert.deepEqual(mergeEventSensitivity(undefined), {
    mailbox: true,
    broadcasts: false,
    tasks: false,
    workflows: false,
  });
});

test("mergeEventSensitivity treats falsy booleans correctly", () => {
  assert.deepEqual(
    mergeEventSensitivity({ mailbox: false, broadcasts: false }),
    {
      mailbox: true, // mailbox always enabled
      broadcasts: false,
      tasks: false,
      workflows: false,
    }
  );
});

// ── allowsEventSensitivity ──

test("allowsEventSensitivity allows mailbox source unconditionally", () => {
  const off = { mailbox: true, broadcasts: false, tasks: false, workflows: false };
  assert.equal(allowsEventSensitivity("gantry.wake", "mailbox", off), true);
  assert.equal(allowsEventSensitivity("mail.sent", "mailbox", off), true);
});

test("allowsEventSensitivity gates reactor source on broadcast/task/workflow flags", () => {
  const onlyBroadcasts = mergeEventSensitivity({ broadcasts: true });
  assert.equal(allowsEventSensitivity("gantry.wake", "reactor", onlyBroadcasts), true);

  const onlyTasks = mergeEventSensitivity({ tasks: true });
  assert.equal(allowsEventSensitivity("gantry.wake", "reactor", onlyTasks), true);

  const onlyWorkflows = mergeEventSensitivity({ workflows: true });
  assert.equal(allowsEventSensitivity("gantry.wake", "reactor", onlyWorkflows), true);

  const allOff = defaultEventSensitivity();
  assert.equal(allowsEventSensitivity("gantry.wake", "reactor", allOff), false);
});

test("allowsEventSensitivity gates broadcast events on broadcasts flag", () => {
  const enabled = mergeEventSensitivity({ broadcasts: true });
  assert.equal(allowsEventSensitivity("broadcast.build", undefined, enabled), true);
  assert.equal(allowsEventSensitivity("broadcast.alert", undefined, enabled), true);

  const disabled = defaultEventSensitivity();
  assert.equal(allowsEventSensitivity("broadcast.build", undefined, disabled), false);
});

test("allowsEventSensitivity gates task events on tasks flag", () => {
  const enabled = mergeEventSensitivity({ tasks: true });
  assert.equal(allowsEventSensitivity("task.created", undefined, enabled), true);

  const disabled = defaultEventSensitivity();
  assert.equal(allowsEventSensitivity("task.created", undefined, disabled), false);
});

test("allowsEventSensitivity gates workflow events on workflows flag", () => {
  const enabled = mergeEventSensitivity({ workflows: true });
  assert.equal(allowsEventSensitivity("workflow.completed", undefined, enabled), true);

  const disabled = defaultEventSensitivity();
  assert.equal(allowsEventSensitivity("workflow.completed", undefined, disabled), false);
});

test("allowsEventSensitivity rejects unknown event types", () => {
  assert.equal(
    allowsEventSensitivity("unknown.event", undefined, mergeEventSensitivity({ broadcasts: true, tasks: true, workflows: true })),
    false
  );
});

// ── selectAutoHubTargetFromConfig ──

test("selectAutoHubTargetFromConfig returns null for empty config", () => {
  assert.equal(selectAutoHubTargetFromConfig({}), null);
});

test("selectAutoHubTargetFromConfig returns null when no hub links or hub_url", () => {
  assert.equal(
    selectAutoHubTargetFromConfig({ federation: { links: [] } }),
    null
  );
});

test("selectAutoHubTargetFromConfig picks plain hub link when no opencode-tagged links", () => {
  const target = selectAutoHubTargetFromConfig({
    project: "gantry",
    federation: {
      links: [
        { kind: "hub", url: "https://first.example", project_id: "p-a" },
        { kind: "hub", url: "https://second.example" },
      ],
    },
  });
  assert.deepEqual(target, {
    url: "https://first.example",
    projectID: "p-a",
    source: "gantry.yaml:federation.links[kind=hub]",
  });
});

test("selectAutoHubTargetFromConfig ignores non-hub link kinds", () => {
  assert.equal(
    selectAutoHubTargetFromConfig({
      federation: {
        links: [{ kind: "something-else", url: "https://example" }],
      },
    }),
    null
  );
});

test("selectAutoHubTargetFromConfig handles string tags comma-separated", () => {
  const target = selectAutoHubTargetFromConfig({
    project: "gantry",
    federation: {
      links: [
        {
          kind: "hub",
          url: "https://tagged-hub.example",
          project_id: "proj-t",
          tags: "team-a, opencode-session-hub",
        },
      ],
    },
  });
  assert.deepEqual(target, {
    url: "https://tagged-hub.example",
    projectID: "proj-t",
    source: "gantry.yaml:federation.links[tag=opencode-session-hub]",
  });
});

test("selectAutoHubTargetFromConfig hub_url fallback uses project from config", () => {
  const target = selectAutoHubTargetFromConfig({
    project: "my-project",
    federation: { hub_url: "https://hub.example" },
  });
  assert.deepEqual(target, {
    url: "https://hub.example",
    projectID: "my-project",
    source: "gantry.yaml:federation.hub_url",
  });
});

test("selectAutoHubTargetFromConfig hub_url fallback without project", () => {
  const target = selectAutoHubTargetFromConfig({
    federation: { hub_url: "https://hub.example" },
  });
  assert.deepEqual(target, {
    url: "https://hub.example",
    projectID: undefined,
    source: "gantry.yaml:federation.hub_url",
  });
});

test("selectAutoHubTargetFromConfig skips links with empty url", () => {
  const target = selectAutoHubTargetFromConfig({
    project: "gantry",
    federation: {
      links: [
        { kind: "hub", url: "" },
        { kind: "hub", url: "https://valid.example", project_id: "p-z" },
      ],
    },
  });
  assert.deepEqual(target, {
    url: "https://valid.example",
    projectID: "p-z",
    source: "gantry.yaml:federation.links[kind=hub]",
  });
});

const execFileAsync = promisify(execFile);

async function writeFactoryIdentity(dir: string): Promise<string> {
  const workspace = path.join(dir, ".agf-workspace");
  await fs.mkdir(workspace);
  const keyPath = path.join(workspace, "factory.key");
  const certPath = path.join(workspace, "factory.cert");
  await execFileAsync("openssl", [
    "ecparam",
    "-name",
    "prime256v1",
    "-genkey",
    "-noout",
    "-out",
    keyPath,
  ]);
  await execFileAsync("openssl", [
    "req",
    "-new",
    "-x509",
    "-key",
    keyPath,
    "-out",
    certPath,
    "-subj",
    "/CN=gantry-plugin-test",
    "-days",
    "365",
  ]);
  return fs.readFile(certPath, "utf-8");
}

test("buildHubAuthHeaders signs hub SSE requests with workspace factory identity", async () => {
  const tmp = await fs.mkdtemp(path.join(os.tmpdir(), "gantry-plugin-auth-"));
  const oldCwd = process.cwd();
  try {
    const certPEM = await writeFactoryIdentity(tmp);
    process.chdir(tmp);

    const result = await buildHubAuthHeaders("/api/v1/events/stream?project_id=z-accelerator");
    assert.ok(result);
    assert.equal(result.source, ".agf-workspace/factory.key");

    const cert = new X509Certificate(certPEM);
    const expectedFingerprint = Array.from(createHash("sha256").update(cert.raw).digest())
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join(":");
    assert.equal(result.headers["X-AGF-Fingerprint"], expectedFingerprint);
    assert.match(result.headers["X-AGF-Timestamp"] ?? "", /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
    assert.match(result.headers["X-AGF-Nonce"] ?? "", /^[0-9a-f]{32}$/);

    const emptyBodyHash = createHash("sha256").update(Buffer.alloc(0)).digest("hex");
    const canonical = [
      "GET",
      "/api/v1/events/stream?project_id=z-accelerator",
      result.headers["X-AGF-Timestamp"],
      result.headers["X-AGF-Nonce"],
      emptyBodyHash,
    ].join("\n");
    const verifier = createVerify("sha256");
    verifier.update(canonical);
    verifier.end();
    assert.equal(verifier.verify(cert.publicKey, result.headers["X-AGF-Signature"] ?? "", "base64"), true);
  } finally {
    process.chdir(oldCwd);
    await fs.rm(tmp, { recursive: true, force: true });
  }
});
