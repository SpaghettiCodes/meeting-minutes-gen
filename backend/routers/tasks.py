from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile, WebSocket, WebSocketDisconnect, status

from backend.dependencies import get_task_service
from backend.routers.http_errors import raise_http_error
from backend.schemas import (
    CreateGenerateTaskRequest,
    CreateTaskResponse,
    TaskDetail,
    TaskSummary,
)
from backend.services.exceptions import ServiceError
from backend.services.tasks.mappers import task_to_summary
from backend.services.tasks import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _to_detail(task, *, content: str | None = None) -> TaskDetail:
    summary = task_to_summary(task)
    return TaskDetail(
        **summary.model_dump(),
        content=content,
    )


@router.post("/generate", response_model=CreateTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def create_generate_task(
    payload: CreateGenerateTaskRequest,
    service: TaskService = Depends(get_task_service),
) -> CreateTaskResponse:
    try:
        task = service.create_generate_task(
            transcript_name=payload.transcript_name,
            template_name=payload.template_name,
        )
    except ServiceError as exc:
        raise_http_error(exc)

    return CreateTaskResponse(
        task_id=task.id,
        status=task.status,
        message="Generation task queued.",
    )


@router.post(
    "/convert-template",
    response_model=CreateTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_convert_template_task(
    file: UploadFile = File(...),
    service: TaskService = Depends(get_task_service),
) -> CreateTaskResponse:
    raw = await file.read()
    try:
        task = service.create_convert_template_task(
            source_filename=file.filename or "",
            raw=raw,
        )
    except ServiceError as exc:
        raise_http_error(exc)

    return CreateTaskResponse(
        task_id=task.id,
        status=task.status,
        message="Template conversion task queued.",
    )


@router.post(
    "/transcribe",
    response_model=CreateTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_transcribe_task(
    file: UploadFile = File(...),
    service: TaskService = Depends(get_task_service),
) -> CreateTaskResponse:
    raw = await file.read()
    try:
        task = service.create_transcribe_task(
            source_filename=file.filename or "",
            raw=raw,
        )
    except ServiceError as exc:
        raise_http_error(exc)

    return CreateTaskResponse(
        task_id=task.id,
        status=task.status,
        message="Transcription task queued.",
    )


@router.get("", response_model=list[TaskSummary])
def list_tasks(
    active_only: bool = Query(default=False),
    service: TaskService = Depends(get_task_service),
) -> list[TaskSummary]:
    tasks = service.list_tasks(active_only=active_only)
    return [task_to_summary(task) for task in tasks]


@router.websocket("/ws")
async def tasks_websocket(websocket: WebSocket) -> None:
    service: TaskService = websocket.app.state.task_service
    await service.broadcaster.connect(websocket)
    try:
        summaries = [task_to_summary(task) for task in service.list_tasks()]
        await service.broadcaster.send_snapshot(websocket, summaries)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        service.broadcaster.disconnect(websocket)


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> TaskDetail:
    try:
        task = service.get_task(task_id)
        content = service.get_task_output_content(task_id)
    except ServiceError as exc:
        raise_http_error(exc)

    return _to_detail(task, content=content)
