"""Canonical SSE HTTP adapter for live QuickChat turns and approval resume."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.bootstrap.quickchat import chat_run_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None
    thinking: bool = False
    effort: Literal["low", "medium", "high", "max"] = "medium"
    web_search_enabled: bool = True


class ChatResumeRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    interrupt_id: str = Field(min_length=1)
    decision: Literal["approve", "reject", "other"]
    message: str = ""


def _sse_event(event: dict) -> str:
    kind = event["kind"]
    event_name = "token" if kind == "answer" else kind
    data = {key: value for key, value in event.items() if key != "kind"}
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"


@router.post("/chat")
async def create_chat(request: ChatRequest):
    thread_id = request.thread_id or str(uuid.uuid4())

    async def event_stream():
        yield f"event: start\ndata: {json.dumps({'thread_id': thread_id})}\n\n"
        try:
            async for event in chat_run_service.stream(
                request.message,
                thread_id=thread_id,
                thinking=request.thinking,
                effort=request.effort,
                web_search_enabled=request.web_search_enabled,
            ):
                yield _sse_event(event)
        except Exception as exc:  # noqa: BLE001
            logger.exception("chat stream failed")
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/chat/resume")
async def resume_chat(request: ChatResumeRequest):
    if request.decision == "other" and not request.message.strip():
        raise HTTPException(422, "Other requires non-empty feedback.")
    claim = await chat_run_service.claim_approval(
        thread_id=request.thread_id,
        interrupt_id=request.interrupt_id,
    )
    if claim is None:
        raise HTTPException(409, "Approval is missing, expired, or already handled.")

    async def event_stream():
        yield f"event: start\ndata: {json.dumps({'thread_id': request.thread_id})}\n\n"
        try:
            async for event in chat_run_service.resume(
                thread_id=request.thread_id,
                interrupt_id=request.interrupt_id,
                decision=request.decision,
                message=request.message,
                claim=claim,
            ):
                yield _sse_event(event)
        except Exception as exc:  # noqa: BLE001
            logger.exception("chat approval resume failed")
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
