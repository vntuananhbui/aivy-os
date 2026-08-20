"""Backend-owned persistence adapters for research runs.

Import concrete adapters from their defining modules. Keeping this package
initializer dependency-free prevents cycles while legacy workspace facades
are still present during migration.
"""

__all__: list[str] = []
