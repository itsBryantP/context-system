import * as fs from "node:fs/promises";
import * as path from "node:path";
import { createHash, randomBytes, sign, X509Certificate } from "node:crypto";
import { fileURLToPath } from "node:url";
import type { Config } from "@opencode-ai/plugin";

export interface AutoHubTarget {
  url: string;
  projectID?: string;
  source: string;
}

export interface WakeGSIDDiscovery {
  targets: string[];
  source: string;
}

export interface HubAuthHeaders {
  headers: Record<string, string>;
  source: string;
}

interface ParsedMarkdown {
  frontmatter: Record<string, string | undefined>;
  body: string;
}

export interface ReactionRule {
  name: string;
  event: string;
  template: string;
  source?: string;
  noReply: boolean;
}

interface ReactionConfigFile {
  reactions?: unknown;
}

export const GANTRY_GUIDANCE = `<gantry-context version="1">
You are operating in a Gantry-coordinated workflow.

Execution protocol:
- Claim the assigned task before substantive work.
- Keep notes concise and decision-oriented as work progresses.
- Attach evidence and commit references for code changes.
- Broadcast meaningful results for gated outcomes.
- Complete the task with outcome-focused summary and changed files.
</gantry-context>`;

const USER_REACTIONS_ENV = "GANTRY_OPENCODE_REACTIONS";

function getVendorDir(): string {
  const dirname = path.dirname(fileURLToPath(import.meta.url));
  return path.join(dirname, "..", "vendor");
}

function parseMarkdownWithFrontmatter(content: string): ParsedMarkdown | null {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!match) {
    return null;
  }

  const frontmatterText = match[1];
  const body = match[2];
  if (frontmatterText === undefined || body === undefined) {
    return null;
  }

  const frontmatter: Record<string, string | undefined> = {};
  for (const rawLine of frontmatterText.split("\n")) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) {
      continue;
    }
    const idx = line.indexOf(":");
    if (idx === -1) {
      continue;
    }
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (value === "[]") {
      value = "";
    }
    frontmatter[key] = value;
  }

  return { frontmatter, body: body.trim() };
}

async function readVendorFile(relativePath: string): Promise<string | null> {
  try {
    return await fs.readFile(path.join(getVendorDir(), relativePath), "utf-8");
  } catch {
    return null;
  }
}

async function listVendorFiles(relativePath: string): Promise<string[]> {
  try {
    return await fs.readdir(path.join(getVendorDir(), relativePath));
  } catch {
    return [];
  }
}

function parseBool(input: string | undefined, defaultValue: boolean): boolean {
  if (!input) {
    return defaultValue;
  }
  return input.trim().toLowerCase() === "true";
}

function parseReactionFromMarkdown(file: string, content: string): ReactionRule | null {
  const parsed = parseMarkdownWithFrontmatter(content);
  if (!parsed) {
    return null;
  }

  const event = parsed.frontmatter.event?.trim();
  if (!event) {
    return null;
  }

  const name = parsed.frontmatter.name?.trim() || file.replace(/\.md$/, "");
  const source = parsed.frontmatter.source?.trim() || undefined;
  return {
    name,
    event,
    source,
    template: parsed.body,
    noReply: parseBool(parsed.frontmatter["no-reply"], false)
  };
}

async function loadVendorReactions(): Promise<ReactionRule[]> {
  const files = await listVendorFiles("reactions");
  const reactions: ReactionRule[] = [];

  for (const file of files) {
    if (!file.endsWith(".md")) {
      continue;
    }
    const content = await readVendorFile(path.join("reactions", file));
    if (!content) {
      continue;
    }
    const reaction = parseReactionFromMarkdown(file, content);
    if (!reaction) {
      continue;
    }
    reactions.push(reaction);
  }

  return reactions;
}

