"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";

import type { SkillInfo, SkillOverrides } from "@/lib/types";
import { useSettings } from "@/components/settings/SettingsProvider";
import PillGroup from "@/components/settings/controls/PillGroup";

const ACCESS_MODE_OPTIONS = [
  { value: "default", label: "Default" },
  { value: "router", label: "Router" },
  { value: "only", label: "Only" },
];

type SkillCategory = "access" | "strategy" | "orchestrator";

function hasOwn(value: object | null | undefined, key: PropertyKey) {
  return value != null && Object.prototype.hasOwnProperty.call(value, key);
}

/** Per-run skill selection, extracted from RunOverridesPopover so the composer
 * "attach" popover can host it. Reads/writes ``overrides.skills`` directly. */
export default function SkillsSection() {
  const { settings, overrides, setOverrides } = useSettings();
  const [skillFilter, setSkillFilter] = useState("");
  const [skillCategory, setSkillCategory] = useState<SkillCategory>("access");

  const skillOverrides = overrides.skills;
  const accessMode = !hasOwn(skillOverrides, "access_only")
    ? "default"
    : skillOverrides?.access_only === null ? "router" : "only";
  const categories = useMemo(
    () => settings?.skills.categories ?? {},
    [settings?.skills.categories],
  );

  const patchSkills = (patch: Partial<SkillOverrides>, remove: (keyof SkillOverrides)[] = []) => {
    const next: SkillOverrides = { ...(skillOverrides ?? {}) };
    remove.forEach((field) => delete next[field]);
    Object.assign(next, patch);
    setOverrides({ ...overrides, skills: Object.keys(next).length ? next : undefined });
  };

  const skillEnabled = (category: SkillCategory, skill: SkillInfo) => {
    if (category === "access" && accessMode === "only") {
      return skillOverrides?.access_only?.includes(skill.name) ?? false;
    }
    const field = category === "access" ? "access_deny" : `${category}_deny` as const;
    if (hasOwn(skillOverrides, field)) return !skillOverrides?.[field]?.includes(skill.name);
    return skill.enabled;
  };

  const categorySkills = useMemo(
    () => (categories[skillCategory] ?? []).filter((skill) => {
      const query = skillFilter.trim().toLowerCase();
      return !query || skill.name.toLowerCase().includes(query)
        || skill.description.toLowerCase().includes(query);
    }),
    [categories, skillCategory, skillFilter],
  );

  const setAccessMode = (mode: string) => {
    if (mode === "default") {
      patchSkills({}, ["access_only", "access_deny"]);
    } else if (mode === "router") {
      patchSkills({ access_only: null }, ["access_deny"]);
    } else {
      const selected = (categories.access ?? []).filter((skill) => skill.enabled).map((skill) => skill.name);
      patchSkills({ access_only: selected }, ["access_deny"]);
    }
  };

  const toggleSkill = (category: SkillCategory, name: string) => {
    const pool = categories[category] ?? [];
    if (category === "access" && accessMode === "only") {
      const selected = new Set(skillOverrides?.access_only ?? []);
      if (selected.has(name)) selected.delete(name); else selected.add(name);
      patchSkills({ access_only: Array.from(selected) });
      return;
    }
    const enabled = new Set(pool.filter((skill) => skillEnabled(category, skill)).map((skill) => skill.name));
    if (enabled.has(name)) enabled.delete(name); else enabled.add(name);
    const denied = pool.filter((skill) => !enabled.has(skill.name)).map((skill) => skill.name);
    if (category === "access") {
      patchSkills({ access_only: null, access_deny: denied });
    } else if (category === "strategy") {
      patchSkills({ strategy_deny: denied });
    } else {
      patchSkills({ orchestrator_deny: denied });
    }
  };

  if (!settings?.skills.enable_skills) {
    return <p className="text-[12px] text-ink-faint">Skills are disabled in Settings.</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[12px] text-ink-dim">Access policy</span>
        <PillGroup
          ariaLabel="Access skill policy"
          value={accessMode}
          options={ACCESS_MODE_OPTIONS}
          onChange={setAccessMode}
        />
      </div>

      <div>
        <div role="tablist" aria-label="Skill categories" className="mb-2 flex items-center gap-1 border-b border-line">
          {(["access", "strategy", "orchestrator"] as SkillCategory[]).map((category) => {
            const pool = categories[category] ?? [];
            const count = pool.filter((skill) => skillEnabled(category, skill)).length;
            return (
              <button
                key={category}
                type="button"
                role="tab"
                aria-selected={skillCategory === category}
                onClick={() => setSkillCategory(category)}
                className={`border-b-2 px-2 py-1.5 text-[11.5px] capitalize transition-colors ${
                  skillCategory === category
                    ? "border-accent text-ink"
                    : "border-transparent text-ink-faint hover:text-ink"
                }`}
              >
                {category} <span className="tabular-nums">{count}/{pool.length}</span>
              </button>
            );
          })}
        </div>
        <label className="mb-1.5 flex items-center gap-2 rounded-lg border border-line bg-paper px-2.5 py-1.5">
          <Search size={12} className="text-ink-faint" />
          <input
            value={skillFilter}
            onChange={(event) => setSkillFilter(event.target.value)}
            placeholder={`Filter ${skillCategory} skills`}
            className="min-w-0 flex-1 bg-transparent text-[12px] text-ink outline-none placeholder:text-ink-faint"
          />
        </label>
        <div className="rounded-lg border border-line">
          {categorySkills.length ? categorySkills.map((skill) => (
            <label key={skill.name} className="flex cursor-pointer items-start gap-2 border-b border-line/60 px-1.5 py-2 last:border-b-0 hover:bg-surface-2/60">
              <input
                type="checkbox"
                checked={skillEnabled(skillCategory, skill)}
                onChange={() => toggleSkill(skillCategory, skill.name)}
                className="mt-0.5 h-3.5 w-3.5 accent-accent"
              />
              <span className="min-w-0">
                <span className="block truncate font-mono text-[11.5px] text-ink">{skill.name}</span>
                {skill.description && <span className="block truncate text-[10.5px] text-ink-faint">{skill.description}</span>}
              </span>
            </label>
          )) : (
            <p className="px-2 py-4 text-center text-[11.5px] text-ink-faint">No matching skills</p>
          )}
        </div>
        {skillCategory === "access" && accessMode === "default" && (
          <p className="mt-1.5 text-[10.5px] text-ink-faint">Changing a skill switches this run to Router mode.</p>
        )}
      </div>
    </div>
  );
}
