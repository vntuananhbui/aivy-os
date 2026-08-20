"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  Ban,
  Check,
  ChevronDown,
  Globe2,
  ShieldCheck,
  Table2,
} from "lucide-react";

import DomainInput from "@/components/ui/DomainInput";
import SkillsSection from "@/components/settings/SkillsSection";

export interface DataSourceOption {
  id: string;
  label: string;
  /** Real domain to fetch a brand favicon for — omitted for the generic "Web link" entry. */
  domain?: string;
}

// "web" (trusted/excluded domains, this popover), "sharepoint" and "jira"
// (real connectors) are functional; "google" now really gates the web search
// provider (see Composer.tsx's webSearchEnabled) but the rest are still
// local-only demo state. The connector list itself lives in the "Connector"
// flyout off the "+" menu (ComposerPlusMenu.tsx), not here — this popover
// only keeps "Web link" (domain trust) plus the Table/Skills tabs.
export const DATA_SOURCES: DataSourceOption[] = [
  { id: "google", label: "Google Search", domain: "google.com" },
  { id: "web", label: "Web link" },
  { id: "sharepoint", label: "SharePoint", domain: "sharepoint.com" },
  { id: "jira", label: "Jira", domain: "atlassian.com" },
  { id: "outlook", label: "Outlook", domain: "outlook.com" },
  { id: "gmail", label: "Gmail", domain: "gmail.com" },
  { id: "drive", label: "Google Drive", domain: "drive.google.com" },
  { id: "notion", label: "Notion", domain: "notion.so" },
  { id: "slack", label: "Slack", domain: "slack.com" },
];

export const DEFAULT_CONNECTED_SOURCES = ["google"];

// Locally bundled logos (previously fetched live from Google's s2 favicon
// service / vendor favicon.ico on every render) — see public/icons/sources/.
// Domains without an entry here fall back to Google's s2 favicon service
// (faviconOf below) — e.g. "atlassian.com" until a local icon is bundled.
const LOCAL_FAVICONS: Record<string, string> = {
  "google.com": "/icons/sources/google.png",
  "sharepoint.com": "/icons/sources/sharepoint.svg",
  "outlook.com": "/icons/sources/outlook.jpg",
  "gmail.com": "/icons/sources/gmail.ico",
  "drive.google.com": "/icons/sources/drive.ico",
  "notion.so": "/icons/sources/notion.png",
  "slack.com": "/icons/sources/slack.png",
};

export const faviconOf = (domain: string) =>
  LOCAL_FAVICONS[domain] ?? `https://www.google.com/s2/favicons?sz=32&domain=${domain}`;

export function SourceIcon({ source, size = 16 }: { source: DataSourceOption; size?: number }) {
  if (!source.domain) return <Globe2 size={size} className="shrink-0 text-ink-faint" />;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={faviconOf(source.domain)} alt="" width={size} height={size} className="shrink-0 rounded-sm" />;
}

interface Props {
  direction: "down" | "up";
  trustedDomains: string[];
  excludedDomains: string[];
  onTrustedDomainsChange: (values: string[]) => void;
  onExcludedDomainsChange: (values: string[]) => void;
  /** Opens the full table-schema editor (rendered below the composer). */
  onOpenSchema: () => void;
  /** Human-readable summary of the currently pinned schema, if any. */
  schemaSummary?: string;
  onClose: () => void;
}

