"""Centralized LLM construction — driven by settings.profiles + settings.roles.

Usage::

    from searchos.config.models import get_model_for

    orchestrator = get_model_for("orchestrator")
    judge        = get_model_for("judge")

Roles are listed in ``settings.ROLE_NAMES``. Each role is bound to a profile
in ``settings.roles``; each profile spec lives in ``settings.profiles``.
Override at runtime via env vars, e.g. ``SF_ROLES__JUDGE=glm5-strong``.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.language_models import BaseChatModel

from searchos.config.settings import ROLE_NAMES, ModelProfile, settings
from searchos.util.token_tracker import TokenTrackingCallback


def _patch_reasoning_content() -> None:
    """Preserve ``reasoning_content`` (GLM-5 / DeepSeek-R1 / QwQ) into
    AIMessage.additional_kwargs — langchain-openai 1.x drops it.
    Ref: https://github.com/langchain-ai/langchain/issues/35059
    """
    import langchain_openai.chat_models.base as _base
    from langchain_core.messages import AIMessage

    _original_ccr = _base.ChatOpenAI._create_chat_result

    def _patched_ccr(
        self: "_base.ChatOpenAI",
        response: Any,
        generation_info: dict | None = None,
    ) -> Any:
        result = _original_ccr(self, response, generation_info)
        if not isinstance(response, dict):
            choices = getattr(response, "choices", None) or []
            for i, choice in enumerate(choices):
                msg = getattr(choice, "message", None)
                if msg is None:
                    continue
                extras = getattr(msg, "model_extra", None) or {}
                rc = extras.get("reasoning_content", "")
                if rc and i < len(result.generations):
                    gen_msg = result.generations[i].message
                    if isinstance(gen_msg, AIMessage):
                        gen_msg.additional_kwargs["reasoning_content"] = rc
        return result

    if not getattr(_base, "_sf_reasoning_patched", False):
        _base.ChatOpenAI._create_chat_result = _patched_ccr
        _base._sf_reasoning_patched = True  # type: ignore[attr-defined]


def _patch_reasoning_content_streaming() -> None:
    """Same as ``_patch_reasoning_content`` but for the streaming path —
    ``_convert_chunk_to_generation_chunk`` builds each ``AIMessageChunk`` from
    the raw delta and drops unknown fields (``reasoning_content``) same as
    the non-streaming result object.
    """
    import langchain_openai.chat_models.base as _base
    from langchain_core.messages import AIMessageChunk

    _original_ccgc = _base.ChatOpenAI._convert_chunk_to_generation_chunk

    def _patched_ccgc(
        self: "_base.ChatOpenAI",
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> Any:
        result = _original_ccgc(self, chunk, default_chunk_class, base_generation_info)
        choices = chunk.get("choices", []) or chunk.get("chunk", {}).get("choices", [])
        if result is not None and choices and isinstance(result.message, AIMessageChunk):
            delta = choices[0].get("delta") or {}
            rc = delta.get("reasoning_content", "")
            if rc:
                result.message.additional_kwargs["reasoning_content"] = rc
        return result

    if not getattr(_base, "_sf_reasoning_stream_patched", False):
        _base.ChatOpenAI._convert_chunk_to_generation_chunk = _patched_ccgc
        _base._sf_reasoning_stream_patched = True  # type: ignore[attr-defined]


_patch_reasoning_content()
_patch_reasoning_content_streaming()


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def resolve_profile(role: str) -> ModelProfile:
    """Look up the ModelProfile bound to a role. Raises on misconfiguration."""
    if role not in ROLE_NAMES:
        raise ValueError(
            f"Unknown role {role!r}. Known roles: {ROLE_NAMES}"
        )
    profile_name = settings.roles.get(role)
    if not profile_name:
        raise ValueError(
            f"Role {role!r} has no profile binding in settings.roles. "
            f"Set settings.roles[{role!r}] to one of: {list(settings.profiles)}"
        )
    profile = settings.profiles.get(profile_name)
    if profile is None:
        raise ValueError(
            f"Role {role!r} → profile {profile_name!r} not in settings.profiles. "
            f"Available: {list(settings.profiles)}"
        )
    return profile


def _rate_limit_kwargs(profile: ModelProfile) -> dict[str, Any]:
    """Shared limiter + usage callback for the profile's quota bucket."""
    from searchos.util.llm_rate_limiter import get_shared_rate_limiter

    limiter, usage_cb = get_shared_rate_limiter(
        (profile.api_base, profile.model, profile.api_key_env),
        rpm=profile.rpm, tpm=profile.tpm,
    )
    if not (profile.rpm or profile.tpm):
        return {}
    return {"rate_limiter": limiter, "callbacks": [usage_cb]}


