"""Delegated Microsoft Graph token validation shared by all Graph features."""

from __future__ import annotations

import base64
import json
import time
from typing import Any


class GraphAuthError(Exception):
    """The delegated Graph token is absent, malformed, or expired."""


def decode_token_claims(token: str) -> dict[str, Any]:
    """Best-effort JWT claim decoding for diagnostics only.

    This does not validate the token signature; Microsoft Graph remains the
    authorization authority. Callers must never log the raw token.
    """
    try:
        payload_b64 = token.split(".")[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def delegated_scopes(token: str) -> tuple[str, ...]:
    """Return the delegated permissions carried in the JWT ``scp`` claim."""
    scopes = decode_token_claims(token).get("scp", "")
    if not isinstance(scopes, str):
        return ()
    return tuple(sorted(scope for scope in scopes.split() if scope))


def decode_token_expiry(token: str) -> float | None:
    """Best-effort JWT expiry read; Graph remains the authorization authority."""
    try:
        return float(decode_token_claims(token)["exp"])
    except Exception:
        return None


class GraphAuth:
    def __init__(self, access_token: str):
        if not access_token or not access_token.strip():
            raise GraphAuthError("Microsoft account is not connected.")
        self._token = access_token.strip()
        self._expires_at = decode_token_expiry(self._token)

    @property
    def expires_at(self) -> float | None:
        return self._expires_at

    async def get_token(self) -> str:
        if self._expires_at is not None and time.time() >= self._expires_at:
            raise GraphAuthError(
                "Microsoft access token has expired — sign in with Microsoft again."
            )
        return self._token