function coerceReaction(candidate: unknown, index: number): ReactionRule | null {
  if (!candidate || typeof candidate !== "object") {
    return null;
  }

  const value = candidate as Record<string, unknown>;
  const event = typeof value.event === "string" ? value.event.trim() : "";
  const template = typeof value.template === "string" ? value.template : "";
  if (!event || !template) {
    return null;
  }

  const name =
    typeof value.name === "string" && value.name.trim()
      ? value.name.trim()
      : `user-reaction-${index + 1}`;

  const source = typeof value.source === "string" && value.source.trim() ? value.source.trim() : undefined;
  const noReply = typeof value.noReply === "boolean" ? value.noReply : false;

  return {
    name,
    event,
    template,
    source,
    noReply
  };
}

async function readUserReactionFile(filePath: string): Promise<ReactionRule[]> {
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    const parsed = JSON.parse(raw) as unknown;
    const config = parsed as ReactionConfigFile | unknown[];
    const configReactions = (config as ReactionConfigFile).reactions;
    const entries: unknown[] = Array.isArray(config)
      ? config
      : Array.isArray(configReactions)
      ? configReactions
      : [];

    const reactions: ReactionRule[] = [];
    for (let i = 0; i < entries.length; i += 1) {
      const reaction = coerceReaction(entries[i], i);
      if (!reaction) {
        continue;
      }
      reactions.push(reaction);
    }
    return reactions;
  } catch {
    return [];
  }
}

async function loadUserReactions(): Promise<ReactionRule[]> {
  const envPath = process.env[USER_REACTIONS_ENV];
  const candidates = [
    envPath,
    path.join(process.cwd(), ".opencode", "gantry-reactions.json")
  ].filter((item): item is string => Boolean(item && item.trim()));

  const merged: ReactionRule[] = [];
  for (const candidate of candidates) {
    const reactions = await readUserReactionFile(candidate);
    if (reactions.length > 0) {
      merged.push(...reactions);
    }
  }

  return merged;
}

function lookupPath(root: Record<string, unknown>, keyPath: string): unknown {
  const segments = keyPath.split(".").filter(Boolean);
  let current: unknown = root;
  for (const segment of segments) {
    if (!current || typeof current !== "object") {
      return undefined;
    }
    current = (current as Record<string, unknown>)[segment];
  }
  return current;
}

function stringifyTemplateValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return "";
  }
}

export function formatTemplate(template: string, data: Record<string, unknown>): string {
  return template.replace(/\{([a-zA-Z0-9_.-]+)\}/g, (_full, keyPath) => {
    const value = lookupPath(data, keyPath);
    return stringifyTemplateValue(value);
  });
}

export function matchReaction(rule: ReactionRule, eventType: string, source?: string): boolean {
  if (rule.event !== eventType) {
    return false;
  }
  if (rule.source && rule.source !== source) {
    return false;
  }
  return true;
}

export async function loadCommands(): Promise<Config["command"]> {
  const files = await listVendorFiles("commands");
  const commands: Config["command"] = {};

  for (const file of files) {
    if (!file.endsWith(".md")) {
      continue;
    }
    const content = await readVendorFile(path.join("commands", file));
    if (!content) {
      continue;
    }
    const parsed = parseMarkdownWithFrontmatter(content);
    if (!parsed) {
      continue;
    }

    const commandName = `gantry:${file.replace(/\.md$/, "")}`;
    const baseDescription = parsed.frontmatter.description ?? commandName;
    const argHint = parsed.frontmatter["argument-hint"];
    commands[commandName] = {
      description: argHint ? `${baseDescription} (${argHint})` : baseDescription,
      template: parsed.body,
      agent: parsed.frontmatter.agent,
      model: parsed.frontmatter.model,
      subtask: parsed.frontmatter.subtask === "true"
    };
  }

  return commands;
}

export async function loadReactions(): Promise<ReactionRule[]> {
  const vendor = await loadVendorReactions();
  const user = await loadUserReactions();
  return [...vendor, ...user];
}

