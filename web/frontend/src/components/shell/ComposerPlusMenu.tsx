"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronRight, Microscope, Plug } from "lucide-react";

import { DATA_SOURCES, SourceIcon } from "@/components/shell/ComposerSourcesPopover";

interface Props {
  direction: "down" | "up";
  deepResearch: boolean;
  onSelectDeepResearch: () => void;
  connectedSources: string[];
  onToggleConnector: (id: string) => void;
  onClose: () => void;
}

const CONNECTOR_SOURCES = DATA_SOURCES.filter((s) => s.id !== "web");

// More modes/skills land here over time — already a picker rather than a
// plain toggle. Connectors live in a flyout off the "Connector" row so they're
// reachable regardless of whether Deep research is on (SharePoint works for
// plain chat too), not nested inside Deep research's own options popover.
export default function ComposerPlusMenu({
  direction, deepResearch, onSelectDeepResearch, connectedSources, onToggleConnector, onClose,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [connectorOpen, setConnectorOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelClose = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };
  const scheduleClose = () => {
    cancelClose();
    closeTimer.current = setTimeout(() => setConnectorOpen(false), 200);
  };

  useEffect(() => () => cancelClose(), []);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const connectedCount = connectedSources.length;

  return (
    <div
      ref={ref}
      className={`rise-in surface absolute left-0 z-30 w-72 overflow-visible rounded-xl p-1.5 shadow-xl ${
        direction === "down" ? "top-full mt-2" : "bottom-full mb-2"
      }`}
    >
      <button
        type="button"
        onClick={() => { onSelectDeepResearch(); onClose(); }}
        aria-pressed={deepResearch}
        className="flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-surface-2"
      >
        <Microscope size={16} className="mt-0.5 shrink-0 text-accent-ink" />
        <span className="min-w-0 flex-1">
          <span className="block text-[13px] font-medium text-ink">Deep research</span>
          <span className="block text-[11.5px] leading-snug text-ink-faint">
            Orchestrator + sub-agents work the query in depth, with sources and coverage tracking.
          </span>
        </span>
        {deepResearch && <Check size={14} className="mt-0.5 shrink-0 text-accent-ink" />}
      </button>

      <div
        className="relative"
        onMouseEnter={() => { cancelClose(); setConnectorOpen(true); }}
        onMouseLeave={scheduleClose}
      >
        <button
          type="button"
          onClick={() => setConnectorOpen((v) => !v)}
          aria-expanded={connectorOpen}
          className="flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-surface-2"
        >
          <Plug size={16} className="mt-0.5 shrink-0 text-accent-ink" />
          <span className="min-w-0 flex-1">
            <span className="block text-[13px] font-medium text-ink">Connector</span>
            <span className="block text-[11.5px] leading-snug text-ink-faint">
              {connectedCount > 0 ? `${connectedCount} connected` : "Attach a data source to this chat."}
            </span>
          </span>
          <ChevronRight size={14} className="mt-0.5 shrink-0 text-ink-faint" />
        </button>

        {connectorOpen && (
          <div
            className={`rise-in surface absolute left-full ml-1 w-60 max-h-[min(60vh,20rem)] overflow-y-auto rounded-xl p-1.5 shadow-xl ${
              direction === "down" ? "top-0" : "bottom-0"
            }`}
          >
            {CONNECTOR_SOURCES.map((source) => {
              const isConnected = connectedSources.includes(source.id);
              const isLastOne = isConnected && connectedSources.length === 1;
              return (
                <button
                  key={source.id}
                  type="button"
                  onClick={() => { if (!isLastOne) onToggleConnector(source.id); }}
                  disabled={isLastOne}
                  title={isLastOne ? "At least one connector must stay connected" : undefined}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] transition-colors ${
                    isLastOne ? "cursor-not-allowed opacity-60" : "hover:bg-surface-2"
                  }`}
                >
                  <SourceIcon source={source} />
                  <span className="min-w-0 flex-1 truncate text-ink">{source.label}</span>
                  {isConnected && <Check size={14} className="shrink-0 text-accent-ink" />}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
