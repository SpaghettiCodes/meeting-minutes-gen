from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.dependencies import get_generation_service
from backend.routers.http_errors import raise_http_error
from backend.schemas import GenerateRequest, GenerateResponse
from backend.services.exceptions import ServiceError
from backend.services.generation import GenerationService

router = APIRouter(prefix="/generate", tags=["generation"])


@router.post("", response_model=GenerateResponse)
def generate_minutes_endpoint(
    payload: GenerateRequest,
    service: GenerationService = Depends(get_generation_service),
) -> GenerateResponse:
    try:
        result = service.generate(
            transcript_name=payload.transcript_name,
            template_name=payload.template_name,
            output_name=payload.output_name,
        )
    except ServiceError as exc:
        raise_http_error(exc)

    return GenerateResponse(output_name=result.output_name, content=result.content)