interface GantryFederationLink {
  name?: string;
  kind?: string;
  url?: string;
  project_id?: string;
  tags?: unknown;
}

interface GantryConfig {
  federation?: {
    hub_url?: string;
    links?: GantryFederationLink[];
  };
  project?: string;
}

function normalizeTagList(input: unknown): string[] {
  if (Array.isArray(input)) {
    return input
      .filter((value): value is string => typeof value === "string")
      .map((value) => value.trim().toLowerCase())
      .filter((value) => value.length > 0);
  }
  if (typeof input === "string") {
    return input
      .split(",")
      .map((value) => value.trim().toLowerCase())
      .filter((value) => value.length > 0);
  }
  return [];
}

export function selectAutoHubTargetFromConfig(cfg: GantryConfig): AutoHubTarget | null {
  const links = Array.isArray(cfg.federation?.links) ? cfg.federation?.links ?? [] : [];
  let firstHub: AutoHubTarget | null = null;
  let firstTagged: AutoHubTarget | null = null;

  for (const link of links) {
    const kind = (link.kind ?? "hub").trim().toLowerCase();
    if (kind !== "hub") {
      continue;
    }
    const url = (link.url ?? "").trim();
    if (!url) {
      continue;
    }
    const projectID = (link.project_id ?? cfg.project ?? "").trim() || undefined;
    const tags = normalizeTagList(link.tags);
    if (tags.includes("opencode-session-hub")) {
      if (!firstTagged) {
        firstTagged = { url, projectID, source: "gantry.yaml:federation.links[tag=opencode-session-hub]" };
      }
    } else if (!firstHub) {
      firstHub = { url, projectID, source: "gantry.yaml:federation.links[kind=hub]" };
    }
  }

  if (firstTagged) {
    return firstTagged;
  }
  if (firstHub) {
    return firstHub;
  }

  const fallbackHubURL = (cfg.federation?.hub_url ?? "").trim();
  if (fallbackHubURL) {
    const projectID = (cfg.project ?? "").trim() || undefined;
    return { url: fallbackHubURL, projectID, source: "gantry.yaml:federation.hub_url" };
  }
  return null;
}

export async function discoverAutoHubTarget(): Promise<AutoHubTarget | null> {
  const configPath = path.join(process.cwd(), "gantry.yaml");
  let raw = "";
  try {
    raw = await fs.readFile(configPath, "utf-8");
  } catch {
    return null;
  }

  const lines = raw.split(/\r?\n/);
  let inFederation = false;
  let inLinks = false;
  let inLinkTags = false;
  let currentLinkIndent = -1;
  let currentLink: GantryFederationLink | null = null;
  const parsed: GantryConfig = { federation: { links: [] } };

  const leadingSpaces = (value: string): number => {
    let count = 0;
    for (const ch of value) {
      if (ch !== " ") {
        break;
      }
      count += 1;
    }
    return count;
  };

  const pushLink = (): void => {
    if (!currentLink) {
      return;
    }
    parsed.federation?.links?.push(currentLink);
    currentLink = null;
    inLinkTags = false;
    currentLinkIndent = -1;
  };

  for (const lineRaw of lines) {
    const line = lineRaw.replace(/\t/g, "    ");
    const trimmed = line.trim();
    const indent = leadingSpaces(line);
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    if (!line.startsWith(" ")) {
      pushLink();
      inFederation = trimmed === "federation:";
      inLinks = false;
      inLinkTags = false;
      if (trimmed.startsWith("project:")) {
        parsed.project = trimmed.slice("project:".length).trim();
      }
      continue;
    }
    if (!inFederation) {
      continue;
    }

    if (trimmed === "links:") {
      inLinks = true;
      inLinkTags = false;
      continue;
    }
    if (trimmed.startsWith("hub_url:")) {
      parsed.federation = parsed.federation ?? {};
      parsed.federation.hub_url = trimmed.slice("hub_url:".length).trim();
      continue;
    }
    if (!inLinks) {
      continue;
    }

    if (trimmed.startsWith("- ")) {
      if (inLinkTags && currentLink && indent > currentLinkIndent) {
        const value = trimmed.slice(2).trim();
        const existing = normalizeTagList(currentLink.tags);
        if (value) {
          currentLink.tags = [...existing, value];
        }
        continue;
      }
      pushLink();
      currentLink = {};
      currentLinkIndent = indent;
      const rest = trimmed.slice(2);
      if (rest.startsWith("name:")) {
        currentLink.name = rest.slice("name:".length).trim();
      }
      inLinkTags = false;
      continue;
    }
    if (!currentLink) {
      continue;
    }

    const idx = trimmed.indexOf(":");
    if (idx === -1) {
      continue;
    }
    const key = trimmed.slice(0, idx).trim();
    const value = trimmed.slice(idx + 1).trim();
    switch (key) {
      case "kind":
        currentLink.kind = value;
        inLinkTags = false;
        break;
      case "url":
        currentLink.url = value;
        inLinkTags = false;
        break;
      case "project_id":
        currentLink.project_id = value;
        inLinkTags = false;
        break;
      case "tags":
        if (!value) {
          currentLink.tags = [];
          inLinkTags = true;
        } else {
          currentLink.tags = value;
          inLinkTags = false;
        }
        break;
      default:
        inLinkTags = false;
        break;
    }
  }
  pushLink();

  return selectAutoHubTargetFromConfig(parsed);
}

