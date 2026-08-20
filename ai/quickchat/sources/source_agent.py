"""Wrap a scoped mini-agent as a single tool — the Subagents multi-agent
pattern (https://docs.langchain.com/oss/python/langchain/multi-agent), sized
for quickchat.

Why this shape and not the alternatives we evaluated:

- **Not deepagents' ``task()`` framework** — searchos tried it and disabled
  it (see ``searchos/agents/runtime.py::_neutralize_deepagents_builtins``):
  its subagents ran with the full tool suite (scope leak) and each call
  nested an unbounded agentic loop that blocked the outer agent for minutes.
  Both failure modes are addressed here by construction: the sub-agent only
  ever sees the tools passed in, and ``recursion_limit`` hard-caps its loop.

- **Not a formal LangGraph subgraph** (compiled graph added via
  ``add_node``) — that wires invocation decisions into static graph
  structure at build time. Our sources are chosen dynamically per question
  by the main model via tool-calling; a plain tool wrapper keeps that,
  and keeps quickchat on ``create_agent`` (no hand-built StateGraph).
  Reference point: be-api-qa uses real subgraphs+Send, but for fanning out
  per *rewritten question* — its per-*source* layer is LLM tool-calling
  inside one agent, same as here.

Parallelism is free: when the main model calls several source-agent tools in
one turn, LangGraph's ToolNode runs them concurrently (one asyncio.gather —
see langgraph/prebuilt/tool_node.py). Nothing here needs to manage that.

Context isolation is the point: the sub-agent burns its own context window
on the source's raw data (API JSON, long documents, tables) and returns a
distilled report; only that report enters the main agent's context.

Each call is **stateless** — a fresh run, no checkpointer, no memory of
previous calls. Give the sub-agent everything it needs in ``query``.

Usage (a future complex connector registers itself in
``ai/quickchat/sources/__init__.py::_SOURCE_TOOLS``):

    jira_tool = wrap_as_source_agent(
        name="jira_agent",
        description="Search and analyze Jira issues...",
        system_prompt="You are a Jira analyst... Report findings concisely.",
        tools=[jira_search, jira_get_issue],
    )
    # in _SOURCE_TOOLS: "jira": SourceTools(get_tools=lambda: [jira_tool], ...)
"""

from __future__ import annotations

from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, StructuredTool
from loguru import logger

from ai.quickchat.sources.model_tiers import ModelTier

# One sub-agent step ≈ one model call + its tool executions. 12 super-steps
# is roomy for "search, read a couple of items, summarize" flows while still
# guaranteeing a runaway sub-agent can't stall the main turn indefinitely
# (the searchos/deepagents failure mode).
_DEFAULT_RECURSION_LIMIT = 12

# Appended to every sub-agent's system prompt: the report contract its
# caller (the main agent) depends on. URLs must come back in plain text
# because the main agent writes the user-facing <cite> tags itself
# (ai/quickchat/citation.py) from what this report gives it.
_REPORT_CONTRACT = (
    "\n\nReport contract: you are a sub-agent; your final message goes to a "
    "coordinating agent, not the end user. Be concise and factual. For every "
    "claim drawn from a tool result, include the item's source URL inline as "
    "plain text (e.g. 'Source: <url>') so the coordinator can cite it. If "
    "you find nothing relevant, say so explicitly instead of padding."
)


def wrap_as_source_agent(
    *,
    name: str,
    description: str,
    system_prompt: str,
    tools: list[BaseTool],
    model: BaseChatModel | None = None,
    tier: ModelTier = ModelTier.STANDARD,
    middleware: list[AgentMiddleware] | None = None,
    recursion_limit: int = _DEFAULT_RECURSION_LIMIT,
) -> BaseTool:
    """Wrap a scoped mini-agent as a single tool the main chat agent can call.

    Args:
        name: tool name the main agent sees (e.g. ``"jira_agent"``).
        description: tool description for the main agent's tool-calling —
            say what the source contains and when to use it.
        system_prompt: the sub-agent's own instructions (its domain
            expertise); the report contract is appended automatically.
        tools: the ONLY tools this sub-agent gets. Scope isolation is the
            whole point — never pass the main agent's toolset through.
        model: explicit model instance; defaults to ``tier``'s role resolved
            at call time (so Settings-UI role overrides apply).
        tier: which quickchat role to resolve when ``model`` is None — see
            ``ai/quickchat/sources/model_tiers.py``.
        middleware: passed straight into this sub-agent's own
            ``create_agent(middleware=...)``. This is the seam for a future
            complexity-based model router: write a ``wrap_model_call``
            middleware that inspects the query and calls
            ``request.override(model=...)``, pass it here — no change needed
            to this factory. Nothing router-like exists yet (no real
            complexity signal to route on today); this only wires the plug.
        recursion_limit: hard cap on the sub-agent's super-steps.
    """

    async def _run(query: str) -> str:
        from langchain.agents import create_agent

        from searchos.config.models import get_model_for

        sub_model = model if model is not None else get_model_for(tier.value)
        # Built per call, not cached at factory time: cheap (graph build is
        # milliseconds, the model calls dominate) and it means settings/model
        # changes apply immediately, mirroring build_chat_agent's behavior.
        agent = create_agent(
            model=sub_model,
            tools=tools,
            system_prompt=system_prompt + _REPORT_CONTRACT,
            middleware=middleware or [],
        )
        logger.info("source_agent[{}]: start query={!r}", name, query)
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": query}]},
                config={"recursion_limit": recursion_limit},
            )
        except Exception as exc:  # fail soft — the main agent decides what next
            logger.warning("source_agent[{}]: failed: {}", name, exc)
            return f"Error: the {name} sub-agent failed: {exc}"
        answer = result["messages"][-1].content
        if not isinstance(answer, str):
            answer = str(answer)
        logger.info("source_agent[{}]: done, report {} chars", name, len(answer))
        return answer

    return StructuredTool.from_function(
        coroutine=_run,
        name=name,
        description=description
        + " Pass a complete, self-contained request — this agent has no memory of previous calls.",
    )
