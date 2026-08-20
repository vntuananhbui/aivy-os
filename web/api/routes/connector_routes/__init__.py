"""Provider-specific HTTP adapters for external connectors.

The public API is still assembled by :mod:`api.routes.connectors`; splitting
the implementations here keeps provider HTTP concerns independent while the
existing route paths and imports remain stable.
"""