def get_model_for(
    role: str,
    *,
    model_override: str | None = None,
    reasoning_effort: str | None = None,
) -> BaseChatModel:
    """Build a fresh BaseChatModel for the role.

    ``model_override`` changes only the wire model id while retaining the
    role's configured provider, endpoint, key env, protocol, and limits. It is
    intended for narrow CLI overrides; normal runtime calls should omit it.

    ``reasoning_effort`` is the standard OpenAI request param
    ("none"/"minimal"/"low"/"medium"/"high") that controls how much a hybrid
    thinking model reasons before answering — separate from ``max_tokens``,
    which only caps output *length* and will truncate a reasoning model
    mid-thought with no answer at all if set too low for the budget it needs.
    Wired for openai/openai_compatible and azure_openai (native
    ``ChatOpenAI``/``AzureChatOpenAI`` field); anthropic profiles ignore it.
    """
    profile = resolve_profile(role)
    if model_override:
        profile = profile.model_copy(update={"model": model_override})
    return _build_model_from_profile(profile, tracking_label=role, reasoning_effort=reasoning_effort)


def get_model_for_profile(
    profile_name: str,
    *,
    tracking_label: str = "",
    reasoning_effort: str | None = None,
) -> BaseChatModel:
    """Build a fresh ``BaseChatModel`` straight from a profile name — no role
    indirection. Used where a role's *fallback* is configured directly as a
    profile (``settings.fallback_roles``), not a role of its own; everything
    else (provider branching, thinking-style, rate limits) is identical to
    ``get_model_for``.
    """
    if profile_name not in settings.profiles:
        raise RuntimeError(
            f"Unknown profile {profile_name!r} — not in settings.profiles "
            f"({list(settings.profiles)})."
        )
    profile = settings.profiles[profile_name]
    return _build_model_from_profile(
        profile, tracking_label=tracking_label or profile_name, reasoning_effort=reasoning_effort,
    )


