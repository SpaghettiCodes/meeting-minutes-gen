from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.dependencies import get_minutes_service, get_task_service
from backend.routers.http_errors import raise_http_error
from backend.schemas import DeleteResponse, FileMetadata, TextFileContent
from backend.services.exceptions import ServiceError
from backend.services.minutes import MinutesService
from backend.services.tasks import TaskService

router = APIRouter(prefix="/minutes", tags=["minutes"])


@router.get("", response_model=list[FileMetadata])
def list_minutes(
    service: MinutesService = Depends(get_minutes_service),
) -> list[FileMetadata]:
    return [
        FileMetadata(
            name=file.name,
            size_bytes=file.size_bytes,
            modified_at=file.modified_at,
        )
        for file in service.list_minutes()
    ]


@router.get("/{filename}", response_model=TextFileContent)
def get_minutes(
    filename: str,
    service: MinutesService = Depends(get_minutes_service),
) -> TextFileContent:
    try:
        document = service.get_minutes(filename)
    except ServiceError as exc:
        raise_http_error(exc)

    return TextFileContent(name=document.name, content=document.content)


@router.delete("/{filename}", response_model=DeleteResponse)
def delete_minutes(
    filename: str,
    service: MinutesService = Depends(get_minutes_service),
    task_service: TaskService = Depends(get_task_service),
) -> DeleteResponse:
    try:
        deleted = service.delete_minutes(filename)
        task_service.delete_tasks_for_output(deleted.name)
    except ServiceError as exc:
        raise_http_error(exc)

    return DeleteResponse(name=deleted.name)
