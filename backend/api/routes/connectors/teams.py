"""Microsoft Teams/Calendar connector HTTP adapter.

This module currently preserves the legacy behavior exactly. Provider
orchestration will move behind ``CalendarService`` in a later phase.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.application.connectors.errors import ConnectorServiceError
from backend.bootstrap.connectors import teams_connector_service

router = APIRouter(prefix="/teams", tags=["connectors:teams"])


class TeamsConnect(BaseModel, extra="forbid"):
    access_token: str = Field(min_length=1)


@router.get("")
async def get_teams():
    return await teams_connector_service.status()


@router.put("")
async def put_teams(req: TeamsConnect):
    try:
        return await teams_connector_service.connect(req.access_token)
    except ConnectorServiceError as exc:
        raise HTTPException(400, exc.message) from exc


@router.delete("")
async def delete_teams():
    await teams_connector_service.disconnect()
    return await teams_connector_service.status()
