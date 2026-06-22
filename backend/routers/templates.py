from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.dependencies import get_task_service, get_template_service
from backend.routers.http_errors import raise_http_error
from backend.schemas import (
    DeleteResponse,
    FileMetadata,
    TextFileContent,
    UploadResponse,
)
from backend.services.exceptions import ServiceError
from backend.services.tasks import TaskService
from backend.services.templates import TemplateService

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[FileMetadata])
def list_templates(
    service: TemplateService = Depends(get_template_service),
) -> list[FileMetadata]:
    return [
        FileMetadata(
            name=file.name,
            size_bytes=file.size_bytes,
            modified_at=file.modified_at,
        )
        for file in service.list_templates()
    ]


@router.get("/{filename}", response_model=TextFileContent)
def get_template(
    filename: str,
    service: TemplateService = Depends(get_template_service),
) -> TextFileContent:
    try:
        document = service.get_template(filename)
    except ServiceError as exc:
        raise_http_error(exc)

    return TextFileContent(name=document.name, content=document.content)


@router.delete("/{filename}", response_model=DeleteResponse)
def delete_template(
    filename: str,
    service: TemplateService = Depends(get_template_service),
    task_service: TaskService = Depends(get_task_service),
) -> DeleteResponse:
    try:
        deleted = service.delete_template(filename)
        task_service.delete_tasks_for_template(deleted.name)
    except ServiceError as exc:
        raise_http_error(exc)

    return DeleteResponse(name=deleted.name)


@router.post("", response_model=UploadResponse, status_code=201)
async def upload_template(
    file: UploadFile = File(...),
    service: TemplateService = Depends(get_template_service),
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="Template must be a UTF-8 text file.",
        ) from exc

    try:
        saved = service.upload_template(file.filename, content)
    except ServiceError as exc:
        raise_http_error(exc)

    return UploadResponse(name=saved.name)
