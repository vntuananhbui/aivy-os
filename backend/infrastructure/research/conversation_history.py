"""Reconstruct user↔AI turns from a filesystem conversation log.

``conversation_turns`` replays a workspace's
``conversations/orchestrator.json`` into ``[{query, answer, steers}]`` so a
reloaded session (web history reopen, TUI ``/resume``) shows the full
multi-turn dialogue instead of just title + last answer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def last_ai_text(messages: list[dict[str, Any]]) -> str:
    """Return the last non-empty assistant text from serialized messages."""
    for message in reversed(messages or []):
        if message.get("role") not in ("ai", "assistant"):
            continue
        content = message.get("content", "")
        if isinstance(content, list):
            parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            content = "\n".join(part for part in parts if part)
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""


def orchestrator_final_text(workspace: str | Path) -> str:
    """Read the orchestrator's last assistant message from a workspace."""
    import json

    path = Path(workspace) / "conversations" / "orchestrator.json"
    try:
        conversation = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return last_ai_text(conversation.get("messages", []))

# Markers the harness injects as "user" messages that are NOT user input.
_HARNESS_PREFIX = "[AUTOMATED HARNESS"
_STEER_PREFIX = "[用户追问"
# session.run() joins a follow-up preamble and the query with this separator.
_QUERY_SEP = "\n---\n当前问题："


def _msg_text(msg: dict[str, Any]) -> str:
    content = msg.get("content", "")
    if isinstance(content, list):
        content = "\n".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return str(content or "").strip()


def conversation_turns(workspace: str | Path) -> list[dict[str, Any]]:
    """Rebuild ``[{query, answer, steers}]`` from the orchestrator's persisted
    conversation log.

    Turn boundary: an assistant text message *not followed by a tool_call*
    (the orchestrator's closing message for that round). Harness-injected
    "user" messages (coverage snapshots, nudges) are ignored; live-steer
    injections become the turn's ``steers``; a follow-up's first message is
    stripped back to the bare query (the preamble precedes ``当前问题：``).
    A closing message with no new user input in between (premature-end
    resume) supersedes the previous turn's answer instead of opening a
    spurious turn.
    """
    import json

    path = Path(workspace) / "conversations" / "orchestrator.json"
    try:
        msgs = json.loads(path.read_text(encoding="utf-8", errors="replace")).get("messages", [])
    except Exception:
        return []

    turns: list[dict[str, Any]] = []
    query: str | None = None
    steers: list[str] = []

    for i, msg in enumerate(msgs):
        role = msg.get("role")
        text = _msg_text(msg)
        if role in ("user", "human"):
            if not text or text.startswith(_HARNESS_PREFIX):
                continue
            if text.startswith(_STEER_PREFIX):
                body = text.split("\n", 1)[1] if "\n" in text else ""
                body = body.split("\n\n请在当前进展", 1)[0].strip()
                if body:
                    steers.append(body)
                continue
            if _QUERY_SEP in text:
                text = text.split(_QUERY_SEP, 1)[1].strip()
            query = text
        elif role in ("ai", "assistant"):
            if msg.get("tool_calls"):
                continue
            nxt = msgs[i + 1] if i + 1 < len(msgs) else None
            if nxt is not None and nxt.get("role") == "tool_call":
                continue
            if not text:
                continue
            if query is not None:
                turns.append({"query": query, "answer": text, "steers": steers})
                query, steers = None, []
            elif turns:
                turns[-1]["answer"] = text
                if steers:
                    turns[-1]["steers"].extend(steers)
                    steers = []
    return turns
