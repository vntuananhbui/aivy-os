"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, PanelLeft, Plus, Settings, Trash2 } from "lucide-react";

import { deleteConversation, getHealth, listConversations, type ConversationSummary } from "@/lib/api";
import ThemeToggle from "@/components/ThemeToggle";

interface Props {
  activeId?: string;
  collapsed: boolean;
  onToggle: () => void;
  onNew: () => void;
  onSelect: (threadId: string) => void;
  onOpenSettings: () => void;
}

/** Chat-mode sibling of HistoryRail — same rail slot, own (much simpler) data
 * source: quickchat conversations (title/timestamp only, no coverage/project/
 * tags/favorites — none of that applies to a plain chat). Kept as a fully
 * separate component rather than teaching HistoryRail a second item shape:
 * that component's item model (coverageScore, project, tags, favorite,
 * archived) is deep-research-specific, and forcing chat conversations into
 * it would mean fields that mean nothing for a chat and select/delete logic
 * that has to branch on which kind of id it got. */
export default function ChatHistoryRail({ activeId, collapsed, onToggle, onNew, onSelect, onOpenSettings }: Props) {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<{ status: string } | null | undefined>(undefined);

  const refresh = useCallback(() => {
    setLoading(true);
    listConversations()
      .then(setItems)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Re-fetch whenever the open conversation changes — covers both "sent the
  // first message of a new chat" (activeId goes undefined -> a real id) and
  // switching between existing ones.
  useEffect(() => { refresh(); }, [refresh, activeId]);

  // Same health poll as HistoryRail's footer (kept separate per-component —
  // this rail can mount without that one, e.g. railMode === "chat").
  useEffect(() => {
    let alive = true;
    const check = () => getHealth().then((result) => alive && setHealth(result));
    void check();
    const interval = setInterval(check, 15000);
    return () => { alive = false; clearInterval(interval); };
  }, []);

  const handleDelete = async (e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();
    await deleteConversation(threadId);
    if (threadId === activeId) onNew();
    refresh();
  };

  if (collapsed) {
    return (
      <div className="flex h-full flex-col items-center gap-3 border-r border-line py-4">
        <button onClick={onToggle} title="Expand" className="rounded-lg p-2 text-ink-faint hover:bg-surface-2 hover:text-ink">
          <PanelLeft size={18} />
        </button>
        <button onClick={onNew} title="New chat" className="rounded-lg p-2 text-ink-faint hover:bg-surface-2 hover:text-ink">
          <Plus size={18} />
        </button>
        <span title={health === undefined ? "Connecting" : health ? "Connected" : "Offline"}
          className={`mt-auto h-1.5 w-1.5 rounded-full ${health === undefined ? "bg-warn" : health ? "bg-ok glow-pulse" : "bg-err"}`} />
        <button onClick={onOpenSettings} title="Settings" className="rounded-lg p-2 text-ink-faint hover:bg-surface-2 hover:text-ink">
          <Settings size={18} />
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col border-r border-line">
      <div className="px-3 pb-2 pt-3">
        <button
          type="button"
          onClick={onNew}
          className="flex w-full items-center gap-2 rounded-lg border border-line bg-surface-2/40 px-2.5 py-1.5 text-left text-[12.5px] text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink"
        >
          <Plus size={14} /> New chat
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {loading ? (
          <div className="flex items-center justify-center py-8 text-ink-faint"><Loader2 size={16} className="animate-spin" /></div>
        ) : items.length === 0 ? (
          <div className="px-2 py-4 text-[12.5px] text-ink-faint">No conversations yet.</div>
        ) : (
          <div className="space-y-0.5">
            {items.map((c) => (
              <div key={c.thread_id}
                className={`group relative flex items-center rounded-lg pr-1 transition-colors ${c.thread_id === activeId ? "bg-clay/60" : "hover:bg-surface-2"}`}>
                <button
                  type="button"
                  onClick={() => onSelect(c.thread_id)}
                  className="min-w-0 flex-1 truncate px-2.5 py-2 text-left text-[13px] text-ink-dim group-hover:text-ink"
                >
                  {c.title || "New chat"}
                </button>
                <button
                  type="button"
                  onClick={(e) => { void handleDelete(e, c.thread_id); }}
                  aria-label="Delete conversation"
                  className="shrink-0 rounded-md p-1 text-ink-faint opacity-0 transition-opacity hover:bg-surface-2 hover:text-err group-hover:opacity-100"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="flex items-center justify-between border-t border-line px-4 py-3 text-[12px] text-ink-faint">
        <span className="flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${health === undefined ? "bg-warn" : health ? "bg-ok glow-pulse" : "bg-err"}`} />
          {health === undefined ? "Connecting" : health ? "Connected" : "Offline"}
        </span>
        <span className="flex items-center gap-0.5">
          <button onClick={onOpenSettings} title="Settings" className="rounded-md p-1.5 text-ink-faint hover:bg-surface-2 hover:text-ink">
            <Settings size={16} />
          </button>
          <ThemeToggle />
        </span>
      </div>
    </div>
  );
}
