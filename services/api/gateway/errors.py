"""Gateway exception hierarchy."""

from __future__ import annotations


class GatewayError(Exception):
    """Base exception for all gateway failures."""


class BudgetExceededError(GatewayError):
    """Raised when daily spend limit or reservation is exceeded."""


class KillSwitchActiveError(GatewayError):
    """Raised when the LLM egress kill switch is engaged."""


class PolicyViolationError(GatewayError):
    """Raised when a request violates routing or model policy."""


class AdapterError(GatewayError):
    """Raised when the underlying provider adapter fails."""


class ProviderRefusalError(GatewayError):
    """Raised when the model refuses to answer due to safety or policy."""
