"use client";

import { useEffect, useRef, useState } from "react";

import useDialogFocus from "@/hooks/useDialogFocus";
import {
  API_BASE,
  putJiraConnector,
  putJiraSelection,
  type JiraAuthMode,
} from "@/lib/api";

interface Props {
  onConnected: () => void;
  onClose: () => void;
}

const FIELD_CLASS =
  "w-full rounded-lg border border-line bg-paper px-2.5 py-1.5 text-[12.5px] text-ink outline-none " +
  "placeholder:text-ink-faint focus-within:border-accent/50";

export default function JiraConnectModal({ onConnected, onClose }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const firstFieldRef = useRef<HTMLButtonElement>(null);
  useDialogFocus({ containerRef: dialogRef, initialFocusRef: firstFieldRef, onClose });

  const [step, setStep] = useState<"credentials" | "projects">("credentials");
  const [authMode, setAuthMode] = useState<JiraAuthMode>("cloud");
  const [siteUrl, setSiteUrl] = useState("");
  const [email, setEmail] = useState("");
  const [apiToken, setApiToken] = useState("");
  const [personalAccessToken, setPersonalAccessToken] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  const [projectKeysInput, setProjectKeysInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const credentialReady =
    siteUrl.trim() &&
    (authMode === "cloud" ? email.trim() && apiToken.trim() : personalAccessToken.trim());

  // The OAuth callback page is served by the backend (a different origin
  // than this frontend, e.g. localhost:8000 vs 3000) and posts with
  // targetOrigin "*" since it can't know the frontend's exact origin from
  // there — so this side is the one responsible for checking `event.origin`
  // before trusting the payload, rather than the sender restricting it.
  useEffect(() => {
    const backendOrigin = new URL(API_BASE).origin;
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== backendOrigin) return;
      if (event.data?.type === "jira-oauth-connected") {
        setSubmitting(false);
        setError(null);
        setStep("projects");
      } else if (event.data?.type === "jira-oauth-error") {
        setSubmitting(false);
        setError(event.data.message || "Could not connect to Jira");
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  const loginWithJira = () => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    const popup = window.open(`${API_BASE}/api/connectors/jira/oauth/start`, "jira-oauth", "width=520,height=720");
    if (!popup) {
      setSubmitting(false);
      setError("Popup was blocked — allow popups for this site and try again.");
    }
  };

  const connect = async () => {
    if (!credentialReady || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await putJiraConnector({
        site_url: siteUrl.trim(),
        auth_mode: authMode,
        email: email.trim(),
        api_token: apiToken.trim(),
        personal_access_token: personalAccessToken.trim(),
      });
      setStep("projects");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not connect to Jira");
    } finally {
      setSubmitting(false);
    }
  };

  const finish = async () => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const projectKeys = projectKeysInput
        .split(",")
        .map((k) => k.trim().toUpperCase())
        .filter(Boolean);
      await putJiraSelection(projectKeys);
      onConnected();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save project selection");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fade-in fixed inset-0 z-50 flex items-center justify-center bg-ink/20 dark:bg-black/50"
      onMouseDown={onClose}>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="jira-connect-title"
        tabIndex={-1}
        onMouseDown={(e) => e.stopPropagation()}
        className="rise-in surface flex max-h-[80vh] w-[min(480px,92vw)] flex-col rounded-2xl p-5 shadow-xl"
      >
        <h2 id="jira-connect-title" className="font-serif text-[15px] text-ink">Connect Jira</h2>

        {step === "credentials" && (
          <>
            <p className="mt-1 text-[11.5px] leading-snug text-ink-faint">
              The credential is kept in memory only — it is never written to disk. Reconnect if the
              backend restarts.
            </p>

            <button
              ref={firstFieldRef}
              type="button"
              onClick={loginWithJira}
              disabled={submitting}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-clay px-3 py-2 text-[12.5px] font-medium text-accent-ink transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? "Waiting for login…" : "Login with Jira"}
            </button>

            <button type="button" onClick={() => setShowPaste((v) => !v)}
              className="mt-3 text-[11.5px] text-ink-faint underline-offset-2 hover:text-ink-dim hover:underline">
              {showPaste ? "Hide" : "Or paste a token instead (Cloud API token / Server-DC PAT)"}
            </button>

            {showPaste && (
              <div className="mt-3 space-y-2.5">
                <div className="flex gap-1.5 rounded-lg border border-line bg-paper p-1">
                  {(["cloud", "server"] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setAuthMode(mode)}
                      className={`flex-1 rounded-md px-2 py-1 text-[12px] font-medium transition-colors ${
                        authMode === mode ? "bg-clay text-accent-ink" : "text-ink-faint hover:text-ink-dim"
                      }`}
                    >
                      {mode === "cloud" ? "Jira Cloud" : "Server / Data Center"}
                    </button>
                  ))}
                </div>

                <label className="block space-y-1">
                  <span className="text-[12px] text-ink-dim">Site URL</span>
                  <input
                    type="url"
                    className={FIELD_CLASS}
                    value={siteUrl}
                    onChange={(e) => setSiteUrl(e.target.value)}
                    placeholder={authMode === "cloud" ? "https://yourcompany.atlassian.net" : "https://jira.yourcompany.com"}
                    spellCheck={false}
                  />
                </label>

                {authMode === "cloud" ? (
                  <>
                    <label className="block space-y-1">
                      <span className="text-[12px] text-ink-dim">Email</span>
                      <input
                        type="email"
                        className={FIELD_CLASS}
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@company.com"
                        spellCheck={false}
                      />
                    </label>
                    <label className="block space-y-1">
                      <span className="text-[12px] text-ink-dim">API token</span>
                      <input
                        type="password"
                        className={`${FIELD_CLASS} font-mono text-[11px]`}
                        value={apiToken}
                        onChange={(e) => setApiToken(e.target.value)}
                        placeholder="Paste your Atlassian API token"
                        spellCheck={false}
                      />
                    </label>
                  </>
                ) : (
                  <label className="block space-y-1">
                    <span className="text-[12px] text-ink-dim">Personal access token</span>
                    <input
                      type="password"
                      className={`${FIELD_CLASS} font-mono text-[11px]`}
                      value={personalAccessToken}
                      onChange={(e) => setPersonalAccessToken(e.target.value)}
                      placeholder="Paste your Jira Server/DC personal access token"
                      spellCheck={false}
                    />
                  </label>
                )}

                <button type="button" onClick={connect} disabled={!credentialReady || submitting}
                  className="rounded-lg border border-line px-3 py-1.5 text-[12.5px] text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink disabled:cursor-not-allowed disabled:opacity-50">
                  {submitting ? "Connecting…" : "Connect with pasted credential"}
                </button>
              </div>
            )}

            {error && <p className="mt-3 text-[12px] text-err">{error}</p>}
            <div className="mt-5 flex justify-end">
              <button type="button" onClick={onClose}
                className="rounded-lg px-3 py-1.5 text-[12.5px] text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink">
                Cancel
              </button>
            </div>
          </>
        )}

        {step === "projects" && (
          <>
            <p className="mt-1 text-[11.5px] leading-snug text-ink-faint">
              Limit the agent to specific project(s) — search and JQL will stay scoped to these keys. Leave
              empty to search every project the credential can see.
            </p>

            <label className="mt-3 block space-y-1">
              <span className="text-[12px] text-ink-dim">Project keys</span>
              <input
                type="text"
                className={FIELD_CLASS}
                value={projectKeysInput}
                onChange={(e) => setProjectKeysInput(e.target.value)}
                placeholder="PROJ, TEAM2 (comma-separated)"
                spellCheck={false}
              />
            </label>

            {error && <p className="mt-3 text-[12px] text-err">{error}</p>}
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={onClose}
                className="rounded-lg px-3 py-1.5 text-[12.5px] text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink">
                Cancel
              </button>
              <button type="button" onClick={finish} disabled={submitting}
                className="rounded-lg bg-clay px-3 py-1.5 text-[12.5px] font-medium text-accent-ink transition-opacity disabled:cursor-not-allowed disabled:opacity-50">
                {submitting ? "Saving…" : "Done"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
