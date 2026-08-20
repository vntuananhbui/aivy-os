"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { BrainCircuit, ChevronDown, ChevronRight, Copy, Link2, Loader2, Plus, RotateCw, X } from "lucide-react";

import Composer from "@/components/shell/Composer";
import type { SubmitOpts } from "@/components/shell/Composer";
import type { ChatMessage } from "@/hooks/useChat";
import Answer from "@/components/conversation/Answer";
import { useSettings } from "@/components/settings/SettingsProvider";

// Mirrors quickchat/session.py::_COMMAND_RE — a leading "/word" is only
// treated as a command chip when word is actually bound (settings.models.commands),
// same rule the backend dispatcher uses, so the chip never lies about what a
// message will do.
const LEADING_COMMAND_RE = /^\/(\S+)(?:[ \t]+([\s\S]*))?$/;

function splitLeadingCommand(text: string, bound: Record<string, string>): { name: string; rest: string } | null {
  const match = LEADING_COMMAND_RE.exec(text);
  if (!match) return null;
  const name = match[1];
  if (!(name in bound)) return null;
  return { name, rest: match[2] ?? "" };
}

/** Blue "agent" chip for a dispatched quickchat command (see globals.css
 * --color-agent). Purple (--color-accent) is reserved for a future "skill"
 * chip kind — not implemented yet. */
function CommandChip({ name }: { name: string }) {
  return (
    <span className="mr-1.5 inline-flex items-center gap-1 rounded-md bg-agent/15 px-1.5 py-0.5 align-middle font-mono text-[13px] font-medium text-agent-ink">
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-agent" />/{name}
    </span>
  );
}

interface Props {
  messages: ChatMessage[];
  sending: boolean;
  onSend: (text: string, opts?: { webSearchEnabled?: boolean }) => void;
  onApproval: (messageId: string, decision: "approve" | "reject" | "other", message?: string) => void;
  onStop: () => void;
  onNewChat: () => void;
  deepResearch: boolean;
  onDeepResearchChange: (value: boolean) => void;
  onSubmit: (query: string, opts: SubmitOpts) => void;
}

// Split accumulated reasoning text into discrete "lines" — the model emits
// paragraph breaks (\n) between logical steps; fall back to sentence breaks
// when a step is one long unbroken line.
function reasoningLines(text: string): string[] {
  const byNewline = text.split("\n").map((l) => l.trim()).filter(Boolean);
  return byNewline.flatMap((line) =>
    line.length > 140 ? line.split(/(?<=[.!?])\s+/).filter(Boolean) : [line],
  );
}

function ReasoningBlock({ text, live }: { text: string; live: boolean }) {
  const [open, setOpen] = useState(live);
  // Auto-open while reasoning streams in, auto-collapse the moment it's done
  // (the answer starts arriving) — the user can still re-expand manually.
  useEffect(() => {
    setOpen(live);
  }, [live]);
  const lines = useMemo(() => reasoningLines(text), [text]);
  const currentLine = lines.at(-1) ?? "";
  if (!text) return null;
  return (
    <div className="mb-2 rounded-lg border border-line bg-surface-2/40 text-[12.5px]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 px-2.5 py-1.5 text-left text-ink-faint transition-colors hover:text-ink-dim"
      >
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <BrainCircuit size={13} className={live ? "animate-pulse text-accent-ink" : ""} />
        <span className="font-medium">{live ? "Thinking…" : "Reasoning"}</span>
      </button>
      {open && live && (
        // Ticker: only the current line is visible, replaced (not appended)
        // as new lines stream in — `key` forces a fresh rise-in per line.
        <div className="overflow-hidden border-t border-line px-2.5 py-2">
          <div key={lines.length} className="rise-in truncate leading-relaxed text-ink-faint">
            {currentLine}
          </div>
        </div>
      )}
      {open && !live && (
        <div className="max-h-64 space-y-1 overflow-y-auto border-t border-line px-2.5 py-2 leading-relaxed text-ink-faint">
          {lines.map((line, i) => <p key={i}>{line}</p>)}
        </div>
      )}
    </div>
  );
}

const hostnameOf = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
};

const faviconOf = (url: string) => `https://www.google.com/s2/favicons?sz=32&domain=${hostnameOf(url)}`;

