"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronRight, File, Folder, Loader2 } from "lucide-react";

import useDialogFocus from "@/hooks/useDialogFocus";
import {
  browseSharepoint,
  putSharepointConnector,
  putSharepointSelection,
  type SharePointBrowseItem,
  type SharePointItem,
} from "@/lib/api";
import { getSharePointAccessToken } from "@/lib/msal";

interface Props {
  onConnected: () => void;
  onClose: () => void;
}

const FIELD_CLASS =
  "w-full rounded-lg border border-line bg-paper px-2.5 py-1.5 text-[12.5px] text-ink outline-none " +
  "placeholder:text-ink-faint focus-within:border-accent/50";

interface Crumb {
  id: string | undefined; // undefined = root
  name: string;
}

export default function SharePointConnectModal({ onConnected, onClose }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const firstFieldRef = useRef<HTMLButtonElement>(null);
  useDialogFocus({ containerRef: dialogRef, initialFocusRef: firstFieldRef, onClose });

  const [step, setStep] = useState<"token" | "browse">("token");
  const [accessToken, setAccessToken] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [crumbs, setCrumbs] = useState<Crumb[]>([{ id: undefined, name: "My files" }]);
  const [items, setItems] = useState<SharePointBrowseItem[]>([]);
  const [loadingFolder, setLoadingFolder] = useState(false);
  const [selected, setSelected] = useState<Map<string, SharePointItem>>(new Map());

  const currentCrumb = crumbs[crumbs.length - 1];

  useEffect(() => {
    if (step !== "browse") return;
    setLoadingFolder(true);
    setError(null);
    browseSharepoint(currentCrumb.id)
      .then((res) => setItems(res.items))
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load folder"))
      .finally(() => setLoadingFolder(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, currentCrumb.id]);

  const connectWithToken = async (token: string) => {
    if (!token.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await putSharepointConnector({ access_token: token.trim() });
      setStep("browse");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not connect to SharePoint");
    } finally {
      setSubmitting(false);
    }
  };

  const loginWithMicrosoft = async () => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const token = await getSharePointAccessToken();
      await connectWithToken(token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Microsoft login failed");
      setSubmitting(false);
    }
  };

  const openFolder = (item: SharePointBrowseItem) => {
    setCrumbs((prev) => [...prev, { id: item.id, name: item.name }]);
  };

  const goToCrumb = (index: number) => {
    setCrumbs((prev) => prev.slice(0, index + 1));
  };

  const toggleItem = (item: SharePointBrowseItem) => {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(item.id)) {
        next.delete(item.id);
      } else {
        const path = crumbs.slice(1).map((c) => c.name).join("/");
        next.set(item.id, { id: item.id, name: item.name, path, web_url: item.web_url, is_folder: item.is_folder });
      }
      return next;
    });
  };

  // Scoped to the current folder's listing — "all" means every item
  // currently on screen is picked, not every item in every folder visited.
  const allInViewSelected = items.length > 0 && items.every((item) => selected.has(item.id));

  const toggleSelectAll = () => {
    setSelected((prev) => {
      const next = new Map(prev);
      const path = crumbs.slice(1).map((c) => c.name).join("/");
      if (allInViewSelected) {
        for (const item of items) next.delete(item.id);
      } else {
        for (const item of items) {
          next.set(item.id, { id: item.id, name: item.name, path, web_url: item.web_url, is_folder: item.is_folder });
        }
      }
      return next;
    });
  };

  const finish = async () => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await putSharepointSelection(Array.from(selected.values()));
      onConnected();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save file selection");
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
        aria-labelledby="sharepoint-connect-title"
        tabIndex={-1}
        onMouseDown={(e) => e.stopPropagation()}
        className="rise-in surface flex max-h-[80vh] w-[min(480px,92vw)] flex-col rounded-2xl p-5 shadow-xl"
      >
        <h2 id="sharepoint-connect-title" className="font-serif text-[15px] text-ink">Connect SharePoint</h2>

        {step === "token" && (
          <>
            <p className="mt-1 text-[11.5px] leading-snug text-ink-faint">
              Sign in with your Microsoft account to search your OneDrive/SharePoint files. The token is
              kept in memory only — it is never written to disk, and expires after about an hour (sign in
              again when it does).
            </p>

            <button
              ref={firstFieldRef}
              type="button"
              onClick={loginWithMicrosoft}
              disabled={submitting}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-clay px-3 py-2 text-[12.5px] font-medium text-accent-ink transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? "Signing in…" : "Login with Microsoft"}
            </button>

            <button type="button" onClick={() => setShowPaste((v) => !v)}
              className="mt-3 text-[11.5px] text-ink-faint underline-offset-2 hover:text-ink-dim hover:underline">
              {showPaste ? "Hide" : "Or paste a token instead"}
            </button>

            {showPaste && (
              <div className="mt-2">
                <label className="block space-y-1">
                  <span className="text-[12px] text-ink-dim">Access token</span>
                  <textarea
                    className={`${FIELD_CLASS} h-20 resize-none font-mono text-[11px]`}
                    value={accessToken}
                    onChange={(e) => setAccessToken(e.target.value)}
                    placeholder="Paste the Graph access token here"
                    spellCheck={false}
                  />
                </label>
                <button type="button" onClick={() => connectWithToken(accessToken)}
                  disabled={!accessToken.trim() || submitting}
                  className="mt-2 rounded-lg border border-line px-3 py-1.5 text-[12.5px] text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink disabled:cursor-not-allowed disabled:opacity-50">
                  Connect with pasted token
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

        {step === "browse" && (
          <>
            <p className="mt-1 text-[11.5px] leading-snug text-ink-faint">
              Pick files or whole folders you want the agent to use. A picked folder is searched live
              (by name and content) instead of listing every file — better for folders with lots of files.
            </p>

            <div className="mt-3 flex flex-wrap items-center gap-1 text-[11.5px] text-ink-faint">
              {crumbs.map((c, i) => (
                <span key={i} className="flex items-center gap-1">
                  {i > 0 && <ChevronRight size={11} />}
                  <button type="button" onClick={() => goToCrumb(i)}
                    className={`hover:text-ink ${i === crumbs.length - 1 ? "font-medium text-ink" : ""}`}>
                    {c.name}
                  </button>
                </span>
              ))}
            </div>

            <div className="mt-2 flex items-center justify-between">
              <button
                type="button"
                onClick={toggleSelectAll}
                disabled={items.length === 0}
                className="text-[11.5px] font-medium text-accent-ink underline-offset-2 hover:underline disabled:cursor-not-allowed disabled:text-ink-faint disabled:no-underline"
              >
                {allInViewSelected ? "Deselect all" : "Select all"}
              </button>
              <span className="text-[11.5px] text-ink-faint">{items.length} item{items.length === 1 ? "" : "s"}</span>
            </div>

            <div className="mt-1.5 min-h-0 flex-1 overflow-y-auto rounded-lg border border-line">
              {loadingFolder ? (
                <div className="flex items-center justify-center gap-2 py-8 text-[12px] text-ink-faint">
                  <Loader2 size={14} className="animate-spin" /> Loading…
                </div>
              ) : items.length === 0 ? (
                <div className="py-8 text-center text-[12px] text-ink-faint">Empty folder</div>
              ) : (
                items.map((item) => (
                  <div key={item.id}
                    className="flex items-center gap-2.5 border-b border-line px-3 py-2 text-[12.5px] last:border-b-0">
                    <input
                      type="checkbox"
                      checked={selected.has(item.id)}
                      onChange={() => toggleItem(item)}
                      className="h-3.5 w-3.5 shrink-0 accent-accent"
                      title={item.is_folder ? "Pick this whole folder" : "Pick this file"}
                    />
                    {item.is_folder ? (
                      <>
                        <Folder size={14} className="shrink-0 text-ink-faint" />
                        <button type="button" onClick={() => openFolder(item)}
                          className="min-w-0 flex-1 truncate text-left text-ink hover:underline">
                          {item.name}
                        </button>
                      </>
                    ) : (
                      <>
                        <File size={14} className="shrink-0 text-ink-faint" />
                        <span className="min-w-0 flex-1 truncate text-ink">{item.name}</span>
                      </>
                    )}
                  </div>
                ))
              )}
            </div>

            {error && <p className="mt-3 text-[12px] text-err">{error}</p>}

            <div className="mt-4 flex items-center justify-between">
              <span className="text-[11.5px] text-ink-faint">
                {selected.size} file{selected.size === 1 ? "" : "s"} selected
              </span>
              <div className="flex gap-2">
                <button type="button" onClick={onClose}
                  className="rounded-lg px-3 py-1.5 text-[12.5px] text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink">
                  Cancel
                </button>
                <button type="button" onClick={finish} disabled={submitting}
                  className="rounded-lg bg-clay px-3 py-1.5 text-[12.5px] font-medium text-accent-ink transition-opacity disabled:cursor-not-allowed disabled:opacity-50">
                  {submitting ? "Saving…" : "Done"}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
