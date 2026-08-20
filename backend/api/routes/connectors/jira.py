"""Jira connector HTTP and OAuth adapters.

HTTP concerns stay here; basic connection and OAuth/provider orchestration
are delegated to backend application services.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from backend.application.connectors.errors import ConnectorServiceError
from backend.application.connectors.jira import JiraConnectRequest
from backend.application.connectors.jira_oauth import (
    JIRA_AUTHORIZE_URL as _JIRA_AUTHORIZE_URL,
    JIRA_OAUTH_SCOPES as _JIRA_OAUTH_SCOPES,
    JIRA_RESOURCES_URL as _JIRA_RESOURCES_URL,
    JIRA_TOKEN_URL as _JIRA_TOKEN_URL,
    OAUTH_STATE_TTL as _OAUTH_STATE_TTL,
)
from backend.bootstrap.connectors import jira_connector_service, jira_oauth_service

router = APIRouter(prefix="/jira", tags=["connectors:jira"])


class JiraConnect(BaseModel, extra="forbid"):
    site_url: str = Field(min_length=1)
    auth_mode: str = Field(pattern="^(cloud|server)$")
    email: str = ""
    api_token: str = ""
    personal_access_token: str = ""
    project_keys: list[str] = Field(default_factory=list)


class JiraSelectionUpdate(BaseModel, extra="forbid"):
    project_keys: list[str]


@router.get("")
async def get_jira():
    return await jira_connector_service.status()


@router.put("")
async def put_jira(req: JiraConnect):
    try:
        return await jira_connector_service.connect(
            JiraConnectRequest(
                site_url=req.site_url,
                auth_mode=req.auth_mode,
                email=req.email,
                api_token=req.api_token,
                personal_access_token=req.personal_access_token,
                project_keys=req.project_keys,
            )
        )
    except ConnectorServiceError as exc:
        raise HTTPException(400, exc.message) from exc


@router.put("/selection")
async def put_jira_selection(req: JiraSelectionUpdate):
    try:
        return await jira_connector_service.update_selection(req.project_keys)
    except ConnectorServiceError as exc:
        raise HTTPException(400, exc.message) from exc


@router.delete("")
async def delete_jira():
    await jira_connector_service.disconnect()
    return await jira_connector_service.status()


def _oauth_message_page(message_type: str, detail: str = "") -> HTMLResponse:
    import json

    payload = json.dumps({"type": message_type, "message": detail})
    html = f"""<!doctype html><html><body>
<script>
  if (window.opener) window.opener.postMessage({payload}, "*");
  window.close();
</script>
<p>{detail or "You can close this window."}</p>
</body></html>"""
    return HTMLResponse(html)


@router.get("/oauth/start")
async def jira_oauth_start():
    try:
        return RedirectResponse(await jira_oauth_service.authorization_url())
    except ConnectorServiceError as exc:
        raise HTTPException(400, exc.message) from exc


@router.get("/oauth/callback")
async def jira_oauth_callback(request: Request):
    params = request.query_params
    if params.get("error"):
        return _oauth_message_page(
            "jira-oauth-error",
            "You declined access on Jira — click 'Login with Jira' again if you want to retry.",
        )

    try:
        await jira_oauth_service.complete(
            state=params.get("state", ""),
            code=params.get("code", ""),
        )
    except ConnectorServiceError as exc:
        return _oauth_message_page("jira-oauth-error", exc.message)
    return _oauth_message_page("jira-oauth-connected")