def _build_model_from_profile(
    profile: ModelProfile, *, tracking_label: str, reasoning_effort: str | None,
) -> BaseChatModel:
    # api_key_fallback covers local servers (Ollama/vLLM) that need a
    # placeholder key even without auth.
    api_key = os.environ.get(profile.api_key_env, "") or profile.api_key_fallback
    if not api_key:
        # Fail loud — a silent empty key produces cryptic deep 401s.
        raise RuntimeError(
            f"{tracking_label!r} → profile uses api_key_env={profile.api_key_env!r}, "
            f"but that env var is not set. Add it to your .env file "
            f"(quick start: SF_PROVIDER + key, see searchos/config/providers.py)."
        )

    rl_kwargs = _rate_limit_kwargs(profile)
    callbacks = [TokenTrackingCallback(role=tracking_label), *rl_kwargs.pop("callbacks", [])]

    if profile.provider in ("openai_compatible", "openai"):
        from langchain_openai import ChatOpenAI

        kwargs: dict[str, Any] = {
            "model": profile.model,
            "api_key": api_key,
            "max_tokens": profile.max_tokens,
            "max_retries": settings.llm_max_retries,
            "callbacks": callbacks,
            **rl_kwargs,
        }
        if profile.temperature is not None:
            kwargs["temperature"] = profile.temperature
        if profile.api_base:
            kwargs["base_url"] = profile.api_base
        if reasoning_effort is not None:
            kwargs["reasoning_effort"] = reasoning_effort
        # How the thinking switch is spelled differs per gateway; strict APIs
        # (OpenAI/Gemini/OpenRouter) reject unknown params, so "none" sends
        # nothing at all.
        #
        # These gateways only support on/off, not a graduated depth — so a
        # per-call ``reasoning_effort`` (when the caller passed one) overrides
        # the profile's static default instead of being silently ignored by
        # it. Without this, callers like quickchat that vary effort/thinking
        # per request would always get the profile's fixed enable_thinking
        # value no matter what the user picked.
        thinking_on = (
            reasoning_effort not in (None, "none")
            if reasoning_effort is not None
            else bool(profile.enable_thinking)
        )
        extra_body: dict[str, Any] = {}
        if profile.thinking_style == "chat_template_kwargs":
            # vLLM / SiliconFlow 系网关只认 chat_template_kwargs 里的开关；
            # 顶层形式会被静默忽略。
            extra_body["chat_template_kwargs"] = {
                "enable_thinking": thinking_on,
            }
        elif profile.thinking_style == "enable_thinking":
            # DashScope compatible-mode top-level switch.
            extra_body["enable_thinking"] = thinking_on
        elif profile.thinking_style == "kimi_chat_template":
            # Kimi K2.5 spells the same chat_template_kwargs envelope with its
            # own key ("thinking", not "enable_thinking") — and defaults ON, so
            # this is mainly used to explicitly turn it OFF (instant mode).
            extra_body["chat_template_kwargs"] = {
                "thinking": thinking_on,
            }
        # Deep-merge profile extra_body so it doesn't clobber the whole dict.
        profile_extra = dict(profile.extra)
        profile_extra_body = profile_extra.pop("extra_body", None)
        if isinstance(profile_extra_body, dict):
            for k, v in profile_extra_body.items():
                if isinstance(v, dict) and isinstance(extra_body.get(k), dict):
                    extra_body[k] = {**extra_body[k], **v}
                else:
                    extra_body[k] = v
        if extra_body:
            kwargs["extra_body"] = extra_body
        kwargs.update(profile_extra)
        return ChatOpenAI(**kwargs)

    if profile.provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI

        kwargs = {
            # Azure deployments are addressed by name, not model id — profile.model
            # doubles as the deployment name (Azure convention: deployment named
            # after the underlying model).
            "azure_deployment": profile.model,
            "azure_endpoint": profile.api_base,
            "api_version": profile.api_version or "2025-04-01-preview",
            "api_key": api_key,
            "max_tokens": profile.max_tokens,
            "max_retries": settings.llm_max_retries,
            "callbacks": callbacks,
            **rl_kwargs,
        }
        if profile.temperature is not None:
            kwargs["temperature"] = profile.temperature
        if reasoning_effort is not None:
            kwargs["reasoning_effort"] = reasoning_effort
        kwargs.update(profile.extra)
        return AzureChatOpenAI(**kwargs)

    if profile.provider == "anthropic":
        # Lazy import — anthropic is optional.
        from langchain_anthropic import ChatAnthropic

        kwargs = {
            "model": profile.model,
            "api_key": api_key,
            "max_tokens": profile.max_tokens,
            "max_retries": settings.llm_max_retries,
            "callbacks": callbacks,
            **rl_kwargs,
        }
        if profile.temperature is not None:
            kwargs["temperature"] = profile.temperature
        # Custom Anthropic-compatible gateway — pass base_url so the
        # SDK routes to the override instead of api.anthropic.com.
        if profile.api_base:
            kwargs["base_url"] = profile.api_base
        kwargs.update(profile.extra)
        return ChatAnthropic(**kwargs)

    raise ValueError(f"Unsupported provider: {profile.provider!r}")


__all__ = ["get_model_for", "get_model_for_profile", "resolve_profile"]
