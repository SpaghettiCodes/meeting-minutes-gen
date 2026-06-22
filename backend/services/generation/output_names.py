from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def output_name_for_task(*, task_id: str, at: datetime | None = None) -> str:
    timestamp = at or datetime.now(timezone.utc)
    date_str = timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d")
    return f"{date_str}-{task_id}.md"


def output_name_for_generation(*, at: datetime | None = None) -> str:
    return output_name_for_task(task_id=str(uuid4()), at=at)


def template_output_name_for_task(*, task_id: str) -> str:
    return f"template-{task_id}.md"


def transcript_output_name_for_task(*, task_id: str) -> str:
    return f"transcript-{task_id}.txt"
