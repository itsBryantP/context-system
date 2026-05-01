import type { Plugin, PluginInput } from "@opencode-ai/plugin";
import {
  GANTRY_GUIDANCE,
  buildHubAuthHeaders,
  discoverAutoHubTarget,
  discoverWakeGSIDTargets,
  formatTemplate,
  loadCommands,
  loadReactions,
  matchReaction
} from "./vendor.ts";

type OpenCodeClient = PluginInput["client"];

export interface SessionEventSensitivity {
  mailbox: boolean;
  broadcasts: boolean;
  tasks: boolean;
  workflows: boolean;
}

interface SessionControls {
  event_sensitivity?: Partial<SessionEventSensitivity>;
}

interface SessionMessagePart {
  id?: string;
  type?: string;
  text?: string;
}

interface SessionMessageLike {
  parts?: SessionMessagePart[];
}

interface WakeEnvelope {
  type: string;
  properties?: Record<string, unknown>;
}

interface WakeQueueItem {
  wake: WakeEnvelope;
  dedupeKey: string;
}

interface ReactionSessionContext {
  model?: { providerID: string; modelID: string };
  agent?: string;
}

interface ReactionPromptPayload {
  [key: string]: unknown;
  event: {
    type: string;
    source: string | undefined;
    properties: Record<string, unknown>;
  };
  session: {
    id: string;
    agent: string | undefined;
    modelProvider: string | undefined;
    modelID: string | undefined;
  };
  reaction: {
    name: string;
  };
}

async function getSessionContext(client: OpenCodeClient, sessionID: string): Promise<{
  model?: { providerID: string; modelID: string };
  agent?: string;
}> {
  try {
    const response = await client.session.messages({
      path: { id: sessionID },
      query: { limit: 50 }
    });
    const data = response.data ?? [];
    for (const message of data) {
      if (message.info.role === "user" && "model" in message.info && message.info.model) {
        return { model: message.info.model, agent: message.info.agent };
      }
    }
  } catch {
  }
  return {};
}

export function buildReactionPromptPayload(
  event: { type: string; properties?: Record<string, unknown> },
  source: string | undefined,
  sessionID: string,
  context: ReactionSessionContext,
  reactionName: string
): ReactionPromptPayload {
  return {
    event: {
      type: event.type,
      source,
      properties: event.properties ?? {}
    },
    session: {
      id: sessionID,
      agent: context.agent,
      modelProvider: context.model?.providerID,
      modelID: context.model?.modelID
    },
    reaction: {
      name: reactionName
    }
  };
}

async function hasInjectedContext(client: OpenCodeClient, sessionID: string): Promise<boolean> {
  try {
    const existing = await client.session.messages({ path: { id: sessionID }, query: { limit: 20 } });
    const data = existing.data ?? [];
    for (const message of data) {
      const parts = message.parts ?? [];
      for (const part of parts) {
        if (part.type === "text" && part.text?.includes("<gantry-context version=\"1\">")) {
          return true;
        }
      }
    }
  } catch {
  }
  return false;
}

async function injectContext(
  client: OpenCodeClient,
  sessionID: string,
  context?: {
    model?: { providerID: string; modelID: string };
    agent?: string;
  }
): Promise<void> {
  try {
    await client.session.prompt({
      path: { id: sessionID },
      body: {
        noReply: true,
        model: context?.model,
        agent: context?.agent,
        parts: [{ type: "text", text: GANTRY_GUIDANCE, synthetic: true }]
      }
    });
  } catch {
  }
}

export function defaultEventSensitivity(): SessionEventSensitivity {
  return {
    mailbox: true,
    broadcasts: false,
    tasks: false,
    workflows: false
  };
}

export function mergeEventSensitivity(input?: Partial<SessionEventSensitivity>): SessionEventSensitivity {
  const defaults = defaultEventSensitivity();
  return {
    mailbox: true,
    broadcasts: Boolean(input?.broadcasts),
    tasks: Boolean(input?.tasks),
    workflows: Boolean(input?.workflows)
  };
}

export function parseSessionControls(text: string): SessionControls | null {
  const match = text.match(/<gantry-session-controls>([\s\S]*?)<\/gantry-session-controls>/i);
  if (!match || !match[1]) {
    return null;
  }
  try {
    return JSON.parse(match[1].trim()) as SessionControls;
  } catch {
    return null;
  }
}