/** Fixed right-hand panel listing every link the assistant opened for this
 * answer — mirrors the Comet/Perplexity "Sources" drawer. */
function SourcesPanel({ sources, onClose }: { sources: ChatMessage["sources"]; onClose: () => void }) {
  return (
    <div className="drawer-in fixed inset-y-0 right-0 z-40 w-80 max-w-[85vw] overflow-y-auto border-l border-line bg-paper shadow-xl">
      <div className="sticky top-0 flex items-center justify-between border-b border-line bg-paper px-4 py-3">
        <span className="text-[13px] font-medium text-ink">Sources · {sources.length}</span>
        <button type="button" onClick={onClose} aria-label="Close sources"
          className="rounded-md p-1 text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink">
          <X size={15} />
        </button>
      </div>
      <div className="divide-y divide-line">
        {sources.map((s, i) => (
          <a key={i} href={s.url} target="_blank" rel="noreferrer"
            className="flex items-start gap-2.5 px-4 py-3 transition-colors hover:bg-surface-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={faviconOf(s.url)} alt="" width={16} height={16} className="mt-0.5 shrink-0 rounded-sm" />
            <div className="min-w-0">
              <p className="line-clamp-2 text-[13px] leading-snug text-ink">{s.title}</p>
              <p className="mt-0.5 truncate text-[11.5px] text-ink-faint">{hostnameOf(s.url)}</p>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

function LinksRow({ sources, open, onToggle }: { sources: ChatMessage["sources"]; open: boolean; onToggle: () => void }) {
  if (sources.length === 0) return null;
  const shown = sources.slice(0, 4);
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={open}
      className={`mt-2 flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[12px] transition-colors ${
        open ? "border-line-strong bg-clay text-accent-ink" : "border-line bg-surface-2/40 text-ink-faint hover:bg-surface-2"
      }`}
    >
      <Link2 size={12} />
      <span className="flex -space-x-1">
        {shown.map((s, i) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img key={i} src={faviconOf(s.url)} alt="" width={14} height={14}
            className="rounded-full border border-paper bg-paper" />
        ))}
      </span>
      <span className="font-medium">{sources.length} {sources.length === 1 ? "source" : "sources"}</span>
    </button>
  );
}

function Bubble({
  message,
  sourcesOpen,
  onToggleSources,
  onCopy,
  onRetry,
  onApproval,
}: {
  message: ChatMessage;
  sourcesOpen: boolean;
  onToggleSources: () => void;
  onCopy: () => void;
  onRetry: () => void;
  onApproval: (decision: "approve" | "reject" | "other", message?: string) => void;
}) {
  const [showOther, setShowOther] = useState(false);
  const [otherText, setOtherText] = useState("");
  const { settings } = useSettings();
  if (message.role === "user") {
    const parsed = splitLeadingCommand(message.text, settings?.models.commands ?? {});
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-surface-2 px-4 py-2.5 text-[15px] leading-relaxed text-ink">
          {parsed ? (
            <>
              <CommandChip name={parsed.name} />
              {parsed.rest}
            </>
          ) : (
            message.text
          )}
        </div>
      </div>
    );
  }
  return (
    <div className="w-full">
      <ReasoningBlock text={message.reasoning} live={message.streaming && !message.text} />
      {message.text ? (
        <Answer markdown={message.text} citations={message.citations} streaming={message.streaming} />
      ) : message.streaming ? (
        <span className="flex items-center gap-2 text-[13px] text-ink-faint">
          <Loader2 size={13} className="animate-spin" /> Thinking…
        </span>
      ) : null}
      {message.error && (
        <p className="mt-1 text-[13px] text-err">{message.error}</p>
      )}
      {message.approval && (
        <div className="mt-3 rounded-xl border border-line-strong bg-surface-2/50 p-4">
          <p className="text-[14px] font-semibold text-ink">Xác nhận tạo lịch họp Teams</p>
          <p className="mt-1 whitespace-pre-wrap text-[12.5px] leading-relaxed text-ink-dim">
            {message.approval.action.description}
          </p>
          {message.approval.status === "pending" && (
            <>
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" onClick={() => onApproval("approve")}
                  className="rounded-lg bg-agent px-3 py-1.5 text-[13px] font-medium text-white">Đồng ý</button>
                <button type="button" onClick={() => onApproval("reject")}
                  className="rounded-lg border border-line px-3 py-1.5 text-[13px] text-ink-dim">Reject</button>
                <button type="button" onClick={() => setShowOther((v) => !v)}
                  className="rounded-lg border border-line px-3 py-1.5 text-[13px] text-ink-dim">Other</button>
              </div>
              {showOther && (
                <div className="mt-3 flex gap-2">
                  <textarea value={otherText} onChange={(e) => setOtherText(e.target.value)}
                    aria-label="Meeting correction" placeholder="Nhập thay đổi bạn muốn…"
                    className="min-h-20 flex-1 rounded-lg border border-line bg-paper p-2 text-[13px] text-ink outline-none focus:border-agent" />
                  <button type="button" disabled={!otherText.trim()}
                    onClick={() => onApproval("other", otherText.trim())}
                    className="self-end rounded-lg bg-agent px-3 py-1.5 text-[13px] text-white disabled:opacity-40">Gửi</button>
                </div>
              )}
            </>
          )}
          {message.approval.status !== "pending" && (
            <p className="mt-3 text-[12px] text-ink-faint">
              {message.approval.status === "submitting" ? "Đang xử lý…" : `Đã ${message.approval.status}`}
            </p>
          )}
        </div>
      )}
      <LinksRow sources={message.sources} open={sourcesOpen} onToggle={onToggleSources} />
      {!message.streaming && message.text && (
        <div className="mt-2 flex items-center gap-1">
          <button type="button" onClick={onCopy} title="Copy answer" aria-label="Copy answer"
            className="rounded-md p-1.5 text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink-dim">
            <Copy size={13} />
          </button>
          <button type="button" onClick={onRetry} title="Retry" aria-label="Retry"
            className="rounded-md p-1.5 text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink-dim">
            <RotateCw size={13} />
          </button>
        </div>
      )}
    </div>
  );
}

export default function ChatView({
  messages, sending, onSend, onApproval, onStop, onNewChat, deepResearch, onDeepResearchChange, onSubmit,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [sourcesOpenId, setSourcesOpenId] = useState<string | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const handleSubmit = (query: string, opts: SubmitOpts) => {
    if (opts.deepResearch) {
      onSubmit(query, opts);
      return;
    }
    onSend(query, { webSearchEnabled: opts.webSearchEnabled });
  };

  const openSources = messages.find((m) => m.id === sourcesOpenId);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="relative flex items-center justify-end gap-1 px-4 pt-16 sm:px-6 min-[1180px]:pt-3">
        <button type="button" onClick={onNewChat} title="New chat" aria-label="New chat"
          className="rounded-md p-1.5 text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink-dim">
          <Plus size={15} />
        </button>
      </div>
      <div className="mx-auto min-h-0 w-full max-w-3xl flex-1 space-y-7 overflow-y-auto px-4 pb-8 pt-3 sm:px-6">
        {messages.map((m, i) => (
          <Bubble
            key={m.id}
            message={m}
            sourcesOpen={sourcesOpenId === m.id}
            onToggleSources={() => setSourcesOpenId((id) => (id === m.id ? null : m.id))}
            onCopy={() => navigator.clipboard.writeText(m.text)}
            onRetry={() => {
              const prevUser = [...messages.slice(0, i)].reverse().find((x) => x.role === "user");
              if (prevUser) onSend(prevUser.text);
            }}
            onApproval={(decision, feedback) => onApproval(m.id, decision, feedback)}
          />
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="mx-auto w-full max-w-3xl px-4 pb-5 sm:px-6">
        <Composer
          onSubmit={handleSubmit}
          onStop={sending ? onStop : undefined}
          running={sending}
          deepResearch={deepResearch}
          onDeepResearchChange={onDeepResearchChange}
          placeholder={deepResearch ? "Ask anything — deep research is on…" : "Ask anything…"}
        />
      </div>
      {openSources && <SourcesPanel sources={openSources.sources} onClose={() => setSourcesOpenId(null)} />}
    </div>
  );
}
