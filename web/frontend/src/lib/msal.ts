"use client";

import { PublicClientApplication } from "@azure/msal-browser";

// Public client identifiers (not secrets — an SPA public-client app has no
// client secret, this is the normal thing to embed in frontend code). Set
// per-environment in .env.local — see .env.example.
const CLIENT_ID = process.env.NEXT_PUBLIC_MSAL_CLIENT_ID ?? "";
const TENANT_ID = process.env.NEXT_PUBLIC_MSAL_TENANT_ID ?? "";

if (!CLIENT_ID || !TENANT_ID) {
  throw new Error(
    "Missing NEXT_PUBLIC_MSAL_CLIENT_ID / NEXT_PUBLIC_MSAL_TENANT_ID — set them in .env.local (see .env.example)."
  );
}

const msalConfig = {
  auth: {
    clientId: CLIENT_ID,
    authority: `https://login.microsoftonline.com/${TENANT_ID}`,
    // Dynamic (not hardcoded like the fe app's :5173) so dev/prod both work —
    // must be pre-registered as an allowed SPA redirect URI in the app
    // registration, or the popup fails with a redirect-URI mismatch.
    redirectUri: typeof window !== "undefined" ? window.location.origin : undefined,
  },
};

let instance: PublicClientApplication | null = null;

function getMsalInstance(): PublicClientApplication {
  if (!instance) instance = new PublicClientApplication(msalConfig);
  return instance;
}

// Explicit scopes, NOT "https://graph.microsoft.com/.default" — .default
// returns whatever happens to already be admin-consented for the app
// registration as one bundle, which silently dropped Files.*/Sites.* for
// SharePoint once Teams scopes were added (see
// connector/microsoft_graph/token_store.py). Two separate scope lists, two
// separate logins/tokens (connector.sharepoint vs connector.teams
// token_store on the backend). If Microsoft returns a SharePoint-login token
// that already includes Calendars.ReadWrite, the backend can safely activate
// Calendar too without asking for a redundant second popup.
const SHAREPOINT_SCOPES = ["Files.Read", "Sites.Read.All", "User.Read"];
const TEAMS_SCOPES = ["Calendars.ReadWrite", "User.Read"];

function logGraphTokenPermissions(label: string, accessToken: string): void {
  try {
    const payloadPart = accessToken.split(".")[1];
    const normalized = payloadPart.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const claims = JSON.parse(atob(padded)) as Record<string, unknown>;
    const scopes = typeof claims.scp === "string" ? claims.scp.split(" ").filter(Boolean).sort() : [];
    console.info(`[Microsoft Graph] ${label} login token permissions`, {
      tokenType: claims.scp ? "delegated" : "app-only-or-unknown",
      tenantId: claims.tid ?? "unknown",
      clientId: claims.appid ?? claims.azp ?? "unknown",
      expiresAt: typeof claims.exp === "number" ? new Date(claims.exp * 1000).toISOString() : "unknown",
      delegatedScopes: scopes,
    });
  } catch (error) {
    console.warn("[Microsoft Graph] Could not decode token claims for permission debugging", error);
  }
}

async function loginAndGetToken(label: string, scopes: string[]): Promise<string> {
  const msal = getMsalInstance();
  await msal.initialize();
  const response = await msal.loginPopup({ scopes });
  logGraphTokenPermissions(label, response.accessToken);
  return response.accessToken;
}

// One popup does login + Graph consent + token acquisition in a single call.
export const getSharePointAccessToken = () => loginAndGetToken("SharePoint", SHAREPOINT_SCOPES);
export const getTeamsAccessToken = () => loginAndGetToken("Teams", TEAMS_SCOPES);