async function getSessionEventSensitivity(client: OpenCodeClient, sessionID: string, cache?: Map<string, SessionEventSensitivity>): Promise<SessionEventSensitivity> {
  if (cache) {
    const cached = cache.get(sessionID);
    if (cached) {
      return cached;
    }
  }

  let result = defaultEventSensitivity();
  try {
    const response = await client.session.messages({ path: { id: sessionID }, query: { limit: 50 } });
    const data = response.data ?? [];
    for (const message of data) {
      const parts = message.parts ?? [];
      for (const part of parts) {
        if (part.type !== "text" || !part.text) {
          continue;
        }
        const controls = parseSessionControls(part.text);
        if (!controls) {
          continue;
        }
        result = mergeEventSensitivity(controls.event_sensitivity);
        break;
      }
    }
  } catch {
  }

  if (cache) {
    cache.set(sessionID, result);
  }
  return result;
}

export function allowsEventSensitivity(eventType: string, source: string | undefined, sensitivity: SessionEventSensitivity): boolean {
  if (source === "mailbox") {
    return true;
  }
  if (source === "reactor") {
    return sensitivity.broadcasts || sensitivity.tasks || sensitivity.workflows;
  }
  if (eventType.startsWith("broadcast.")) {
    return sensitivity.broadcasts;
  }
  if (eventType.startsWith("task.")) {
    return sensitivity.tasks;
  }
  if (eventType.startsWith("workflow.")) {
    return sensitivity.workflows;
  }
  return false;
}

export function parseWakeEnvelope(text: string): WakeEnvelope | null {
  const match = text.match(/<gantry-wake[^>]*>([\s\S]*?)<\/gantry-wake>/i);
  if (!match || !match[1]) {
    return null;
  }
  const body = match[1].trim();
  if (!body.startsWith("{")) {
    return null;
  }
  try {
    const parsed = JSON.parse(body) as { type?: string; properties?: Record<string, unknown> };
    if (!parsed.type || typeof parsed.type !== "string") {
      return null;
    }
    return { type: parsed.type, properties: parsed.properties ?? {} };
  } catch {
    return null;
  }
}

