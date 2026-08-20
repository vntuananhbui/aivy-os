"""Explicit model dependencies for one research session."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from langchain_core.language_models import BaseChatModel


@dataclass(frozen=True)
class ResearchModelBundle:
    """Role models and their display metadata, resolved before AI execution."""

    models: Mapping[str, BaseChatModel]
    distribution: Mapping[str, Mapping[str, str]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "models", MappingProxyType(dict(self.models)))
        object.__setattr__(
            self,
            "distribution",
            MappingProxyType(
                {
                    role: MappingProxyType(dict(metadata))
                    for role, metadata in self.distribution.items()
                }
            ),
        )

    def require(self, role: str) -> BaseChatModel:
        try:
            return self.models[role]
        except KeyError as exc:
            raise ValueError(f"Missing research model for role {role!r}") from exc


__all__ = ["ResearchModelBundle"]
