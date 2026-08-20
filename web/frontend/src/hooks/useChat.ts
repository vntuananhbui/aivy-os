"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { loadConversation as apiLoadConversation, streamChat, streamChatResume } from "@/lib/api";
import type { EffortLevel } from "@/lib/types";

// Conversation id lives in the URL (?c=<thread_id>), not localStorage — a
// reload with no id in the URL should land on the fresh main chat page, and
// a reload with one should reopen that exact conversation (shareable/
// bookmarkable too). Plain History API, not next/navigation's
// useSearchParams: this page isn't wrapped in a Suspense boundary and
// pushing that requirement on the whole page just for this would be overkill.
const THREAD_ID_QUERY_KEY = "c";

function readThreadIdFromUrl(): string | undefined {
  if (typeof window === "undefined") return undefined;
  return new URLSearchParams(window.location.search).get(THREAD_ID_QUERY_KEY) || undefined;
}

function writeThreadIdToUrl(id: string | undefined) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (id) url.searchParams.set(THREAD_ID_QUERY_KEY, id);
  else url.searchParams.delete(THREAD_ID_QUERY_KEY);
  window.history.replaceState(null, "", url);
}

export interface ChatSource {
  url: string;
  title: string;
}

export interface ChatCitation {
  url: string;
  title: string;
  quote: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  reasoning: string;
  streaming: boolean;
  error: string | null;
  sources: ChatSource[];
  // Index 0 = marker [1], index 1 = [2], etc — assigned in the order
  // "citation" events arrive, which matches the order the model writes
  // markers (see quickchat/tools.py's `cite` tool docstring).
  citations: ChatCitation[];
  approval: ChatApproval | null;
}

export interface ChatApproval {
  interruptId: string;
  agentType: string;
  action: { name: string; args: Record<string, unknown>; description: string };
  status: "pending" | "submitting" | "approved" | "rejected" | "revising";
}

// crypto.randomUUID() instead of an incrementing counter: a module-level
// counter gets reset by Next.js Fast Refresh in dev while `messages` state
// survives, producing duplicate ids (and React's "same key" warning).
const nextId = () => crypto.randomUUID();

