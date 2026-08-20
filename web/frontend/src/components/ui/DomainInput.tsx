"use client";

import { useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { X } from "lucide-react";

export function normalizeDomain(raw: string): string {
  const value = raw.trim().toLowerCase();
  if (!value) return "";
  try {
    const url = new URL(value.includes("://") ? value : `https://${value}`);
    return url.hostname.replace(/^\*\./, "").replace(/^\.|\.$/g, "");
  } catch {
    return "";
  }
}

export default function DomainInput({
  label,
  icon,
  values,
  placeholder,
  onChange,
}: {
  label: string;
  icon: ReactNode;
  values: string[];
  placeholder: string;
  onChange: (values: string[]) => void;
}) {
  const [draft, setDraft] = useState("");

  const commit = () => {
    const additions = draft.split(/[,\s]+/).map(normalizeDomain).filter(Boolean);
    if (additions.length) onChange(Array.from(new Set([...values, ...additions])));
    setDraft("");
  };

  const onKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      commit();
    } else if (event.key === "Backspace" && !draft && values.length) {
      onChange(values.slice(0, -1));
    }
  };

  return (
    <div className="block">
      <span className="mb-1.5 flex items-center gap-1.5 text-[12px] text-ink-dim">
        {icon}
        {label}
      </span>
      <span className="flex min-h-9 flex-wrap items-center gap-1 rounded-lg border border-line bg-paper px-2 py-1.5 focus-within:border-accent/50">
        {values.map((domain) => (
          <span key={domain} className="inline-flex min-w-0 items-center gap-1 rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[10.5px] text-ink">
            <span className="max-w-44 truncate">{domain}</span>
            <button
              type="button"
              aria-label={`Remove ${domain}`}
              onClick={() => onChange(values.filter((item) => item !== domain))}
              className="text-ink-faint transition-colors hover:text-ink"
            >
              <X size={10} />
            </button>
          </span>
        ))}
        <input
          aria-label={`${label} domain`}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          onBlur={commit}
          placeholder={values.length ? "Add domain" : placeholder}
          spellCheck={false}
          className="min-w-28 flex-1 bg-transparent py-0.5 text-[12px] text-ink outline-none placeholder:text-ink-faint"
        />
      </span>
    </div>
  );
}
