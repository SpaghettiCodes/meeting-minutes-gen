from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.dependencies import get_task_service, get_transcript_service
from backend.routers.http_errors import raise_http_error
from backend.schemas import DeleteResponse, FileMetadata, TextFileContent, UploadResponse
from backend.services.exceptions import ServiceError
from backend.services.tasks import TaskService
from backend.services.transcripts import TranscriptService

router = APIRouter(prefix="/transcripts", tags=["transcripts"])


@router.get("", response_model=list[FileMetadata])
def list_transcripts(
    service: TranscriptService = Depends(get_transcript_service),
) -> list[FileMetadata]:
    return [
        FileMetadata(
            name=file.name,
            size_bytes=file.size_bytes,
            modified_at=file.modified_at,
        )
        for file in service.list_transcripts()
    ]


@router.get("/{filename}", response_model=TextFileContent)
def get_transcript(
    filename: str,
    service: TranscriptService = Depends(get_transcript_service),
) -> TextFileContent:
    try:
        document = service.get_transcript(filename)
    except ServiceError as exc:
        raise_http_error(exc)

    return TextFileContent(name=document.name, content=document.content)


@router.delete("/{filename}", response_model=DeleteResponse)
def delete_transcript(
    filename: str,
    service: TranscriptService = Depends(get_transcript_service),
    task_service: TaskService = Depends(get_task_service),
) -> DeleteResponse:
    try:
        deleted = service.delete_transcript(filename)
        task_service.delete_tasks_for_transcript(deleted.name)
    except ServiceError as exc:
        raise_http_error(exc)

    return DeleteResponse(name=deleted.name)


@router.post("", response_model=UploadResponse, status_code=201)
async def upload_transcript(
    file: UploadFile = File(...),
    service: TranscriptService = Depends(get_transcript_service),
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="Transcript must be a UTF-8 text file.",
        ) from exc

    try:
        saved = service.upload_transcript(file.filename, content)
    except ServiceError as exc:
        raise_http_error(exc)

    return UploadResponse(name=saved.name)
