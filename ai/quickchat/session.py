"""ChatSession — thin streaming wrapper around the plain chat agent.

Sibling of ``ai.research.orchestration.session.SearchSession`` (in the research
deep-research package) but with none of the workspace/orchestrator/sub-agent
machinery: one agent, one thread, streamed token-by-token.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage
from loguru import logger

from ai.quickchat.agent import build_chat_agent, current_date_str
from ai.quickchat.citation import CitationStreamFilter
from ai.quickchat.ports import ActionWorkflowPort, ConversationMetadataPort
from ai.quickchat.tools import reset_web_tool_budget

# LangGraph counts graph supersteps here, not just LLM calls. A normal
# tool-assisted answer is model -> tools -> model (at least 3 steps), while
# paginated SharePoint reads can legitimately need several such pairs before
# the final model response. Keep this effort-aware so the UI setting also
# governs how much agent looping is allowed; the limit remains a safety fuse,
# not a mechanism for forcing a final response.
_QUICKCHAT_RECURSION_LIMITS = {
    "low": 12,
    "medium": 20,
    "high": 28,
    "max": 40,
}


def _recursion_limit_for_effort(effort: str) -> int:
    return _QUICKCHAT_RECURSION_LIMITS.get(effort, _QUICKCHAT_RECURSION_LIMITS["medium"])

_RESULT_RE = re.compile(
    r"^\[\d+\] (?P<title>.+)\nURL: (?P<url>\S+)", re.MULTILINE
)
_SOURCE_HEADER_RE = re.compile(
    r"^SOURCE TITLE: (?P<title>.+)\nSOURCE URL: (?P<url>\S+)", re.MULTILINE
)

# "/word rest of message" (rest optional, may span lines). Only actually
# dispatched as a command when word matches a key in settings.commands —
# an unrecognized "/xxx" (e.g. a real filesystem path the user typed) falls
# through to normal chat untouched, see _parse_command below.
_COMMAND_RE = re.compile(r"^/(\S+)(?:[ \t]+(.*))?$", re.DOTALL)


def _parse_command(message: str) -> tuple[str, str] | tuple[None, None]:
    """Split a leading ``/<command>`` off ``message`` iff it's a registered
    command (``searchos.config.settings.settings.commands``). Returns
    ``(command_name, rest)`` or ``(None, None)`` when there's no match —
    callers should treat the latter as "run normal chat unchanged"."""
    from searchos.config.settings import settings

    match = _COMMAND_RE.match(message.strip())
    if not match:
        return None, None
    name = match.group(1)
    if name not in settings.commands:
        return None, None
    return name, (match.group(2) or "").strip()


def _citation_with_trusted_source(
    citation: dict[str, str], trusted_sources: list[dict[str, str]]
) -> dict[str, str]:
    """Replace model-copied URL/title with the exact tool-provided values.

    Unicode-heavy SharePoint paths are especially easy for a model to alter
    by dropping a combining character, yielding a plausible-looking 404 URL.
    The quote remains model-selected, but provenance never relies on the model
    reproducing an opaque URL byte-for-byte.
    """
    title = citation.get("title", "").strip().casefold()
    if not title:
        return citation
    for source in reversed(trusted_sources):
        if source["title"].strip().casefold() == title:
            return {**citation, "url": source["url"], "title": source["title"]}
    return citation


class ChatEvent(dict):
    """``{"kind": ..., **payload}`` — a dict so it JSON-dumps straight through."""


class ChatSession:
    def __init__(
        self,
        *,
        conversation_metadata: ConversationMetadataPort,
        action_workflows: ActionWorkflowPort,
    ) -> None:
        self._conversation_metadata = conversation_metadata
        self._action_workflows = action_workflows
        # Keyed by (thinking, effort, date, active source types): one graph
        # per combo, built lazily and reused. All combos share the same
        # module-level MemorySaver, so a thread's history survives switching
        # thinking/effort mid-conversation. The date is part of the key (not
        # just the prompt) because this session is a process-wide singleton —
        # without it, the "runtime as-of date" baked into the system prompt at
        # build time would go stale for the lifetime of the process instead of
        # rolling daily. Active-sources is part of the key for the same
        # reason: attaching/detaching a source (SharePoint or any future
        # connector) mid-conversation must produce a graph whose tools
        # actually reflect that, not keep serving a toolset frozen from
        # before the change — a sorted tuple of types so key order is stable
        # regardless of registry iteration order. web_search_enabled is part
        # of the key for the same reason again — toggling the composer's
        # "Google Search" source chip must actually add/remove the tool, not
        # reuse a graph built before the toggle changed.
        self._graphs: dict[tuple[bool, str, str, tuple[str, ...], bool, bool], Any] = {}

        # Command-agent graphs, keyed by (command's agent_type, thinking,
        # effort, date) — separate cache from ``_graphs`` above since these
        # are different ``create_agent`` graphs (different tools/prompt) built
        # from ``ai.quickchat.commands.catalog``. Same date-in-key rationale as
        # ``_graphs``. Built with the SAME checkpointer as normal chat (see
        # ``_command_graph_for``), so a command turn lands in the ongoing
        # thread's history rather than a separate memory.
        self._command_graphs: dict[tuple[str, bool, str, str, bool], Any] = {}

    def _graph_for(self, thinking: bool, effort: str, web_search_enabled: bool = True):
        from ai.adapters.connectors.calendar import is_calendar_configured
        from ai.quickchat.sources import active_sources

        source_types = tuple(sorted(s.type for s in active_sources()))
        key = (
            thinking,
            effort,
            current_date_str(),
            source_types,
            web_search_enabled,
            is_calendar_configured(),
        )
        graph = self._graphs.get(key)
        if graph is None:
            logger.info(
                "quickchat: building new agent graph for key={} (cache miss, {} cached)",
                key,
                len(self._graphs),
            )
            graph = build_chat_agent(
                thinking=thinking,
                effort=effort,
                web_search_enabled=web_search_enabled,
            )
            self._graphs[key] = graph
        else:
            logger.debug("quickchat: reusing cached agent graph for key={}", key)
        return graph

    def _command_graph_for(
        self, agent_type: str, thinking: bool, effort: str, build_key: str | None = None,
    ):
        from ai.adapters.connectors.calendar import is_calendar_configured
        from ai.quickchat.commands.catalog import get_command_spec
        from ai.quickchat.persistence.checkpointer import get_checkpointer

        calendar_connected = is_calendar_configured()
        key = (
            agent_type,
            thinking,
            effort,
            build_key or current_date_str(),
            calendar_connected,
        )
        graph = self._command_graphs.get(key)
        if graph is None:
            spec = get_command_spec(agent_type)
            # Settings validated this at apply time, but config may have changed
            # since this graph's key was cached.
            if spec is None:
                raise ValueError(f"unknown command agent_type {agent_type!r}")
            logger.info("quickchat: building new command agent graph for key={}", key)
            graph = spec.build(checkpointer=get_checkpointer(), thinking=thinking, effort=effort)
            self._command_graphs[key] = graph
        else:
            logger.debug("quickchat: reusing cached command agent graph for key={}", key)
        return graph

    async def astream(
        self, message: str, *, thread_id: str, thinking: bool = False, effort: str = "medium",
        web_search_enabled: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield event dicts as the agent runs. ``kind`` is one of:

        - ``reasoning`` / ``answer`` — text chunks (``text``)
        - ``tool_call`` — a tool the agent decided to invoke (``name``, ``args``)
        - ``tool_result`` — that tool's result (``name``, ``url``/``title`` when present)
        - ``citation`` — a completed inline ``<cite>`` tag (see ``ai/quickchat/citation.py``),
          in the same order its ``[n]`` marker appears in the answer text
          (1st citation event = ``[1]``, etc.)

        ``thinking`` toggles the model's reasoning mode. ``effort`` sizes the
        reasoning budget for models that support it and the maximum number of
        graph steps available for tool-assisted work.
        """
        recursion_limit = _recursion_limit_for_effort(effort)
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": recursion_limit,
        }
        reset_web_tool_budget(thread_id)

        command_name, command_rest = _parse_command(message)
        active_workflow = await self._action_workflows.get(thread_id, active_only=True)
        agent_type: str | None = None
        if command_name is not None:
            from searchos.config.settings import settings

            agent_type = settings.commands[command_name]
            logger.info(
                "quickchat.astream: dispatching command={!r} agent_type={!r} thread_id={}",
                command_name, agent_type, thread_id,
            )
            graph = self._command_graph_for(agent_type, thinking, effort)
            input_state = {"messages": [HumanMessage(content=command_rest)]}
        elif active_workflow is not None and active_workflow.status == "collecting":
            agent_type = active_workflow.agent_type
            thinking = active_workflow.thinking
            effort = active_workflow.effort
            config["recursion_limit"] = _recursion_limit_for_effort(effort)
            graph = self._command_graph_for(
                agent_type, thinking, effort, active_workflow.graph_build_key
            )
            input_state = {"messages": [HumanMessage(content=message)]}
        else:
            try:
                from ai.quickchat.router import route_request

                decision = await route_request(message)
            except Exception as exc:
                logger.warning("quickchat router failed; falling back to normal chat: {}", exc)
                decision = None
            if decision is not None and decision.route == "teams_meeting_action":
                agent_type = "teams_meeting_action"
                graph = self._command_graph_for(agent_type, thinking, effort)
                input_state = {"messages": [HumanMessage(content=decision.request)]}
            else:
                graph = self._graph_for(thinking, effort, web_search_enabled)
                input_state = {"messages": [HumanMessage(content=message)]}

        if agent_type == "teams_meeting_action":
            workflow_build_key = (
                active_workflow.graph_build_key
                if active_workflow is not None and active_workflow.agent_type == agent_type
                else current_date_str()
            )
            await self._action_workflows.upsert(
                thread_id,
                agent_type=agent_type,
                status="collecting",
                thinking=thinking,
                effort=effort,
                graph_build_key=workflow_build_key,
            )

        logger.info(
            "quickchat.astream: start thread_id={} effort={} recursion_limit={} message={!r}",
            thread_id,
            effort,
            recursion_limit,
            message,
        )
        await self._conversation_metadata.touch(thread_id, message)

        # Fresh per answer-segment — reset whenever a tool_call starts a new
        # segment below, mirroring the frontend's own text-reset-on-tool_call
        # (useChat.ts): a <cite> span realistically never spans across a tool
        # call, so there's nothing worth carrying over.
        cite_filter = CitationStreamFilter()

        # Debug accumulators — never reset mid-turn (unlike cite_filter above),
        # so the final log dump below shows the *entire* raw model output for
        # this turn, including any pre-tool-call narration segments.
        raw_reasoning_parts: list[str] = []
        raw_answer_parts: list[str] = []
        processed_answer_parts: list[str] = []
        tool_call_count = 0
        create_action_called = False
        citation_count = 0
        trusted_sources: list[dict[str, str]] = []
        model_round = 0
        turn_started = time.monotonic()
        node_started = turn_started

        async for mode, payload in graph.astream(
            input_state, config, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                token, metadata = payload
                if metadata.get("langgraph_node") != "model":
                    continue
                reasoning = token.additional_kwargs.get("reasoning_content", "")
                if reasoning:
                    raw_reasoning_parts.append(reasoning)
                    yield {"kind": "reasoning", "text": reasoning}
                if token.content and isinstance(token.content, str):
                    raw_answer_parts.append(token.content)
                    safe_text, citations = cite_filter.feed(token.content)
                    if safe_text:
                        processed_answer_parts.append(safe_text)
                        yield {"kind": "answer", "text": safe_text}
                    for c in citations:
                        c = _citation_with_trusted_source(c, trusted_sources)
                        citation_count += 1
                        yield {"kind": "citation", **c}
            elif mode == "updates":
                for node, update in payload.items():
                    if node == "__interrupt__":
                        interrupts = list(update or [])
                        if len(interrupts) != 1:
                            raise RuntimeError(
                                "Teams meeting V1 requires exactly one pending approval."
                            )
                        interrupt = interrupts[0]
                        approval = _approval_event(interrupt)
                        if agent_type != "teams_meeting_action":
                            raise RuntimeError("Unexpected approval from a non-action agent.")
                        await self._action_workflows.upsert(
                            thread_id,
                            agent_type=agent_type,
                            status="awaiting_approval",
                            thinking=thinking,
                            effort=effort,
                            graph_build_key=workflow_build_key,
                            interrupt_id=approval["interrupt_id"],
                        )
                        yield approval
                        continue
                    messages = (update or {}).get("messages") or []
                    if node == "model":
                        model_round += 1
                        now = time.monotonic()
                        logger.info(
                            "quickchat.astream: model_round #{} completed in {:.2f}s",
                            model_round,
                            now - node_started,
                        )
                        node_started = now
                        started_tool_call = False
                        for msg in messages:
                            for call in getattr(msg, "tool_calls", None) or []:
                                started_tool_call = True
                                if not call.get("name"):
                                    continue
                                tool_call_count += 1
                                if call["name"] == "create_teams_meeting":
                                    create_action_called = True
                                logger.info(
                                    "quickchat.astream: tool_call #{} name={} args={}",
                                    tool_call_count, call["name"], call.get("args") or {},
                                )
                                yield {
                                    "kind": "tool_call",
                                    "name": call["name"],
                                    "args": call.get("args") or {},
                                }
                        if started_tool_call:
                            cite_filter = CitationStreamFilter()
                    elif node == "tools":
                        now = time.monotonic()
                        logger.info(
                            "quickchat.astream: tool_round completed in {:.2f}s",
                            now - node_started,
                        )
                        node_started = now
                        for msg in messages:
                            name = getattr(msg, "name", "") or ""
                            content = msg.content if isinstance(msg.content, str) else ""
                            logger.debug(
                                "quickchat.astream: tool_result name={} content={!r}",
                                name, content[:2000],
                            )
                            matches = list(_RESULT_RE.finditer(content))
                            matches.extend(_SOURCE_HEADER_RE.finditer(content))
                            if not matches:
                                yield {"kind": "tool_result", "name": name, "url": "", "title": ""}
                                continue
                            for match in matches:
                                source = {
                                    "url": match.group("url"),
                                    "title": match.group("title").strip(),
                                }
                                if source not in trusted_sources:
                                    trusted_sources.append(source)
                                yield {
                                    "kind": "tool_result",
                                    "name": name,
                                    **source,
                                }

        if agent_type == "teams_meeting_action":
            workflow = await self._action_workflows.get(thread_id)
            if (
                workflow is not None
                and workflow.status == "collecting"
                and create_action_called
            ):
                await self._action_workflows.upsert(
                    thread_id,
                    agent_type=agent_type,
                    status="completed",
                    thinking=thinking,
                    effort=effort,
                    graph_build_key=workflow.graph_build_key,
                )

        leftover = cite_filter.flush()
        if leftover:
            processed_answer_parts.append(leftover)
            yield {"kind": "answer", "text": leftover}

        logger.info(
            "quickchat.astream: done thread_id={} model_rounds={} tool_calls={} "
            "citations={} elapsed={:.2f}s",
            thread_id,
            model_round,
            tool_call_count,
            citation_count,
            time.monotonic() - turn_started,
        )
        logger.info(
            "quickchat.astream: RAW model answer (before citation filtering)={!r}",
            "".join(raw_answer_parts),
        )
        logger.info(
            "quickchat.astream: FINAL displayed answer (after citation filtering)={!r}",
            "".join(processed_answer_parts),
        )
        if raw_reasoning_parts:
            logger.debug(
                "quickchat.astream: RAW reasoning trace={!r}",
                "".join(raw_reasoning_parts),
            )

    async def load_thread(self, thread_id: str) -> list[dict[str, Any]] | None:
        """Reconstruct a past conversation's messages from checkpointed state,
        for the history/sidebar UI — same per-message shape ``useChat.ts``
        uses live. ``None`` if no checkpoint exists for ``thread_id``.

        Citations are recovered by re-running ``CitationStreamFilter`` over
        each AIMessage's stored text: the streaming filter in ``astream``
        above only affects what's sent over SSE live, it never mutates the
        message actually appended to graph state, so the raw ``<cite>`` tags
        are still there in the checkpoint to re-parse.
        """
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

        graph = self._graph_for(True, "medium")
        state = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        raw_messages = state.values.get("messages") if state.values else None
        if not raw_messages:
            return None

        result: list[dict[str, Any]] = []
        sources: list[dict[str, str]] = []
        for msg in raw_messages:
            if isinstance(msg, HumanMessage):
                sources = []
                result.append({"role": "user", "text": msg.content, "citations": [], "sources": []})
            elif isinstance(msg, ToolMessage):
                content = msg.content if isinstance(msg.content, str) else ""
                matches = list(_RESULT_RE.finditer(content))
                matches.extend(_SOURCE_HEADER_RE.finditer(content))
                for match in matches:
                    url = match.group("url")
                    if not any(s["url"] == url for s in sources):
                        sources.append({"url": url, "title": match.group("title").strip()})
            elif isinstance(msg, AIMessage):
                text = msg.content if isinstance(msg.content, str) else ""
                if not text:
                    continue  # tool-call-only step (no visible text yet)
                clean_text, citations = CitationStreamFilter().feed(text)
                citations = [_citation_with_trusted_source(c, sources) for c in citations]
                result.append({
                    "role": "assistant", "text": clean_text,
                    "citations": citations, "sources": list(sources),
                })
        return result

    async def delete_thread(self, thread_id: str) -> None:
        checkpointer = self._graph_for(True, "medium").checkpointer
        if checkpointer is not None and hasattr(checkpointer, "adelete_thread"):
            await checkpointer.adelete_thread(thread_id)
        await self._action_workflows.delete(thread_id)

    async def pending_approval(self, thread_id: str) -> dict[str, Any] | None:
        """Reconstruct a pending HITL card from durable checkpoint state."""
        workflow = await self._action_workflows.get(thread_id, active_only=True)
        if workflow is None or workflow.status != "awaiting_approval":
            return None
        graph = self._command_graph_for(
            workflow.agent_type,
            workflow.thinking,
            workflow.effort,
            workflow.graph_build_key,
        )
        state = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        interrupts = [
            interrupt
            for task in state.tasks
            for interrupt in (getattr(task, "interrupts", None) or [])
        ]
        if len(interrupts) != 1:
            return None
        approval = _approval_event(interrupts[0])
        if approval["interrupt_id"] != workflow.interrupt_id:
            return None
        return {k: v for k, v in approval.items() if k != "kind"}

    async def aresume(
        self,
        *,
        thread_id: str,
        interrupt_id: str,
        decision: str,
        message: str = "",
        _claim: tuple[Any, str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Resume one durable Teams approval using LangGraph Command."""
        import uuid

        from langgraph.types import Command

        if _claim is None:
            request_id = str(uuid.uuid4())
            workflow = await self._action_workflows.acquire_resume_lease(
                thread_id, interrupt_id, request_id
            )
            if workflow is None:
                raise ValueError("Approval is missing, expired, or already handled.")
        else:
            workflow, request_id = _claim
        graph = self._command_graph_for(
            workflow.agent_type,
            workflow.thinking,
            workflow.effort,
            workflow.graph_build_key,
        )
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": _recursion_limit_for_effort(workflow.effort),
        }
        if decision == "approve":
            human_decision = {"type": "approve"}
        elif decision == "reject":
            human_decision = {
                "type": "reject",
                "message": "User rejected and cancelled this meeting creation. Do not retry it.",
            }
        elif decision == "other":
            clean_message = message.strip()
            if not clean_message:
                await self._action_workflows.finish_resume(
                    thread_id, request_id, status="awaiting_approval"
                )
                raise ValueError("Other requires non-empty feedback.")
            human_decision = {
                "type": "reject",
                "message": f"User explicitly requests these corrections: {clean_message}",
            }
        else:
            await self._action_workflows.finish_resume(
                thread_id, request_id, status="awaiting_approval"
            )
            raise ValueError("Unknown approval decision.")

        saw_interrupt = False
        saw_tool_result = False
        saw_conflict_result = False
        try:
            async for mode, payload in graph.astream(
                Command(resume={"decisions": [human_decision]}),
                config,
                stream_mode=["messages", "updates"],
            ):
                if mode == "messages":
                    token, metadata = payload
                    if metadata.get("langgraph_node") != "model":
                        continue
                    reasoning = token.additional_kwargs.get("reasoning_content", "")
                    if reasoning:
                        yield {"kind": "reasoning", "text": reasoning}
                    if token.content and isinstance(token.content, str):
                        yield {"kind": "answer", "text": token.content}
                elif mode == "updates":
                    for node, update in payload.items():
                        if node == "__interrupt__":
                            interrupts = list(update or [])
                            if len(interrupts) != 1:
                                raise RuntimeError("Expected exactly one revised approval.")
                            approval = _approval_event(interrupts[0])
                            await self._action_workflows.upsert(
                                thread_id,
                                agent_type=workflow.agent_type,
                                status="awaiting_approval",
                                thinking=workflow.thinking,
                                effort=workflow.effort,
                                graph_build_key=workflow.graph_build_key,
                                interrupt_id=approval["interrupt_id"],
                            )
                            saw_interrupt = True
                            yield approval
                            continue
                        messages = (update or {}).get("messages") or []
                        if node == "tools":
                            saw_tool_result = True
                            for msg in messages:
                                content = getattr(msg, "content", "")
                                if isinstance(content, str):
                                    try:
                                        result = json.loads(content)
                                    except (TypeError, ValueError):
                                        result = None
                                    if isinstance(result, dict) and result.get("status") == "conflict":
                                        saw_conflict_result = True
                                yield {
                                    "kind": "tool_result",
                                    "name": getattr(msg, "name", "") or "",
                                    "url": "",
                                    "title": "",
                                }
            if not saw_interrupt:
                if decision == "approve" and saw_tool_result:
                    final_status = "collecting" if saw_conflict_result else "completed"
                else:
                    final_status = "cancelled"
                await self._action_workflows.finish_resume(
                    thread_id, request_id, status=final_status
                )
        except Exception:
            # Release the lease back to its pending state when execution did
            # not reach a new interrupt or terminal state.
            await self._action_workflows.finish_resume(
                thread_id, request_id, status="awaiting_approval"
            )
            raise

    async def claim_approval(
        self, *, thread_id: str, interrupt_id: str
    ) -> tuple[Any, str] | None:
        """Atomically claim an approval before opening the resume SSE stream."""
        import uuid

        request_id = str(uuid.uuid4())
        workflow = await self._action_workflows.acquire_resume_lease(
            thread_id, interrupt_id, request_id
        )
        if workflow is None:
            return None
        return workflow, request_id


def _approval_event(interrupt) -> dict[str, Any]:
    """Normalize LangChain HITLRequest without exposing framework internals."""
    value = interrupt.value
    actions = list(value.get("action_requests") or [])
    configs = list(value.get("review_configs") or [])
    if len(actions) != 1 or len(configs) != 1:
        raise RuntimeError("Teams meeting V1 supports exactly one approval action.")
    action = actions[0]
    return {
        "kind": "approval_required",
        "interrupt_id": interrupt.id,
        "agent_type": "teams_meeting_action",
        "action": {
            "name": action.get("name", ""),
            "args": action.get("args") or {},
            "description": action.get("description", ""),
        },
        "allowed_decisions": list(configs[0].get("allowed_decisions") or []),
    }
