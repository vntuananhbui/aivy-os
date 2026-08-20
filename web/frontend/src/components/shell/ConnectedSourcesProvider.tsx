"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { DEFAULT_CONNECTED_SOURCES } from "@/components/shell/ComposerSourcesPopover";
import {
  deleteJiraConnector, deleteSharepointConnector, getJiraConnector, getSharepointConnector,
} from "@/lib/api";

interface ConnectedSourcesCtx {
  connectedSources: string[];
  toggleConnectedSource: (id: string) => void;
  showSharePointModal: boolean;
  openSharePointModal: () => void;
  closeSharePointModal: () => void;
  markSharePointConnected: () => void;
  showJiraModal: boolean;
  openJiraModal: () => void;
  closeJiraModal: () => void;
  markJiraConnected: () => void;
}

const Ctx = createContext<ConnectedSourcesCtx | null>(null);

// `<Composer>` mounts independently in three places (Landing/hero,
// Conversation/bar, ChatView/quickchat) — each used to keep its own
// `connectedSources` state, so switching between those views (e.g. landing →
// conversation right after connecting SharePoint) swapped in a fresh,
// out-of-sync instance and connected-source chips (like Google's) would
// flicker or vanish until something forced that instance to resync. Lifting
// the state here to one shared provider means every Composer reads/writes
// the same source of truth regardless of which one is currently mounted.
export function ConnectedSourcesProvider({ children }: { children: ReactNode }) {
  const [connectedSources, setConnectedSources] = useState<string[]>(DEFAULT_CONNECTED_SOURCES);
  const [showSharePointModal, setShowSharePointModal] = useState(false);
  const [showJiraModal, setShowJiraModal] = useState(false);

  useEffect(() => {
    getSharepointConnector().then((view) => {
      if (view?.connected) setConnectedSources((prev) => prev.includes("sharepoint") ? prev : [...prev, "sharepoint"]);
    });
    getJiraConnector().then((view) => {
      if (view?.connected) setConnectedSources((prev) => prev.includes("jira") ? prev : [...prev, "jira"]);
    });
  }, []);

  const toggleConnectedSource = useCallback((id: string) => {
    if (id === "sharepoint") {
      setConnectedSources((prev) => {
        if (prev.includes("sharepoint")) {
          deleteSharepointConnector().catch(() => {});
          return prev.filter((s) => s !== "sharepoint");
        }
        setShowSharePointModal(true);
        return prev;
      });
      return;
    }
    if (id === "jira") {
      setConnectedSources((prev) => {
        if (prev.includes("jira")) {
          deleteJiraConnector().catch(() => {});
          return prev.filter((s) => s !== "jira");
        }
        setShowJiraModal(true);
        return prev;
      });
      return;
    }
    setConnectedSources((prev) => prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]);
  }, []);

  const markSharePointConnected = useCallback(() => {
    setConnectedSources((prev) => prev.includes("sharepoint") ? prev : [...prev, "sharepoint"]);
  }, []);

  const markJiraConnected = useCallback(() => {
    setConnectedSources((prev) => prev.includes("jira") ? prev : [...prev, "jira"]);
  }, []);

  return (
    <Ctx.Provider
      value={{
        connectedSources,
        toggleConnectedSource,
        showSharePointModal,
        openSharePointModal: () => setShowSharePointModal(true),
        closeSharePointModal: () => setShowSharePointModal(false),
        markSharePointConnected,
        showJiraModal,
        openJiraModal: () => setShowJiraModal(true),
        closeJiraModal: () => setShowJiraModal(false),
        markJiraConnected,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useConnectedSources() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useConnectedSources must be used within a ConnectedSourcesProvider");
  return ctx;
}