export async function discoverWakeGSIDTargets(): Promise<WakeGSIDDiscovery> {
  const envValue = (process.env.GANTRY_WAKE_GSID ?? "").trim();
  if (envValue) {
    return { targets: [envValue], source: "env:GANTRY_WAKE_GSID" };
  }

  const factoryIDPath = path.join(process.cwd(), ".agf-workspace", "factory.id");
  try {
    const raw = await fs.readFile(factoryIDPath, "utf-8");
    const factoryID = raw.trim();
    if (!factoryID) {
      return { targets: [], source: "none" };
    }
    return {
      targets: [factoryID, `mail-${factoryID}`],
      source: ".agf-workspace/factory.id"
    };
  } catch {
    return { targets: [], source: "none" };
  }
}

function formatFingerprint(raw: Buffer): string {
  return Array.from(createHash("sha256").update(raw).digest())
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join(":");
}

function rfc3339Now(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

export async function buildHubAuthHeaders(requestTarget: string): Promise<HubAuthHeaders | null> {
  const workspaceDir = path.join(process.cwd(), ".agf-workspace");
  const keyPath = path.join(workspaceDir, "factory.key");
  const certPath = path.join(workspaceDir, "factory.cert");
  let keyPEM = "";
  let certPEM = "";
  try {
    [keyPEM, certPEM] = await Promise.all([
      fs.readFile(keyPath, "utf-8"),
      fs.readFile(certPath, "utf-8"),
    ]);
  } catch {
    return null;
  }

  try {
    const timestamp = rfc3339Now();
    const nonce = randomBytes(16).toString("hex");
    const emptyBodyHash = createHash("sha256").update(Buffer.alloc(0)).digest("hex");
    const canonical = `GET\n${requestTarget}\n${timestamp}\n${nonce}\n${emptyBodyHash}`;
    const signature = sign("sha256", Buffer.from(canonical), {
      key: keyPEM,
      dsaEncoding: "der",
    }).toString("base64");
    const cert = new X509Certificate(certPEM);
    return {
      headers: {
        "X-AGF-Fingerprint": formatFingerprint(cert.raw),
        "X-AGF-Timestamp": timestamp,
        "X-AGF-Nonce": nonce,
        "X-AGF-Signature": signature,
      },
      source: ".agf-workspace/factory.key",
    };
  } catch {
    return null;
  }
}
