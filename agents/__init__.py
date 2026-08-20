"""Legacy top-level agent facades for standalone agents that
are their own thing (meeting assistant, ...) rather than QuickChat-native
command agents (those live under ``ai/quickchat/commands/``, built directly on
``create_agent`` with quickchat's own tool/middleware conventions).

Each subfolder is one agent: ``AGENT_TYPE`` + ``build_agent(...)``, same
shape QuickChat's command dispatch expects (see
``ai/quickchat/commands/catalog.py``) so any agent here can be registered as a
``/command`` target from Settings without extra glue.
"""

from __future__ import annotations
