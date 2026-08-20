"""External-source connectors (SharePoint, Outlook, ...).

Top-level package (sibling to ``searchos``/``web``/``tools``) — connectors are
shared across features, not owned by the search agent specifically. Mirrors
the ``tools/backend`` / ``tools/search`` split: ``base.py`` defines the common
interface, each provider gets its own subpackage.
"""
