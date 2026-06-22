from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

TaskType = Literal["generate", "convert_template"]
TaskStatus = Literal["pending", "running", "completed", "failed"]


@dataclass
class GenerateTaskPayload:
    transcript_name: str
    template_name: str


@dataclass
class ConvertTemplateTaskPayload:
    source_filename: str
    staging_name: str


TaskPayload = GenerateTaskPayload | ConvertTemplateTaskPayload


@dataclass
class Task:
    id: str
    type: TaskType
    status: TaskStatus
    created_at: datetime
    payload: TaskPayload
    started_at: datetime | None = None
    finished_at: datetime | None = None
    output_name: str | None = None
    error: str | None = None

    @classmethod
    def create_generate(cls, payload: GenerateTaskPayload) -> Task:
        return cls(
            id=str(uuid4()),
            type="generate",
            status="pending",
            created_at=datetime.now(timezone.utc),
            payload=payload,
        )

    @classmethod
    def create_convert_template(cls, payload: ConvertTemplateTaskPayload) -> Task:
        return cls(
            id=str(uuid4()),
            type="convert_template",
            status="pending",
            created_at=datetime.now(timezone.utc),
            payload=payload,
        )
