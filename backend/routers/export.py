from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from backend.dependencies import get_export_service, get_minutes_service
from backend.routers.http_errors import raise_http_error
from backend.schemas import ExportRequest
from backend.services.exceptions import ServiceError
from backend.services.export import ExportService
from backend.services.minutes import MinutesService

router = APIRouter(prefix="/export", tags=["export"])

MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


@router.post("")
def export_minutes_content(
    payload: ExportRequest,
    service: ExportService = Depends(get_export_service),
) -> Response:
    try:
        data, download_name = service.export(
            content=payload.content,
            filename=payload.filename,
            export_format=payload.format,
        )
    except ServiceError as exc:
        raise_http_error(exc)

    return Response(
        content=data,
        media_type=MEDIA_TYPES[payload.format],
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.get("/minutes/{filename}")
def export_saved_minutes(
    filename: str,
    format: str,
    minutes_service: MinutesService = Depends(get_minutes_service),
    export_service: ExportService = Depends(get_export_service),
) -> Response:
    try:
        document = minutes_service.get_minutes(filename)
        data, download_name = export_service.export(
            content=document.content,
            filename=document.name,
            export_format=format,
        )
    except ServiceError as exc:
        raise_http_error(exc)

    return Response(
        content=data,
        media_type=MEDIA_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )
