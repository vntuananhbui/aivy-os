"""Canonical AI-owned QuickChat package.

Import runtime entry points from their concrete modules (for example
``ai.quickchat.session``) to keep package initialization free of agent-graph
side effects and circular imports.
"""
