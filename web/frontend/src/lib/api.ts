// REST + WebSocket API client

import type {
  AdvancedView,
  BrowserDiagnostic,
  EffortLevel,
  EffortView,
  FileNode,
  ModelsView,
  ProvidersResponse,
  ProviderDiagnostic,
  RepairRequest,
  ResolveEvidenceRequest,
  ResolveEvidenceResponse,
  RunDefaultsView,
  SearchRequest,
  SearchDiagnostic,
  SearchResult,
  SearchState,
  SettingsData,
  SkillsView,
  WSEvent,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 12000;

function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  return new Promise((resolve, reject) => {
    const timeout = globalThis.setTimeout(() => {
      controller.abort();
      reject(new Error("Request timed out"));
    }, timeoutMs);

    fetch(input, { ...init, signal: init.signal ?? controller.signal }).then(
      (response) => {
        globalThis.clearTimeout(timeout);
        resolve(response);
      },
      (error) => {
        globalThis.clearTimeout(timeout);
        reject(error);
      },
    );
  });
}

function readJsonWithTimeout<T>(response: Response): Promise<T> {
  return new Promise((resolve, reject) => {
    const timeout = globalThis.setTimeout(() => reject(new Error("Response timed out")), REQUEST_TIMEOUT_MS);
    response.json().then(
      (data) => {
        globalThis.clearTimeout(timeout);
        resolve(data as T);
      },
      (error) => {
        globalThis.clearTimeout(timeout);
        reject(error);
      },
    );
  });
}

// ---- REST ----

export async function getHealth(): Promise<{ status: string; version?: string } | null> {
  try {
    const res = await fetchWithTimeout(`${API_BASE}/api/health`, { cache: "no-store" });
    if (!res.ok) return null;
    return readJsonWithTimeout(res);
  } catch {
    return null;
  }
}

export async function startSearch(req: SearchRequest): Promise<{ session_id: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Search failed: ${res.statusText}`);
  return readJsonWithTimeout(res);
}

export async function startRepair(
  sessionId: string,
  req: RepairRequest,
): Promise<RepairStartResponse> {
  const res = await fetchWithTimeout(
    `${API_BASE}/api/search/${sessionId}/repair`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    },
    35000,
  );
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await readJsonWithTimeout<{ detail?: string | string[] }>(res);
      if (Array.isArray(body.detail)) detail = body.detail.join("; ");
      else if (body.detail) detail = body.detail;
    } catch { /* keep statusText */ }
    if (res.status === 404 && detail === "Not Found") {
      throw new Error("Repair API unavailable — restart the SearchOS API to load the current WebUI routes");
    }
    throw new Error(`Repair failed: ${detail}`);
  }
  return readJsonWithTimeout(res);
}

export interface RepairStartResponse {
  session_id: string;
  task_ids: string[];
  planner: "orchestrator" | "llm" | "deterministic";
  planning_latency_ms: number;
  planning_warning?: string | null;
}

export async function resolveEvidence(
  sessionId: string,
  req: ResolveEvidenceRequest,
): Promise<ResolveEvidenceResponse> {
  const res = await fetchWithTimeout(`${API_BASE}/api/search/${sessionId}/evidence/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await readJsonWithTimeout<{ detail?: string }>(res);
      if (body.detail) detail = body.detail;
    } catch { /* keep statusText */ }
    throw new Error(`Resolve evidence failed: ${detail}`);
  }
  return readJsonWithTimeout(res);
}

export async function stopSearch(sessionId: string): Promise<void> {
  const res = await fetchWithTimeout(`${API_BASE}/api/search/${sessionId}/stop`, { method: "POST" });
  if (!res.ok) throw new Error(`Stop failed: ${res.statusText}`);
}

