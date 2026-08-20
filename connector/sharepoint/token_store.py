"""Compatibility facade for the shared Microsoft Graph token store.

Deliberately NOT persisted anywhere (not ``.env``, not ``web_settings.json``):
it's a short-lived (~1h) user token, not a long-lived secret, so writing it to
disk would outlive its usefulness while adding a plaintext-token-at-rest risk
for no benefit. Lost on process restart — the user re-pastes a fresh token,
same as re-logging-in.
"""

from connector.microsoft_graph.token_store import clear_token, get_token, set_token

__all__ = ["clear_token", "get_token", "set_token"]
