"use client";

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatCitation } from "@/hooks/useChat";

/** Keep the agent's prose intact — the answer must render complete. Only
 *  strip lines that leak harness internals, plus a trailing References dump
 *  (the Evidence tab already lists sources with full URLs). */
export function cleanAnswer(md: string): string {
  // cut a trailing references/sources/citations section
  md = md.replace(/\n#{1,6}\s*(references|sources|citations|footnotes|url citations)\b[\s\S]*$/i, "\n");
  const out: string[] = [];
  for (const line of md.split("\n")) {
    if (/\bdo not fabricate\b/i.test(line)) continue;   // leaked schema warning
    if (/\d+\/\d+ data cells filled/i.test(line)) continue;
    out.push(line);
  }
  return out.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

// The model is told to put a <cite> tag inline right after the claim it
// supports, but doesn't always comply — it sometimes drops the marker as
// its own paragraph (blank-line separated) instead. Left alone, ReactMarkdown
// renders that as a standalone block — a big citation chip sitting alone on
// its own line, not attached to any sentence. Glue a paragraph consisting of
// nothing but marker(s) onto the end of the previous line so it always
// renders inline, regardless of where the model actually placed the tag.
function collapseStandaloneCitationMarkers(md: string): string {
  return md.replace(
    /\n{2,}((?:\[\d+\]\s*)+)(?=\n{2,}|$)/g,
    (_, markers: string) => " " + markers.replace(/\s+/g, " ").trim(),
  );
}

// Turn a literal "[1]" marker into a markdown link the ReactMarkdown `a`
// override below can recognize and render as a citation chip — anything
// already followed by "(" is a real markdown link, not our marker, so it's
// left untouched.
function linkifyCitationMarkers(md: string): string {
  return md.replace(/\[(\d+)\](?!\()/g, (full, n) => `[${full}](#cite-${n})`);
}

const CITATION_POPOVER_WIDTH = 256; // w-64
const CITATION_POPOVER_MARGIN = 8; // keep clear of the viewport edge

function CitationMark({ index, citation }: { index: number; citation?: ChatCitation }) {
  const [open, setOpen] = useState(false);
  const [popoverStyle, setPopoverStyle] = useState<React.CSSProperties>({});
  const anchorRef = useRef<HTMLAnchorElement>(null);

  if (!citation) {
    // cite() hasn't landed yet (still streaming) — show a plain, inert marker.
    return <sup className="text-[11px] text-ink-faint">[{index}]</sup>;
  }

  const handleEnter = () => {
    setOpen(true);
    const rect = anchorRef.current?.getBoundingClientRect();
    if (!rect) return;
    const centered = rect.left + rect.width / 2 - CITATION_POPOVER_WIDTH / 2;
    const clampedLeft = Math.min(
      Math.max(centered, CITATION_POPOVER_MARGIN),
      window.innerWidth - CITATION_POPOVER_WIDTH - CITATION_POPOVER_MARGIN,
    );
    setPopoverStyle({ left: clampedLeft, bottom: window.innerHeight - rect.top + 6 });
  };

  return (
    <span className="relative inline-block" onMouseEnter={handleEnter} onMouseLeave={() => setOpen(false)}>
      <a
        ref={anchorRef}
        href={citation.url || undefined}
        target="_blank"
        rel="noreferrer"
        className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-surface-2 px-1 align-super text-[10px] font-medium text-accent-ink no-underline hover:bg-clay"
      >
        {index}
      </a>
      {open && (
        <span
          style={popoverStyle}
          className="rise-in fixed z-10 w-64 rounded-lg border border-line bg-paper p-2.5 text-left text-[12px] leading-snug shadow-lg"
        >
          <span className="block truncate font-medium text-ink">{citation.title || citation.url}</span>
          {citation.quote && <span className="mt-1 block text-ink-faint">&ldquo;{citation.quote}&rdquo;</span>}
        </span>
      )}
    </span>
  );
}

export default function Answer({
  markdown, citations, streaming,
}: {
  markdown: string;
  citations?: ChatCitation[];
  /** While true, skip citation-chip linkification entirely — marker
   *  resolution (plain "[1]" text -> clickable chip) is deferred to the
   *  final post-stream render so it doesn't pop/reflow mid-stream on every
   *  token or the moment a `citation` event lands. */
  streaming?: boolean;
}) {
  const clean = cleanAnswer(markdown);
  if (!clean) return null;
  const withMarkers = citations && !streaming
    ? linkifyCitationMarkers(collapseStandaloneCitationMarkers(clean))
    : clean;
  return (
    <div className="space-y-3 break-words text-[15px] leading-[1.7] text-ink">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h2 className="font-serif text-[22px] font-semibold tracking-tight text-ink">{children}</h2>,
          h2: ({ children }) => <h3 className="mt-4 font-serif text-[18px] font-semibold text-ink">{children}</h3>,
          h3: ({ children }) => <h4 className="mt-3 text-[15px] font-semibold text-ink">{children}</h4>,
          p: ({ children }) => <p>{children}</p>,
          ul: ({ children }) => <ul className="list-disc space-y-1 pl-5 marker:text-ink-faint">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5 marker:text-ink-faint">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          a: ({ href, children }) => {
            const citeMatch = /^#cite-(\d+)$/.exec(href || "");
            if (citeMatch) {
              const index = Number(citeMatch[1]);
              return <CitationMark index={index} citation={citations?.[index - 1]} />;
            }
            return (
              <a href={href} target="_blank" rel="noreferrer" className="break-all text-accent-ink underline decoration-line-strong underline-offset-2 hover:decoration-accent">{children}</a>
            );
          },
          strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
          code: ({ children }) => <code className="break-all rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[13px] text-accent-ink">{children}</code>,
          blockquote: ({ children }) => <blockquote className="border-l-2 border-line-strong pl-3 text-ink-dim">{children}</blockquote>,
          hr: () => <hr className="border-line" />,
          table: ({ children }) => (
            <div className="overflow-x-auto rounded-lg border border-line">
              <table className="w-full text-[13.5px]">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-surface-2 text-left">{children}</thead>,
          th: ({ children }) => (
            <th className="whitespace-nowrap border-b border-line px-3 py-2 text-[12.5px] font-medium text-ink-dim">{children}</th>
          ),
          td: ({ children }) => <td className="border-b border-line px-3 py-2 align-top">{children}</td>,
          tr: ({ children }) => <tr className="last:[&>td]:border-b-0">{children}</tr>,
        }}
      >
        {withMarkers}
      </ReactMarkdown>
    </div>
  );
}
