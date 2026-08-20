import base64
import json

from connector.microsoft_graph.auth import decode_token_claims, delegated_scopes


def _jwt(payload: dict) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{encoded}.signature"


def test_decode_delegated_scopes_returns_sorted_permissions() -> None:
    token = _jwt({"scp": "User.ReadBasic.All Files.Read OnlineMeetings.ReadWrite", "exp": 1})

    assert delegated_scopes(token) == (
        "Files.Read",
        "OnlineMeetings.ReadWrite",
        "User.ReadBasic.All",
    )
    assert decode_token_claims(token)["exp"] == 1


def test_decode_invalid_or_app_only_token_has_no_delegated_scopes() -> None:
    assert decode_token_claims("opaque-token") == {}
    assert delegated_scopes("opaque-token") == ()
    assert delegated_scopes(_jwt({"roles": ["Files.Read.All"]})) == ()
