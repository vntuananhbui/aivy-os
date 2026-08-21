"use client";

import { useState } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";

import { deleteCommand, putCommand } from "@/lib/api";
import type { ModelsView } from "@/lib/types";
import { useSettings } from "@/components/settings/SettingsProvider";
import { Card, Row } from "@/components/settings/primitives";
import Select from "@/components/settings/controls/Select";

const NAME_RE = /^[a-zA-Z0-9_-]{1,32}$/;

/**
 * quickchat "/command" bindings: a command name (e.g. "meeting") mapped to a
 * command-agent type from the fixed catalog (ai/agents/, ai/quickchat/commands/).
 * The agent picker only ever offers `command_catalog` keys — never a
 * free-text import path, so this UI can't be used to run arbitrary code.
 */
export default function CommandsSection() {
  const { settings, status, mutate } = useSettings();
  const [newName, setNewName] = useState("");
  const [newAgent, setNewAgent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  if (!settings) return null;
  const { models } = settings;
  const commandNames = Object.keys(models.commands);
  const agentTypes = Object.keys(models.command_catalog);
  const disabled = status !== "ready";

  const rebind = (name: string, agentType: string) =>
    mutate({
      optimistic: (s) => ({
        ...s,
        models: { ...s.models, commands: { ...s.models.commands, [name]: agentType } },
      }),
      call: () => putCommand(name, agentType),
      merge: (s, res: ModelsView) => ({ ...s, models: res }),
      errorLabel: "Couldn't update command",
    });

  const remove = async (name: string) => {
    setBusy(true);
    const result = await mutate({
      call: () => deleteCommand(name),
      merge: (s, res: ModelsView) => ({ ...s, models: res }),
      errorLabel: "Couldn't delete command",
    });
    setBusy(false);
    if (result) setConfirmDelete(null);
  };

  const create = async () => {
    const name = newName.trim().replace(/^\//, "");
    if (!NAME_RE.test(name)) {
      setError("Name must be alphanumeric with _ - (max 32 chars, no leading /)");
      return;
    }
    if (commandNames.includes(name)) {
      setError(`Command /${name} already exists`);
      return;
    }
    if (!newAgent) {
      setError("Pick an agent");
      return;
    }
    setBusy(true);
    setError(null);
    const result = await mutate({
      call: () => putCommand(name, newAgent),
      merge: (s, res: ModelsView) => ({ ...s, models: res }),
      errorLabel: "Couldn't create command",
    });
    setBusy(false);
    if (result) { setNewName(""); setNewAgent(""); }
  };

  return (
    <div className="space-y-2">
      {commandNames.length === 0 ? (
        <p className="text-[12px] text-ink-faint">
          No commands yet. Add one below to route a quickchat &quot;/name&quot; message to an agent.
        </p>
      ) : (
        <Card>
          {commandNames.map((name) => (
            <Row key={name} label={`/${name}`} hint={models.command_catalog[models.commands[name]]}>
              <div className="flex items-center gap-1.5">
                <Select
                  value={models.commands[name]}
                  disabled={disabled}
                  ariaLabel={`Agent for /${name}`}
                  options={agentTypes.map((t) => ({ value: t, label: t }))}
                  onChange={(v) => rebind(name, v)}
                />
                {confirmDelete === name ? (
                  <span className="flex items-center gap-1.5 text-[11.5px]">
                    <span className="text-err">Delete?</span>
                    <button type="button" onClick={() => remove(name)} disabled={busy}
                      className="text-err transition-opacity hover:opacity-80 disabled:opacity-40">Yes</button>
                    <button type="button" onClick={() => setConfirmDelete(null)}
                      className="text-ink-faint transition-colors hover:text-ink-dim">No</button>
                  </span>
                ) : (
                  <button type="button" onClick={() => setConfirmDelete(name)} disabled={disabled}
                    aria-label={`Delete /${name}`}
                    className="rounded-lg p-1.5 text-ink-faint transition-colors hover:text-err disabled:opacity-40">
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            </Row>
          ))}
        </Card>
      )}

      <div className="surface flex flex-wrap items-center gap-1.5 rounded-xl px-3 py-2.5">
        <span className="text-[12px] text-ink-faint">/</span>
        <input value={newName} onChange={(e) => { setNewName(e.target.value); setError(null); }}
          disabled={disabled || busy} placeholder="command name" aria-label="New command name"
          spellCheck={false}
          className="surface w-32 rounded-lg px-2 py-1 font-mono text-[12px] text-ink outline-none focus:border-accent disabled:opacity-40" />
        <Select
          value={newAgent}
          disabled={disabled || busy}
          ariaLabel="Agent for new command"
          options={[{ value: "", label: "Pick an agent…" }, ...agentTypes.map((t) => ({ value: t, label: t }))]}
          onChange={setNewAgent}
        />
        <button type="button" onClick={create} disabled={disabled || busy || !newName.trim() || !newAgent}
          className="flex items-center gap-1 rounded-lg bg-accent px-2.5 py-1 text-[12px] text-white transition-opacity hover:opacity-90 disabled:opacity-25">
          {busy ? <Loader2 size={11} className="animate-spin" /> : <Plus size={11} />} Add
        </button>
      </div>
      {error && <p className="text-[12px] text-err">{error}</p>}
    </div>
  );
}
