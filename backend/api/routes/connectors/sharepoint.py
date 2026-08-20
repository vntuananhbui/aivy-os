"""SharePoint/OneDrive connector HTTP adapter."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.application.connectors.errors import ConnectorServiceError
from backend.application.connectors.models import SharePointSelectionItem
from backend.bootstrap.connectors import sharepoint_connector_service

router = APIRouter(prefix="/sharepoint", tags=["connectors:sharepoint"])


class SharePointConnect(BaseModel, extra="forbid"):
    access_token: str = Field(min_length=1)


class SharePointItemIn(BaseModel, extra="forbid"):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    path: str = ""
    web_url: str = ""
    is_folder: bool = False


class SharePointSelectionUpdate(BaseModel, extra="forbid"):
    items: list[SharePointItemIn]


@router.get("")
async def get_sharepoint():
    return await sharepoint_connector_service.status()


@router.put("")
async def put_sharepoint(req: SharePointConnect):
    try:
        return await sharepoint_connector_service.connect(req.access_token)
    except ConnectorServiceError as exc:
        raise HTTPException(400, exc.message) from exc


@router.get("/browse")
async def browse_sharepoint(folder_id: str | None = None):
    try:
        return {"items": await sharepoint_connector_service.browse(folder_id)}
    except ConnectorServiceError as exc:
        raise HTTPException(400, exc.message) from exc


@router.put("/selection")
async def put_sharepoint_selection(req: SharePointSelectionUpdate):
    try:
        return await sharepoint_connector_service.update_selection(
            [
                SharePointSelectionItem(
                    id=item.id,
                    name=item.name,
                    path=item.path,
                    web_url=item.web_url,
                    is_folder=item.is_folder,
                )
                for item in req.items
            ]
        )
    except ConnectorServiceError as exc:
        raise HTTPException(400, exc.message) from exc


@router.delete("")
async def delete_sharepoint():
    await sharepoint_connector_service.disconnect()
    return await sharepoint_connector_service.status()
