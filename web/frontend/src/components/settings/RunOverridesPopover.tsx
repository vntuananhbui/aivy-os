"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Clock3, RotateCcw, Search, Users } from "lucide-react";

import type { EffortLevel } from "@/lib/types";
import { useSettings } from "@/components/settings/SettingsProvider";
import NumberField from "@/components/settings/controls/NumberField";
import PillGroup from "@/components/settings/controls/PillGroup";
import Toggle from "@/components/settings/controls/Toggle";
import { estimateRunBudget } from "@/lib/budgetEstimate";
import { EFFORT_GUIDANCE } from "@/lib/effortGuidance";

interface Props {
  /** "down" opens below the trigger (hero composer), "up" above (bottom bar). */
  direction: "down" | "up";
  /** "left" pins the popover to the trigger's left edge, "right" to its right. */
  align?: "left" | "right";
  onClose: () => void;
  /** Plain chat (non deep-research): only the effort row, no time/budget. */
  simple?: boolean;
}

const EFFORT_OPTIONS = [
  { value: "default", label: "Default" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Med" },
  { value: "high", label: "High" },
  { value: "max", label: "Max" },
];

export default function RunOverridesPopover({ direction, align = "left", onClose, simple = false }: Props) {
  const { settings, overrides, setOverrides, clearOverrides } = useSettings();
  const ref = useRef<HTMLDivElement>(null);
  const [popoverMaxHeight, setPopoverMaxHeight] = useState<number>();

  useLayoutEffect(() => {
    const updateMaxHeight = () => {
      const element = ref.current;
      if (!element) return;

      const rect = element.getBoundingClientRect();
      const viewportPadding = 16;
      const heightCap = Math.min(window.innerHeight * 0.78, 720);
      const availableHeight = direction === "down"
        ? window.innerHeight - rect.top - viewportPadding
        : rect.bottom - viewportPadding;
      setPopoverMaxHeight(Math.max(0, Math.floor(Math.min(heightCap, availableHeight))));
    };

    updateMaxHeight();
    window.addEventListener("resize", updateMaxHeight);
    return () => window.removeEventListener("resize", updateMaxHeight);
  }, [direction]);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const defaults = settings?.run_defaults;
  // Each effort level bundles a wall-clock budget (default_max_time_s). The
  // time field *displays* the selected level's budget, but it only becomes an
  // override (chip + request field) when the user edits it by hand — the
  // backend already applies the level's budget to an effort-only run.
  const levelTime = (lvl: string | undefined): number | undefined =>
    lvl ? settings?.effort?.levels?.[lvl as EffortLevel]?.default_max_time_s : undefined;
  const impliedTime = levelTime(overrides.effort) ?? defaults?.max_time_s ?? 1800;
  const selectedLevel = overrides.effort ?? settings?.effort.level ?? "medium";
  const estimate = settings
    ? estimateRunBudget(selectedLevel, settings.effort.levels, overrides.max_time ?? impliedTime)
    : null;
  const thinking = overrides.thinking ?? false;
  const hasOverrides = Boolean(
    overrides.effort || overrides.max_time != null || overrides.thinking != null,
  );

  return (
    <div
      ref={ref}
      style={popoverMaxHeight == null ? undefined : { maxHeight: popoverMaxHeight }}
      className={`rise-in surface absolute z-30 max-h-[min(78vh,720px)] w-[min(360px,calc(100vw-2rem))] overflow-y-auto overscroll-contain rounded-xl p-3.5 shadow-xl [scrollbar-gutter:stable] ${overrides.effort === "max" ? "max-effort-popover" : ""} ${
        direction === "down" ? "top-full mt-2" : "bottom-full mb-2"
      } ${align === "right" ? "right-0" : "left-0"}`}
    >
      <div className="mb-2.5 flex items-center justify-between">
        <span className="text-[12px] font-medium uppercase tracking-wider text-ink-faint">
          This run only
        </span>
        {hasOverrides && (
          <button
            type="button"
            onClick={clearOverrides}
            className="flex items-center gap-1 text-[12px] text-ink-dim transition-colors hover:text-ink"
          >
            <RotateCcw size={11} /> Reset
          </button>
        )}
      </div>

      <div className="space-y-3">
        {simple && (
          <div className="flex items-center justify-between gap-3">
            <span className="text-[13px] text-ink">Thinking</span>
            <Toggle
              checked={thinking}
              label="Enable thinking"
              onChange={(v) => setOverrides({ ...overrides, thinking: v ? true : undefined })}
            />
          </div>
        )}
        <div className={`flex items-center justify-between gap-3 ${simple && !thinking ? "opacity-40" : ""}`}>
          <span className="text-[13px] text-ink">Effort</span>
          <PillGroup
            ariaLabel="Run effort"
            value={overrides.effort ?? "default"}
            options={EFFORT_OPTIONS}
            disabled={simple && !thinking}
            onChange={(v) =>
              setOverrides({
                ...overrides,
                effort: v === "default" ? undefined : (v as EffortLevel),
              })
            }
          />
        </div>
        {(!simple || thinking) && (
          <p className="-mt-1 text-[10.5px] leading-relaxed text-ink-faint">
            <span className="font-medium text-ink-dim">{EFFORT_GUIDANCE[selectedLevel].title}:</span>{" "}
            {EFFORT_GUIDANCE[selectedLevel].summary}
          </p>
        )}
        {simple && !thinking && (
          <p className="-mt-1 text-[10.5px] leading-relaxed text-ink-faint">
            Instant mode — the model answers directly without reasoning first.
          </p>
        )}

        {!simple && (
          <div className="flex items-center justify-between gap-3">
            <span className="text-[13px] text-ink">Time limit</span>
            <NumberField
              value={overrides.max_time ?? impliedTime}
              placeholder={String(impliedTime)}
              suffix="s"
              onCommit={(v) =>
                setOverrides({
                  ...overrides,
                  max_time: v === impliedTime ? undefined : v,
                })
              }
            />
          </div>
        )}

        {!simple && estimate && (
          <div className="border-t border-line pt-3" aria-label="Estimated run budget">
            <div className="mb-2 text-[10px] font-medium uppercase tracking-wider text-ink-faint">Budget estimate</div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Clock3 className="mb-1 text-accent-ink" size={12} />
                <div className="text-[12px] font-medium tabular-nums text-ink">{Math.round(estimate.maxTimeSeconds / 60)}m</div>
                <div className="text-[9.5px] text-ink-faint">time cap</div>
              </div>
              <div>
                <Users className="mb-1 text-accent-ink" size={12} />
                <div className="text-[12px] font-medium tabular-nums text-ink">{estimate.parallelAgents}</div>
                <div className="text-[9.5px] text-ink-faint">parallel agents</div>
              </div>
              <div>
                <Search className="mb-1 text-accent-ink" size={12} />
                <div className="text-[12px] font-medium tabular-nums text-ink">~{estimate.searchesPerWave}</div>
                <div className="text-[9.5px] text-ink-faint">search() calls / wave</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