export default function ComposerSourcesPopover({
  direction,
  trustedDomains,
  excludedDomains,
  onTrustedDomainsChange,
  onExcludedDomainsChange,
  onOpenSchema,
  schemaSummary,
  onClose,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [tab, setTab] = useState<"sources" | "table" | "skills">("sources");
  const [webOpen, setWebOpen] = useState(false);
  const [onlyTrusted, setOnlyTrusted] = useState(false);
  const [maxHeight, setMaxHeight] = useState<number>();

  // Cap the height so the popover never runs into the viewport edge — leaves a
  // comfortable gap top or bottom depending on which way it opens.
  useLayoutEffect(() => {
    const update = () => {
      const el = ref.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const gap = 24;
      const available = direction === "down"
        ? window.innerHeight - rect.top - gap
        : rect.bottom - gap;
      setMaxHeight(Math.max(220, Math.floor(Math.min(600, available))));
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [direction, tab, webOpen]);

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

  const webActive = trustedDomains.length > 0 || excludedDomains.length > 0;

  const TABS: { id: typeof tab; label: string; active?: boolean }[] = [
    { id: "sources", label: "Web", active: webActive },
    { id: "table", label: "Table", active: Boolean(schemaSummary) },
    { id: "skills", label: "Skills" },
  ];

  return (
    <div
      ref={ref}
      style={maxHeight == null ? undefined : { maxHeight }}
      className={`rise-in surface absolute left-0 z-30 flex max-h-[min(72vh,600px)] w-96 max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-xl shadow-xl ${
        direction === "down" ? "top-full mt-2" : "bottom-full mb-2"
      }`}
    >
      {/* Tab bar — three equal-width tabs */}
      <div role="tablist" aria-label="Attach data source" className="flex shrink-0 items-stretch border-b border-line px-2 pt-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`flex flex-1 items-center justify-center gap-1.5 border-b-2 px-3 py-2 text-[12.5px] font-medium transition-colors ${
              tab === t.id ? "border-accent text-ink" : "border-transparent text-ink-faint hover:text-ink-dim"
            }`}
          >
            {t.label}
            {t.active && <span className="h-1.5 w-1.5 rounded-full bg-accent" />}
          </button>
        ))}
      </div>

      {/* Tab body — the single scroll region, with generous bottom padding */}
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 pb-4 pt-3 [scrollbar-gutter:stable]">
        {tab === "sources" && (
          <div className="space-y-1">
            {/* Web link — expands inline to include/exclude domain controls */}
            <button
              type="button"
              onClick={() => setWebOpen((v) => !v)}
              className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left text-[13px] text-ink transition-colors hover:bg-surface-2"
            >
              <Globe2 size={16} className="shrink-0 text-ink-faint" />
              <span className="min-w-0 flex-1 truncate">Web link</span>
              {webActive && <Check size={13} className="shrink-0 text-accent-ink" />}
              <ChevronDown size={13} className={`shrink-0 text-ink-faint transition-transform ${webOpen ? "rotate-180" : ""}`} />
            </button>
            {webOpen && (
              <div className="space-y-2.5 px-2 pb-2 pt-1">
                <DomainInput
                  label="Include"
                  icon={<ShieldCheck size={12} className="text-ok" />}
                  values={trustedDomains}
                  placeholder="example.org"
                  onChange={onTrustedDomainsChange}
                />
                <DomainInput
                  label="Exclude"
                  icon={<Ban size={12} className="text-err" />}
                  values={excludedDomains}
                  placeholder="spam.example"
                  onChange={onExcludedDomainsChange}
                />
                <label className="flex cursor-pointer items-center gap-2 text-[12px] text-ink-dim">
                  <input
                    type="checkbox"
                    checked={onlyTrusted}
                    onChange={(e) => setOnlyTrusted(e.target.checked)}
                    className="h-3.5 w-3.5 accent-accent"
                  />
                  Only use included domains
                </label>
              </div>
            )}
            <p className="px-2 pt-1 text-[10.5px] leading-snug text-ink-faint">
              Scopes web search to trusted/excluded domains — connectors (SharePoint, etc.) are
              managed from the Connector menu next to the composer&apos;s + button.
            </p>
          </div>
        )}

        {tab === "table" && (
          <div className="space-y-2">
            <button
              type="button"
              onClick={() => { onOpenSchema(); onClose(); }}
              className="flex w-full items-center gap-2.5 rounded-lg border border-line px-3 py-3 text-left text-[13px] text-ink transition-colors hover:bg-surface-2"
            >
              <Table2 size={16} className="shrink-0 text-ink-faint" />
              <span className="min-w-0 flex-1">
                <span className="block font-medium">Pin rows &amp; columns</span>
                <span className="block text-[11px] text-ink-faint">Draw or paste the table you want filled.</span>
                {schemaSummary && <span className="mt-0.5 block truncate text-[11px] text-accent-ink">{schemaSummary}</span>}
              </span>
            </button>
          </div>
        )}

        {tab === "skills" && <SkillsSection />}
      </div>
    </div>
  );
}
