from __future__ import annotations


class ServiceError(Exception):
    """Base class for service-layer errors."""


class ValidationError(ServiceError):
    """Invalid input or state."""


class NotFoundError(ServiceError):
    """Requested resource was not found."""


class ExternalAPIError(ServiceError):
    """Upstream model API call failed."""
