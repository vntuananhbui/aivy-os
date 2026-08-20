"use client";

import { putRoles } from "@/lib/api";
import { useSettings } from "@/components/settings/SettingsProvider";
import { Card, OfflineSkeleton, Row, SectionShell, SubSection } from "@/components/settings/primitives";
import Select from "@/components/settings/controls/Select";
import NewProfileCard from "@/components/settings/models/NewProfileCard";
import ProfileCard from "@/components/settings/models/ProfileCard";
import ProviderConnections from "@/components/settings/models/ProviderConnections";
import CommandsSection from "@/components/settings/models/CommandsSection";
import ProviderDiagnosticPanel from "@/components/settings/diagnostics/ProviderDiagnosticPanel";

const SECTION_DESC =
  "Providers, model cards, and role bindings. API keys are stored in .env and never shown.";

export default function ModelsSection() {
  const { settings, status, mutate } = useSettings();

  if (!settings) {
    return (
      <SectionShell id="models" title="Models" description={SECTION_DESC}>
        <OfflineSkeleton />
      </SectionShell>
    );
  }

  const { models } = settings;
  const disabled = status !== "ready";
  const profileNames = Object.keys(models.profiles);

  const bindRole = (role: string, profile: string) =>
    mutate({
      optimistic: (s) => ({
        ...s,
        models: { ...s.models, roles: { ...s.models.roles, [role]: profile } },
      }),
      call: () => putRoles({ [role]: profile }),
      merge: (s, res) => ({
        ...s,
        models: { ...s.models, roles: res.roles, role_overrides: res.role_overrides },
      }),
      errorLabel: "Couldn't bind role",
    });

  // "" = no fallback configured for this role (ModelFallbackMiddleware skips
  // it) — distinct from a real profile name, so the API only ever receives
  // an actual profile when the user picks one.
  const bindFallbackRole = (role: string, profile: string) =>
    mutate({
      optimistic: (s) => ({
        ...s,
        models: { ...s.models, fallback_roles: { ...s.models.fallback_roles, [role]: profile } },
      }),
      call: () => putRoles({}, profile ? { [role]: profile } : {}),
      merge: (s, res) => ({
        ...s,
        models: { ...s.models, fallback_roles: res.fallback_roles, fallback_role_overrides: res.fallback_role_overrides },
      }),
      errorLabel: "Couldn't bind fallback role",
    });

  return (
    <SectionShell id="models" title="Models" description={SECTION_DESC}>
      <div className="space-y-8">
        <SubSection title="Providers"
          description="Define your provider connections — an endpoint plus one or more API keys. Vendor presets pre-fill a new connection; model cards below point at these by name and inherit protocol / endpoint / key.">
          <ProviderConnections />
          <ProviderDiagnosticPanel />
        </SubSection>

        <SubSection title="Models"
          description="Each model card points at a provider connection above and sets a model id + sampling (temperature, thinking). Roles pick from these.">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {Object.entries(models.profiles).map(([name, p]) => (
              <ProfileCard key={name} name={name} profile={p} disabled={disabled} />
            ))}
            <NewProfileCard disabled={disabled} />
          </div>
        </SubSection>

        <SubSection title="Roles"
          description="Bind each agent role to a model, plus an optional fallback — used when the primary model errors (different provider recommended, so a primary outage doesn't take the fallback down too).">
          <Card>
            {Object.entries(models.roles).map(([role, profile]) => {
              const keyMissing = models.profiles[profile] && !models.profiles[profile].api_key_set;
              const fallbackProfile = models.fallback_roles[role] ?? "";
              return (
                <Row key={role} label={role}
                  hint={keyMissing ? `${models.profiles[profile].api_key_env} not set — runs will fail` : undefined}>
                  <div className="flex items-center gap-2">
                    <Select
                      value={profile}
                      disabled={disabled}
                      ariaLabel={`Model profile for ${role}`}
                      options={profileNames.map((n) => ({ value: n, label: n }))}
                      onChange={(v) => bindRole(role, v)}
                    />
                    <span className="text-[12px] text-ink-faint">fallback</span>
                    <Select
                      value={fallbackProfile}
                      disabled={disabled}
                      ariaLabel={`Fallback model profile for ${role}`}
                      options={[{ value: "", label: "None" }, ...profileNames.map((n) => ({ value: n, label: n }))]}
                      onChange={(v) => bindFallbackRole(role, v)}
                    />
                  </div>
                </Row>
              );
            })}
          </Card>
        </SubSection>

        <SubSection title="Commands"
          description="Bind a quickchat &quot;/name&quot; message to an agent from the fixed catalog below (agents/, quickchat/commands/) — never a free-text path.">
          <CommandsSection />
        </SubSection>
      </div>
    </SectionShell>
  );
}
