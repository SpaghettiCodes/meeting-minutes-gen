from __future__ import annotations

from fastapi import HTTPException

from backend.services.exceptions import (
    ExternalAPIError,
    NotFoundError,
    ServiceError,
    ValidationError,
)


def raise_http_error(exc: ServiceError) -> None:
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ExternalAPIError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc
