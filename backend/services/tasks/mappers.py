from __future__ import annotations

from backend.models.task import ConvertTemplateTaskPayload, GenerateTaskPayload, TranscribeTaskPayload, Task
from backend.schemas import TaskSummary


def task_to_summary(task: Task) -> TaskSummary:
    transcript_name = None
    template_name = None
    source_filename = None

    if isinstance(task.payload, GenerateTaskPayload):
        transcript_name = task.payload.transcript_name
        template_name = task.payload.template_name
    elif isinstance(task.payload, ConvertTemplateTaskPayload):
        source_filename = task.payload.source_filename
    elif isinstance(task.payload, TranscribeTaskPayload):
        source_filename = task.payload.source_filename

    return TaskSummary(
        id=task.id,
        type=task.type,
        status=task.status,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        transcript_name=transcript_name,
        template_name=template_name,
        source_filename=source_filename,
        output_name=task.output_name,
        error=task.error,
    )
