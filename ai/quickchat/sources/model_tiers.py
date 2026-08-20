"""Model tiers for source sub-agents (``ai.quickchat.sources.source_agent``).

Deliberately NOT the searchos pipeline roles (``chat``, ``sub_agent``,
``extraction``, ...) — those names mean specific deep-research pipeline
stages (``extraction`` = evidence extraction middleware, ``sub_agent`` =
search/explore loop, ...), and a quickchat source sub-agent is none of those
things, even when it happens to want a similarly cheap or strong model.
Reusing those names here would wrongly imply a source sub-agent "is" a
deep-research stage.

Instead, each tier maps to a role **quickchat owns** —
``quickchat_source_light`` / ``quickchat_source_strong`` (see
``searchos/config/profiles.py::ROLE_NAMES``/``builtin_roles``) — resolved
through the exact same ``get_model_for()`` mechanism as every other role, so
they're just as overridable from the Settings UI's "Roles" section. Only the
name differs; the plumbing (role → profile → Settings UI) is identical.
"""

from __future__ import annotations

from enum import Enum


class ModelTier(str, Enum):
    LIGHT = "quickchat_source_light"    # cheap/fast — simple single-step source lookups
    STANDARD = "chat"                   # default — same role quickchat's own main agent uses
    STRONG = "quickchat_source_strong"  # deep multi-step reasoning within one source