// Network token chunks arrive in bursts of uneven size (backend/model
// dependent) — displaying them the instant they land looks stuttery. A small
// fixed-cadence drip decouples "how fast text arrives" from "how fast it's
// shown", the same trick most streaming chat UIs use for a smooth typewriter
// feel regardless of upstream chunking.
const TYPEWRITER_INTERVAL_MS = 20;
const TYPEWRITER_CHARS_PER_TICK = 3;

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  // threadId as state (not just the ref below) so the sidebar can reactively
  // highlight the current conversation; the ref is what send()'s streaming
  // closure reads synchronously (state updates from inside that loop would
  // otherwise lag a render behind).
  const [threadId, setThreadIdState] = useState<string | undefined>(undefined);
  const threadIdRef = useRef<string | undefined>(undefined);
  const abortRef = useRef<AbortController | null>(null);
  const loadSeq = useRef(0);

  const setThreadId = useCallback((id: string | undefined) => {
    threadIdRef.current = id;
    setThreadIdState(id);
    writeThreadIdToUrl(id);
  }, []);

  const patch = (id: string, fn: (m: ChatMessage) => ChatMessage) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? fn(m) : m)));
  };

  const loadConversation = useCallback(async (id: string) => {
    // Guards against a slow load from an older click resolving after a
    // newer one and clobbering it — only the most recent call may commit.
    const seq = ++loadSeq.current;
    try {
      const { messages: loaded, pending_approval: pendingApproval } = await apiLoadConversation(id);
      if (seq !== loadSeq.current) return;
      const restored: ChatMessage[] = loaded.map((m) => ({
          id: nextId(), role: m.role, text: m.text, reasoning: "", streaming: false,
          error: null, sources: m.sources, citations: m.citations, approval: null,
        }));
      if (pendingApproval) {
        restored.push({
          id: nextId(), role: "assistant", text: "", reasoning: "", streaming: false,
          error: null, sources: [], citations: [],
          approval: {
            interruptId: pendingApproval.interrupt_id,
            agentType: pendingApproval.agent_type,
            action: pendingApproval.action,
            status: "pending",
          },
        });
      }
      setMessages(restored);
      setThreadId(id);
    } catch (e) {
      if (seq !== loadSeq.current) return;
      // Conversation gone (deleted, expired, or a stale/tampered URL) — fall
      // back to the main chat page instead of getting stuck on a load that
      // can never succeed.
      setMessages([]);
      setThreadId(undefined);
      throw e;
    }
  }, [setThreadId]);

  // Open whatever conversation the URL points at (?c=<thread_id>) on mount —
  // covers both a deep link and a plain reload. No id in the URL means the
  // fresh main chat page, same as a first visit.
  useEffect(() => {
    const id = readThreadIdFromUrl();
    if (id) void loadConversation(id).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const send = useCallback(async (
    text: string, opts?: { thinking?: boolean; effort?: EffortLevel; webSearchEnabled?: boolean },
  ) => {
    const body = text.trim();
    if (!body || sending) return;

    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", text: body, reasoning: "", streaming: false, error: null, sources: [], citations: [], approval: null },
    ]);
    const assistantId = nextId();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", text: "", reasoning: "", streaming: true, error: null, sources: [], citations: [], approval: null },
    ]);
    setSending(true);

    // Typewriter drip for the answer text — see TYPEWRITER_INTERVAL_MS above.
    // Not a ref/state: this closure lives only for the duration of this
    // `send()` call, same lifetime as `controller` below.
    let pendingText = "";
    let flushTimer: ReturnType<typeof setInterval> | null = null;
    const startTypewriter = () => {
      if (flushTimer) return;
      flushTimer = setInterval(() => {
        if (!pendingText) return;
        const chunk = pendingText.slice(0, TYPEWRITER_CHARS_PER_TICK);
        pendingText = pendingText.slice(TYPEWRITER_CHARS_PER_TICK);
        patch(assistantId, (m) => ({ ...m, text: m.text + chunk }));
      }, TYPEWRITER_INTERVAL_MS);
    };
    const stopTypewriter = () => {
      if (flushTimer) {
        clearInterval(flushTimer);
        flushTimer = null;
      }
      if (pendingText) {
        const rest = pendingText;
        pendingText = "";
        patch(assistantId, (m) => ({ ...m, text: m.text + rest }));
      }
    };

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      for await (const event of streamChat(body, threadIdRef.current, controller.signal, opts)) {
        if (event.type === "start") {
          setThreadId(event.thread_id);
        } else if (event.type === "reasoning") {
          patch(assistantId, (m) => ({ ...m, reasoning: m.reasoning + event.text }));
        } else if (event.type === "token") {
          pendingText += event.text;
          startTypewriter();
        } else if (event.type === "tool_call") {
          // Any text so far was just the model narrating its next move before
          // calling a tool (e.g. "Let me search for that...") — drop it so the
          // bubble only ever shows the answer that follows the last tool call.
          pendingText = "";
          patch(assistantId, (m) => (m.text ? { ...m, text: "" } : m));
        } else if (event.type === "tool_result") {
          if (event.name === "web_search" && event.url) {
            const { url, title } = event;
            patch(assistantId, (m) =>
              m.sources.some((s) => s.url === url)
                ? m
                : { ...m, sources: [...m.sources, { url, title: title || url }] },
            );
          }
        } else if (event.type === "citation") {
          const { url, title, quote } = event;
          patch(assistantId, (m) => ({ ...m, citations: [...m.citations, { url, title, quote }] }));
        } else if (event.type === "approval_required") {
          patch(assistantId, (m) => ({
            ...m,
            approval: {
              interruptId: event.interrupt_id,
              agentType: event.agent_type,
              action: event.action,
              status: "pending",
            },
          }));
        } else if (event.type === "error") {
          patch(assistantId, (m) => ({ ...m, error: event.message }));
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        patch(assistantId, (m) => ({ ...m, error: (e as Error).message }));
      }
    } finally {
      // Flush whatever's still queued before marking done — otherwise the
      // last few chars sit in `pendingText` past the point the UI already
      // considers the message complete (copy/retry buttons, citation
      // linkification all gate on `!streaming`).
      stopTypewriter();
      patch(assistantId, (m) => ({ ...m, streaming: false }));
      setSending(false);
      abortRef.current = null;
    }
  }, [sending, setThreadId]);

  const resumeApproval = useCallback(async (
    assistantId: string,
    decision: "approve" | "reject" | "other",
    message = "",
  ) => {
    if (sending || !threadIdRef.current) return;
    const target = messages.find((m) => m.id === assistantId)?.approval;
    if (!target || target.status !== "pending") return;
    const consumedStatus = decision === "approve" ? "approved" : decision === "reject" ? "rejected" : "revising";
    patch(assistantId, (m) => ({
      ...m, streaming: true, error: null,
      approval: m.approval ? { ...m.approval, status: "submitting" } : null,
    }));
    setSending(true);
    const controller = new AbortController();
    abortRef.current = controller;
    let streamError: string | null = null;
    try {
      for await (const event of streamChatResume({
        thread_id: threadIdRef.current,
        interrupt_id: target.interruptId,
        decision,
        message,
      }, controller.signal)) {
        if (event.type === "token") {
          patch(assistantId, (m) => ({ ...m, text: m.text + event.text }));
        } else if (event.type === "reasoning") {
          patch(assistantId, (m) => ({ ...m, reasoning: m.reasoning + event.text }));
        } else if (event.type === "approval_required") {
          patch(assistantId, (m) => ({
            ...m,
            approval: {
              interruptId: event.interrupt_id,
              agentType: event.agent_type,
              action: event.action,
              status: "pending",
            },
          }));
        } else if (event.type === "error") {
          streamError = event.message;
          patch(assistantId, (m) => ({ ...m, error: event.message }));
        }
      }
      patch(assistantId, (m) => ({
        ...m,
        approval: m.approval?.status === "submitting"
          ? { ...m.approval, status: streamError ? "pending" : consumedStatus }
          : m.approval,
      }));
    } catch (e) {
      patch(assistantId, (m) => ({
        ...m, error: (e as Error).message,
        approval: m.approval ? { ...m.approval, status: "pending" } : null,
      }));
    } finally {
      patch(assistantId, (m) => ({ ...m, streaming: false }));
      setSending(false);
      abortRef.current = null;
    }
  }, [messages, sending]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    setMessages([]);
    setThreadId(undefined);
  }, [setThreadId]);

  return { messages, sending, threadId, send, resumeApproval, stop, reset, loadConversation };
}