export function collectPendingWakeQueue(
  messages: SessionMessageLike[],
  sessionID: string,
  processedWakeKeys: ReadonlySet<string> | ReadonlyMap<string, number>
): WakeQueueItem[] {
  const wakeQueue: WakeQueueItem[] = [];
  for (const message of messages) {
    const parts = message.parts ?? [];
    for (const part of parts) {
      if (part.type !== "text" || !part.text) {
        continue;
      }
      const wake = parseWakeEnvelope(part.text);
      if (!wake) {
        continue;
      }
      const idemRaw = wake.properties?.idempotency_key;
      const idempotencyKey = typeof idemRaw === "string" ? idemRaw : "";
      const partID = typeof part.id === "string" ? part.id : "";
      const dedupeToken = idempotencyKey || partID;
      if (!dedupeToken) {
        continue;
      }
      const dedupeKey = `${sessionID}|${wake.type}|${dedupeToken}`;
      if (processedWakeKeys.has(dedupeKey)) {
        continue;
      }
      wakeQueue.push({ wake, dedupeKey });
    }
  }
  return wakeQueue;
}
export const GantryPlugin: Plugin = async ({ client }) => {
  const injectedSessions = new Set<string>();
  const processedWakeKeys = new Map<string, number>();
  const sensitivityCache = new Map<string, SessionEventSensitivity>();
  const wakeKeyTTLms = 10 * 60 * 1000;
  const wakeKeyMaxEntries = 2000;
  const commands = await loadCommands();
  const reactions = await loadReactions();
  const gsidDiscovery = await discoverWakeGSIDTargets();
  const gsidTargets = new Set(gsidDiscovery.targets.map((item) => item.trim()).filter((item) => item.length > 0));
  const wakeHubURLOverride = (process.env.GANTRY_WAKE_HUB_URL ?? "").trim();
  const wakeHubProjectOverride = (process.env.GANTRY_WAKE_PROJECT_ID ?? "").trim();

  const autoHub = await discoverAutoHubTarget();
  const wakeHubURL = wakeHubURLOverride || autoHub?.url || "http://127.0.0.1:8450";
  const wakeHubProject = wakeHubProjectOverride || autoHub?.projectID || "";
  const wakeHubSource = wakeHubURLOverride
    ? "env:GANTRY_WAKE_HUB_URL"
    : autoHub?.source ?? "default:http://127.0.0.1:8450";
  const wakeHubEnabled = Boolean(wakeHubURL);

  if (wakeHubEnabled) {
    console.log(`[gantry-plugin] wake hub auto-connect enabled: ${wakeHubURL} source=${wakeHubSource} project=${wakeHubProject || ""}`);
  }
  console.log(
    `[gantry-plugin] wake gsid targets=${Array.from(gsidTargets).join(",") || "none"} source=${gsidDiscovery.source}`
  );

  async function processHubWakeEvent(event: {
    type?: string;
    properties?: Record<string, unknown>;
  }): Promise<void> {
    if (!event || event.type !== "gantry.wake") {
      return;
    }
    if (gsidTargets.size === 0) {
      return;
    }
    const target = String(event.properties?.sessionID ?? "").trim();
    if (!target || !gsidTargets.has(target)) {
      return;
    }

    await runEventReactions({
      type: "gantry.wake",
      properties: event.properties,
    });
  }

  async function pollWakeHub(): Promise<void> {
    if (!wakeHubEnabled || gsidTargets.size === 0) {
      return;
    }
    let lastEventID = "";
    let failures = 0;
    while (true) {
      const streamURL = `${wakeHubURL.replace(/\/$/, "")}/api/v1/events/stream${wakeHubProject ? `?project_id=${encodeURIComponent(wakeHubProject)}` : ""}`;
      try {
        const parsedStreamURL = new URL(streamURL);
        const requestTarget = `${parsedStreamURL.pathname}${parsedStreamURL.search}`;
        const headers: Record<string, string> = {
          Accept: "text/event-stream"
        };
        const auth = await buildHubAuthHeaders(requestTarget);
        if (auth) {
          Object.assign(headers, auth.headers);
        }
        if (lastEventID) {
          headers["Last-Event-ID"] = lastEventID;
        }
        const response = await fetch(streamURL, { headers });
        if (!response.ok || !response.body) {
          throw new Error(`wake hub stream HTTP ${response.status}`);
        }
        failures = 0;
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let eventType = "";
        let eventData = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const lineRaw of lines) {
            const line = lineRaw.replace(/\r$/, "");
            if (!line) {
              if (eventType === "gantry.wake" && eventData) {
                try {
                  const payload = JSON.parse(eventData) as { type?: string; properties?: Record<string, unknown> };
                  await processHubWakeEvent(payload);
                } catch {
                }
              }
              eventType = "";
              eventData = "";
              continue;
            }
            if (line.startsWith(":") || line.startsWith("retry:")) {
              continue;
            }
            if (line.startsWith("id:")) {
              lastEventID = line.slice(3).trim();
              continue;
            }
            if (line.startsWith("event:")) {
              eventType = line.slice(6).trim();
              continue;
            }
            if (line.startsWith("data:")) {
              const part = line.slice(5).trimStart();
              eventData = eventData ? `${eventData}\n${part}` : part;
            }
          }
        }
      } catch {
        failures += 1;
      }
      const delay = Math.min(10000, 500 * 2 ** Math.min(failures, 5));
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  if (wakeHubEnabled && gsidTargets.size > 0) {
    void pollWakeHub();
  }

  function pruneWakeKeys(now: number): void {
    for (const [key, ts] of processedWakeKeys.entries()) {
      if (now-ts > wakeKeyTTLms) {
        processedWakeKeys.delete(key);
      }
    }
    if (processedWakeKeys.size <= wakeKeyMaxEntries) {
      return;
    }
    const entries = Array.from(processedWakeKeys.entries()).sort((a, b) => a[1] - b[1]);
    const toDrop = processedWakeKeys.size - wakeKeyMaxEntries;
    for (let i = 0; i < toDrop; i += 1) {
      const entry = entries[i];
      if (!entry) {
        break;
      }
      processedWakeKeys.delete(entry[0]);
    }
  }

  async function postReactionPrompt(
    sessionID: string,
    prompt: string,
    context?: {
      model?: { providerID: string; modelID: string };
      agent?: string;
    },
    noReply = false
  ): Promise<void> {
    if (!prompt.trim()) {
      return;
    }
    try {
      await client.session.prompt({
        path: { id: sessionID },
        body: {
          noReply,
          model: context?.model,
          agent: context?.agent,
          parts: [{ type: "text", text: prompt, synthetic: true }]
        }
      });
    } catch {
    }
  }

  async function runEventReactions(event: {
    type: string;
    properties?: Record<string, unknown>;
  }): Promise<void> {
    const sessionIDRaw = event.properties?.sessionID;
    const sessionID = typeof sessionIDRaw === "string" ? sessionIDRaw : String(sessionIDRaw ?? "");
    if (!sessionID) {
      return;
    }

    const sourceRaw = event.properties?.source;
    const source = typeof sourceRaw === "string" ? sourceRaw : undefined;
    const context = await getSessionContext(client, sessionID);
    const sensitivity = await getSessionEventSensitivity(client, sessionID, sensitivityCache);
    if (!allowsEventSensitivity(event.type, source, sensitivity)) {
      return;
    }

    for (const reaction of reactions) {
      if (!matchReaction(reaction, event.type, source)) {
        continue;
      }
      const payload = buildReactionPromptPayload(event, source, sessionID, context, reaction.name);
      const prompt = formatTemplate(reaction.template, payload);
      await postReactionPrompt(sessionID, prompt, context, reaction.noReply);
    }
  }

  async function processWakeFromSession(sessionID: string): Promise<void> {
    try {
      pruneWakeKeys(Date.now());
      const response = await client.session.messages({
        path: { id: sessionID },
        query: { limit: 10 }
      });
      const data = response.data ?? [];
      const wakeQueue = collectPendingWakeQueue(data, sessionID, processedWakeKeys);

      for (const item of wakeQueue) {
        if (processedWakeKeys.has(item.dedupeKey)) {
          continue;
        }
        // Claim the wake key before posting reaction prompts so nested
        // synthetic prompts do not re-enter and recursively replay the same wake.
        processedWakeKeys.set(item.dedupeKey, Date.now());
        try {
          await runEventReactions(item.wake);
        } catch {
          processedWakeKeys.delete(item.dedupeKey);
          throw new Error("wake reaction failed");
        }
      }
    } catch {
    }
  }

  function getEventSessionID(properties?: Record<string, unknown>): string {
    if (!properties) {
      return "";
    }
    const direct = properties.sessionID;
    if (typeof direct === "string" && direct) {
      return direct;
    }
    const info = properties.info;
    if (info && typeof info === "object") {
      const maybe = (info as Record<string, unknown>).sessionID;
      if (typeof maybe === "string" && maybe) {
        return maybe;
      }
    }
    return "";
  }

  return {
    "chat.message": async (_input, output) => {
      const sessionID = output.message.sessionID;
      if (reactions.length > 0) {
        await processWakeFromSession(sessionID);
      }
      if (injectedSessions.has(sessionID)) {
        return;
      }

      if (await hasInjectedContext(client, sessionID)) {
        injectedSessions.add(sessionID);
        return;
      }

      injectedSessions.add(sessionID);
      await injectContext(client, sessionID, {
        model: output.message.model,
        agent: output.message.agent
      });
    },

    event: async ({ event }) => {
      if (event.type === "session.compacted") {
        const sessionID = String(event.properties.sessionID ?? "");
        if (!sessionID) {
          return;
        }
        const context = await getSessionContext(client, sessionID);
        await injectContext(client, sessionID, context);
      }

      const eventSessionID = getEventSessionID((event.properties ?? {}) as Record<string, unknown>);
      if (eventSessionID && reactions.length > 0) {
        await processWakeFromSession(eventSessionID);
      }

      if (reactions.length > 0) {
        await runEventReactions({
          type: event.type,
          properties: (event.properties ?? {}) as Record<string, unknown>
        });
      }
    },

    config: async (config) => {
      config.command = { ...(config.command ?? {}), ...(commands ?? {}) };
    }
  };
};
