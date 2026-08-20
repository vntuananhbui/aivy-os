"""Canonical HTTP adapter for QuickChat conversation history."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.bootstrap.quickchat import conversation_service

router = APIRouter(prefix="/api/conversations")


@router.get("")
async def list_conversations():
    conversations = await conversation_service.list()
    return [
        {
            "thread_id": item.thread_id,
            "title": item.title,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        for item in conversations
    ]


@router.get("/{thread_id}")
async def get_conversation(thread_id: str):
    conversation = await conversation_service.get(thread_id)
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    return {
        "thread_id": conversation.thread_id,
        "messages": conversation.messages,
        "pending_approval": conversation.pending_approval,
    }


@router.delete("/{thread_id}")
async def delete_conversation(thread_id: str):
    await conversation_service.delete(thread_id)
    return {"ok": True}