export async function steerSearch(sessionId: string, message: string): Promise<void> {
  const res = await fetchWithTimeout(`${API_BASE}/api/search/${sessionId}/steer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(`Steer failed: ${res.statusText}`);
}

export async function getSearchResult(sessionId: string): Promise<SearchResult> {
  const res = await fetchWithTimeout(`${API_BASE}/api/search/${sessionId}`);
  if (!res.ok) throw new Error(`Get result failed: ${res.statusText}`);
  return readJsonWithTimeout(res);
}

export async function getSearchState(sessionId: string): Promise<SearchResult> {
  const res = await fetchWithTimeout(`${API_BASE}/api/search/${sessionId}/state`);
  if (!res.ok) throw new Error(`Get state failed: ${res.statusText}`);
  return readJsonWithTimeout(res);
}

export interface HistoryItem {
  session_id: string;
  title: string;
  status: "running" | "completed" | "incomplete" | "error";
  coverage_score: number | null;
  updated_at: number;
  project: string;
  tags: string[];
  favorite: boolean;
  archived: boolean;
}

export interface HistoryAssetPatch {
  title?: string;
  project?: string;
  tags?: string[];
  favorite?: boolean;
  archived?: boolean;
}

export type HistoryStateSource = "snapshot" | "latest" | "unavailable";

export interface HistoryTurn {
  query: string;
  answer: string;
  steers?: string[];
  search_state: SearchState | null;
  state_source: HistoryStateSource;
  coverage_score: number | null;
  evidence_count: number | null;
  completed_at?: string | null;
  elapsed_s?: number | null;
  total_queries?: number | null;
  total_steps?: number | null;
  tool_counts?: SearchResult["tool_counts"] | null;
  token_usage?: SearchResult["token_usage"] | null;
  token_phases?: SearchResult["token_phases"] | null;
  model_distribution?: SearchResult["model_distribution"] | null;
}

export interface HistoryDetail {
  session_id: string;
  query: string;
  status: "running" | "completed" | "incomplete";
  turns: HistoryTurn[];
  coverage_score: number | null;
  evidence_count: number | null;
  answer: string;
  search_state: SearchState | null;
  events: WSEvent[];
}

// Quickchat conversation history — sibling of the listHistory/loadHistory/
// deleteHistory trio below, but for quickchat threads (checkpointer-backed,
// see quickchat/history_store.py) rather than deep-research sessions.
export interface ConversationSummary {
  thread_id: string;
  title: string;
  created_at: number;
  updated_at: number;
}

export interface ConversationMessage {
  role: "user" | "assistant";
  text: string;
  citations: { url: string; title: string; quote: string }[];
  sources: { url: string; title: string }[];
}

export interface ConversationApproval {
  interrupt_id: string;
  agent_type: string;
  action: { name: string; args: Record<string, unknown>; description: string };
  allowed_decisions: string[];
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const res = await fetchWithTimeout(`${API_BASE}/api/conversations`, { cache: "no-store" });
  if (!res.ok) throw new Error(`List conversations failed: ${res.statusText}`);
  return readJsonWithTimeout(res);
}

export async function loadConversation(
  threadId: string,
): Promise<{
  thread_id: string;
  messages: ConversationMessage[];
  pending_approval: ConversationApproval | null;
}> {
  const res = await fetchWithTimeout(`${API_BASE}/api/conversations/${threadId}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Load conversation failed: ${res.statusText}`);
  return readJsonWithTimeout(res);
}

export async function deleteConversation(threadId: string): Promise<void> {
  const res = await fetchWithTimeout(`${API_BASE}/api/conversations/${threadId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Delete conversation failed: ${res.statusText}`);
}

export async function listHistory(query = ""): Promise<HistoryItem[]> {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  const suffix = params.size ? `?${params.toString()}` : "";
  const res = await fetchWithTimeout(`${API_BASE}/api/history${suffix}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Load history failed: ${res.statusText}`);
  return readJsonWithTimeout(res);
}

export async function loadHistory(sessionId: string): Promise<HistoryDetail> {
  const res = await fetchWithTimeout(`${API_BASE}/api/history/${sessionId}`);
  if (!res.ok) throw new Error(`Load session failed: ${res.statusText}`);
  return readJsonWithTimeout(res);
}

export interface HistoryBranchResponse {
  session_id: string;
  source_session_id: string;
  source_turn_index: number;
  status: "ready";
}

export async function branchHistoryTurn(sessionId: string, turnIndex: number): Promise<HistoryBranchResponse> {
  const res = await fetchWithTimeout(`${API_BASE}/api/history/${sessionId}/turns/${turnIndex}/branch`, {
    method: "POST",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await readJsonWithTimeout<{ detail?: string }>(res);
      if (body.detail) detail = body.detail;
    } catch { /* keep statusText */ }
    throw new Error(`Create branch failed: ${detail}`);
  }
  return readJsonWithTimeout(res);
}

export async function renameHistory(sessionId: string, title: string): Promise<void> {
  await updateHistoryAssets(sessionId, { title });
}

export async function updateHistoryAssets(
  sessionId: string,
  patch: HistoryAssetPatch,
): Promise<HistoryAssetPatch & { session_id: string; title: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/api/history/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await readJsonWithTimeout<{ detail?: string }>(res);
      if (body.detail) detail = body.detail;
    } catch { /* keep statusText */ }
    throw new Error(`Update failed: ${detail}`);
  }
  return readJsonWithTimeout(res);
}

export async function deleteHistory(sessionId: string): Promise<void> {
  const res = await fetchWithTimeout(`${API_BASE}/api/history/${sessionId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Delete failed: ${res.statusText}`);
}

export async function getWorkspaceFiles(sessionId: string): Promise<{ tree: FileNode[] }> {
  const res = await fetchWithTimeout(`${API_BASE}/api/workspace/${sessionId}/files`);
  if (!res.ok) throw new Error(`Get files failed: ${res.statusText}`);
  return readJsonWithTimeout(res);
}

export async function getFileContent(sessionId: string, path: string): Promise<{ content: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/api/workspace/${sessionId}/file?path=${encodeURIComponent(path)}`);
  if (!res.ok) throw new Error(`Get file failed: ${res.statusText}`);
  return readJsonWithTimeout(res);
}

// ---- Settings ----

export async function getSettings(): Promise<SettingsData | null> {
  try {
    const res = await fetch(`${API_BASE}/api/settings`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function putJson<T>(path: string, body: unknown, method = "PUT"): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (data.detail?.detail) detail = data.detail.detail;
    } catch { /* keep statusText */ }
    throw new Error(detail);
  }
  return res.json();
}

export const putEffort = (level: EffortLevel, overrides: Record<string, number> = {}) =>
  putJson<EffortView>("/api/settings/effort", { level, overrides });

export const putSkills = (patch: {
  access_only?: string[] | null;
  access_deny?: string[];
  strategy_deny?: string[];
  orchestrator_deny?: string[];
  enable_access_skill_generation?: boolean | null;
  access_skill_max_per_run?: number | null;
}) => putJson<SkillsView>("/api/settings/skills", patch);

export const patchSkill = (name: string, enabled: boolean) =>
  putJson<SkillsView>(`/api/settings/skills/${encodeURIComponent(name)}`, { enabled }, "PATCH");

export const putSkillCategory = (category: string, enabled: boolean) =>
  putJson<SkillsView>(`/api/settings/skills/category/${encodeURIComponent(category)}`, { enabled });

export const putRoles = (roles: Record<string, string>, fallbackRoles?: Record<string, string>) =>
  putJson<{
    roles: Record<string, string>; role_overrides: Record<string, string>;
    fallback_roles: Record<string, string>; fallback_role_overrides: Record<string, string>;
    warnings: string[];
  }>("/api/settings/models/roles", { roles, fallback_roles: fallbackRoles ?? {} });

export const putSearchBackend = (provider: string | null) =>
  putJson<ModelsView["search"]>("/api/settings/search-backend", { provider });

export const putMisc = (patch: {
  max_time_s?: number;
  search_max_results?: number;
  enable_skills?: boolean;
  enable_explore_batch?: boolean;
  browser_backend?: string;
}) => putJson<RunDefaultsView & { browser_backend: string }>("/api/settings/misc", patch);

// First-class runtime knobs. Only keys present in the patch are touched; send
// null to clear a knob back to its env/code default. https_proxy "" forces
// no-proxy. Proxy / cache dir are not secrets.
export const putAdvanced = (patch: {
  llm_max_retries?: number | null;
  orch_coverage_stall_rounds?: number | null;
  browser_disk_cache_dir?: string | null;
  https_proxy?: string | null;
  search_max_results?: number | null;
  use_layered_context?: boolean | null;
}) => putJson<AdvancedView>("/api/settings/advanced", patch);

export const resetSettings = () =>
  putJson<SettingsData>("/api/settings/reset", {}, "POST");

// ---- Connectors ----

export interface SharePointItem {
  id: string;
  name: string;
  path: string;
  web_url: string;
  is_folder: boolean;
}

export interface SharePointConnectorView {
  connected: boolean;
  selected_items: SharePointItem[];
}

export interface SharePointBrowseItem {
  id: string;
  name: string;
  is_folder: boolean;
  size: number | null;
  web_url: string;
}

export async function getSharepointConnector(): Promise<SharePointConnectorView | null> {
  try {
    const res = await fetch(`${API_BASE}/api/connectors/sharepoint`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// Delegated auth — the token is pasted from an already-signed-in Microsoft
// session (e.g. the FPT SSO app's console output), not obtained via a
// client-secret flow SearchOS runs itself.
export const putSharepointConnector = (body: { access_token: string }) =>
  putJson<SharePointConnectorView>("/api/connectors/sharepoint", body);

export async function browseSharepoint(folderId?: string): Promise<{ items: SharePointBrowseItem[] }> {
  const qs = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : "";
  const res = await fetch(`${API_BASE}/api/connectors/sharepoint/browse${qs}`, { cache: "no-store" });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch { /* keep statusText */ }
    throw new Error(detail);
  }
  return res.json();
}

export const putSharepointSelection = (items: SharePointItem[]) =>
  putJson<SharePointConnectorView>("/api/connectors/sharepoint/selection", { items });

export const deleteSharepointConnector = () =>
  putJson<SharePointConnectorView | null>("/api/connectors/sharepoint", {}, "DELETE");

export type JiraAuthMode = "cloud" | "server" | "oauth";

export interface JiraConnectorView {
  connected: boolean;
  site_url: string;
  auth_mode: JiraAuthMode;
  email: string;
  project_keys: string[];
}

export async function getJiraConnector(): Promise<JiraConnectorView | null> {
  try {
    const res = await fetch(`${API_BASE}/api/connectors/jira`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// Credential is never echoed back — Cloud sends email+api_token (Basic Auth),
// Server/DC sends personal_access_token (Bearer) instead.
export const putJiraConnector = (body: {
  site_url: string;
  auth_mode: JiraAuthMode;
  email?: string;
  api_token?: string;
  personal_access_token?: string;
  project_keys?: string[];
}) => putJson<JiraConnectorView>("/api/connectors/jira", body);

export const putJiraSelection = (project_keys: string[]) =>
  putJson<JiraConnectorView>("/api/connectors/jira/selection", { project_keys });

export const deleteJiraConnector = () =>
  putJson<JiraConnectorView | null>("/api/connectors/jira", {}, "DELETE");

export interface TeamsConnectorView {
  connected: boolean;
}

export async function getTeamsConnector(): Promise<TeamsConnectorView | null> {
  try {
    const res = await fetch(`${API_BASE}/api/connectors/teams`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// Delegated auth — normally its own login/token. A SharePoint token that
// already carries Calendars.ReadWrite may also activate this connector.
export const putTeamsConnector = (body: { access_token: string }) =>
  putJson<TeamsConnectorView>("/api/connectors/teams", body);

export const deleteTeamsConnector = () =>
  putJson<TeamsConnectorView | null>("/api/connectors/teams", {}, "DELETE");

// Throws on failure (unlike getSettings): the provider switcher shows an
// inline retry row and needs to distinguish errors from empty data.
export async function getProviderPresets(): Promise<ProvidersResponse> {
  const res = await fetch(`${API_BASE}/api/settings/providers`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Couldn't load presets: ${res.statusText}`);
  return res.json();
}

export const putSettingsKey = (env: string, value: string) =>
  putJson<ModelsView>("/api/settings/keys", { env, value });

// Create/update a user-defined provider connection (referenced by model cards).
export const putProviderConnection = (name: string, body: {
  protocol?: "openai_compatible" | "openai" | "anthropic" | "azure_openai";
  api_base?: string;
  api_version?: string;
  api_key_envs: string[];
  thinking_style?: "chat_template_kwargs" | "enable_thinking" | "none";
  label?: string;
}) => putJson<ModelsView>(`/api/settings/provider-connections/${encodeURIComponent(name)}`, body);

export const deleteProviderConnection = (name: string) =>
  putJson<ModelsView>(`/api/settings/provider-connections/${encodeURIComponent(name)}`, {}, "DELETE");

// Create/repoint a quickchat "/command" binding. agent_type must be one of
// ModelsView.command_catalog's keys — the fixed catalog in
// quickchat/commands/catalog.py, never a free-text import path.
export const putCommand = (name: string, agentType: string) =>
  putJson<ModelsView>(`/api/settings/commands/${encodeURIComponent(name)}`, { agent_type: agentType });

export const deleteCommand = (name: string) =>
  putJson<ModelsView>(`/api/settings/commands/${encodeURIComponent(name)}`, {}, "DELETE");

// Model-card edits. provider_ref repoints the card at a provider connection;
// the card then only carries model id + temperature + enable_thinking. On a base
// profile "" clears a connection-field override; send null to clear temperature/
// provider_ref, omit a field to leave it unchanged.
export const patchProfile = (name: string, patch: {
  model?: string;
  api_base?: string;
  api_version?: string;
  api_key_env?: string;
  provider?: "openai_compatible" | "openai" | "anthropic" | "azure_openai";
  provider_ref?: string | null;
  temperature?: number | null;
  enable_thinking?: boolean;
  thinking_style?: "chat_template_kwargs" | "enable_thinking" | "none";
  rpm?: number | null;
  tpm?: number | null;
}) => putJson<ModelsView>(`/api/settings/profiles/${encodeURIComponent(name)}`, patch, "PATCH");

export const createProfile = (body: {
  name: string;
  model: string;
  provider_ref?: string | null;
  provider?: string;
  api_base?: string;
  api_version?: string;
  api_key_env?: string;
  temperature?: number | null;
  enable_thinking?: boolean;
  thinking_style?: "chat_template_kwargs" | "enable_thinking" | "none";
  rpm?: number;
  tpm?: number;
}) => putJson<ModelsView>("/api/settings/profiles", body, "POST");

export const deleteProfile = (name: string) =>
  putJson<ModelsView>(`/api/settings/profiles/${encodeURIComponent(name)}`, {}, "DELETE");

async function runDiagnostic<T>(path: string, body: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), 65000);
  try {
    const res = await fetch(`${API_BASE}/api/diagnostics/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`Diagnostic failed: ${res.statusText}`);
    return await res.json() as T;
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

export const testProvider = (role: string) =>
  runDiagnostic<ProviderDiagnostic>("provider", { role });

export const testSearchBackend = (query: string) =>
  runDiagnostic<SearchDiagnostic>("search", { query });

export const testBrowserBackend = (url: string) =>
  runDiagnostic<BrowserDiagnostic>("browser", { url });

// ---- WebSocket ----

export function connectWebSocket(
  sessionId: string,
  onMessage: (event: Record<string, unknown>) => void,
  onClose?: () => void,
  opts?: { tail?: boolean; onOpen?: () => void },
): WebSocket {
  const wsBase = API_BASE.replace(/^http/, "ws");
  const ws = new WebSocket(`${wsBase}/api/ws/${sessionId}${opts?.tail ? "?tail=1" : ""}`);

  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      onMessage(data);
    } catch {
      // ignore parse errors
    }
  };

  ws.onopen = () => opts?.onOpen?.();
  ws.onclose = () => onClose?.();
  // Browsers dispatch `close` after an errored connection is closed. Keeping
  // recovery on that single path prevents duplicate status checks/retries.
  ws.onerror = () => ws.close();

  return ws;
}

// ---- Plain chat (SSE) ----

export type ChatStreamEvent =
  | { type: "start"; thread_id: string }
  | { type: "reasoning"; text: string }
  | { type: "token"; text: string }
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; name: string; url: string; title: string }
  | { type: "citation"; url: string; title: string; quote: string }
  | {
      type: "approval_required";
      interrupt_id: string;
      agent_type: string;
      action: { name: string; args: Record<string, unknown>; description: string };
      allowed_decisions: string[];
    }
  | { type: "error"; message: string }
  | { type: "done" };

// EventSource can't send a POST body, so the SSE frames are parsed by hand
// off a plain fetch stream (frames are separated by a blank line).
export async function* streamChat(
  message: string,
  threadId: string | undefined,
  signal?: AbortSignal,
  opts?: { thinking?: boolean; effort?: EffortLevel; webSearchEnabled?: boolean },
): AsyncGenerator<ChatStreamEvent> {
  yield* streamChatRequest("/api/chat", {
    message, thread_id: threadId,
    ...(opts?.thinking !== undefined ? { thinking: opts.thinking } : {}),
    ...(opts?.effort !== undefined ? { effort: opts.effort } : {}),
    ...(opts?.webSearchEnabled !== undefined ? { web_search_enabled: opts.webSearchEnabled } : {}),
  }, signal);
}

export async function* streamChatResume(
  body: {
    thread_id: string;
    interrupt_id: string;
    decision: "approve" | "reject" | "other";
    message?: string;
  },
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  yield* streamChatRequest("/api/chat/resume", body, signal);
}

async function* streamChatRequest(
  path: string,
  body: Record<string, unknown>,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`Chat request failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);

      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const parsed = JSON.parse(data);
      if (event === "start") yield { type: "start", thread_id: parsed.thread_id };
      else if (event === "reasoning") yield { type: "reasoning", text: parsed.text };
      else if (event === "token") yield { type: "token", text: parsed.text };
      else if (event === "tool_call") yield { type: "tool_call", name: parsed.name, args: parsed.args ?? {} };
      else if (event === "tool_result") yield { type: "tool_result", name: parsed.name, url: parsed.url ?? "", title: parsed.title ?? "" };
      else if (event === "citation") yield { type: "citation", url: parsed.url ?? "", title: parsed.title ?? "", quote: parsed.quote ?? "" };
      else if (event === "approval_required") yield {
        type: "approval_required", interrupt_id: parsed.interrupt_id,
        agent_type: parsed.agent_type, action: parsed.action,
        allowed_decisions: parsed.allowed_decisions ?? [],
      };
      else if (event === "error") yield { type: "error", message: parsed.message };
      else if (event === "done") yield { type: "done" };
    }
  }
}
