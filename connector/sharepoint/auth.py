"""Delegated (user) Graph auth — the caller pastes an access token obtained
from a signed-in Microsoft session (e.g. the FPT SSO app's MSAL login),
rather than SearchOS running its own OAuth/app-only flow.

No refresh: the token is only as long-lived as whatever the user pasted (a
delegated Graph access token is normally ~1h). ``get_token`` raises once it's
expired so callers surface a clear "reconnect" message instead of a raw 401.
"""

from __future__ import annotations

from connector.microsoft_graph.auth import (
    GraphAuth,
    GraphAuthError,
    decode_token_expiry,
)

SharePointAuth = GraphAuth
SharePointAuthError = GraphAuthError

__all__ = ["SharePointAuth", "SharePointAuthError", "decode_token_expiry"]
