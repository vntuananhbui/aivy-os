"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { deleteTeamsConnector, getTeamsConnector, putTeamsConnector, type TeamsConnectorView } from "@/lib/api";
import { getTeamsAccessToken } from "@/lib/msal";
import { Card, Row, SectionShell, SubSection } from "@/components/settings/primitives";

/**
 * Standalone Settings section (own Microsoft login, own token) — deliberately
 * NOT the same connector as SharePoint/Jira, which live in the composer's
 * Sources popover (ComposerSourcesPopover.tsx) since they're per-question
 * data sources you attach. Teams isn't attached per-question — it backs
 * ai/agents/meeting_assistant's own Graph calls — so it belongs here instead.
 * Not wired through SettingsProvider/SettingsData (connectors aren't part of
 * that aggregate today, same reason SharePoint/Jira fetch themselves) — this
 * section owns its own fetch/mutate, mirroring how ChatHistoryRail polls its
 * own health independent of the shared settings context.
 */
export default function ConnectorsSection() {
  const [teams, setTeams] = useState<TeamsConnectorView | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { void getTeamsConnector().then(setTeams); }, []);

  const connect = async () => {
    setBusy(true);
    setError(null);
    try {
      const token = await getTeamsAccessToken();
      setTeams(await putTeamsConnector({ access_token: token }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not connect Teams");
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    setError(null);
    try {
      setTeams(await deleteTeamsConnector());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not disconnect Teams");
    } finally {
      setBusy(false);
    }
  };

  const loading = teams === undefined;
  const connected = !!teams?.connected;

  return (
    <SectionShell id="connectors" title="Connectors"
      description="External accounts that back agent capabilities directly, rather than a per-question data source (see the composer's Sources popover for SharePoint/Jira).">
      <SubSection title="Microsoft Teams"
        description="Sign in with your Microsoft account so ai/agents/meeting_assistant can create/find Teams meetings. Its own login and token, separate from SharePoint — the token is kept in memory only, never written to disk, and expires after about an hour.">
        <Card>
          <Row label="Teams" hint={loading ? "Checking…" : connected ? "Connected" : "Not connected"}>
            {loading ? (
              <Loader2 size={14} className="animate-spin text-ink-faint" />
            ) : connected ? (
              <button type="button" onClick={disconnect} disabled={busy}
                className="rounded-lg border border-line px-3 py-1.5 text-[12.5px] text-ink-dim transition-colors hover:border-err/40 hover:text-err disabled:cursor-not-allowed disabled:opacity-50">
                {busy ? "Disconnecting…" : "Disconnect"}
              </button>
            ) : (
              <button type="button" onClick={connect} disabled={busy}
                className="rounded-lg bg-clay px-3 py-1.5 text-[12.5px] font-medium text-accent-ink transition-opacity disabled:cursor-not-allowed disabled:opacity-50">
                {busy ? "Signing in…" : "Login with Microsoft"}
              </button>
            )}
          </Row>
        </Card>
        {error && <p className="mt-2 text-[12px] text-err">{error}</p>}
      </SubSection>
    </SectionShell>
  );
}
