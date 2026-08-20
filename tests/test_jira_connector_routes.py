import asyncio

import pytest
from fastapi import HTTPException

from backend.api.routes.connectors import jira


def test_cloud_connect_rejects_missing_email_and_token_before_network() -> None:
    request = jira.JiraConnect(site_url="https://example.atlassian.net", auth_mode="cloud")

    with pytest.raises(HTTPException, match="email and api_token") as exc_info:
        asyncio.run(jira.put_jira(request))

    assert exc_info.value.status_code == 400


def test_server_connect_rejects_missing_pat_before_network() -> None:
    request = jira.JiraConnect(site_url="https://jira.example.com", auth_mode="server")

    with pytest.raises(HTTPException, match="personal_access_token") as exc_info:
        asyncio.run(jira.put_jira(request))

    assert exc_info.value.status_code == 400
