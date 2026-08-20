"""Connector application errors independent of HTTP and AI frameworks."""

from __future__ import annotations


class ConnectorServiceError(Exception):
    """Expected connector failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

