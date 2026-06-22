from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, Request

from backend.models.config import ENV_FILE, AppConfig, load_config
from backend.services.export import ExportService
from backend.services.generation import GenerationService
from backend.services.minutes import MinutesService
from backend.services.tasks import TaskService
from backend.services.templates import TemplateService
from backend.services.transcripts import TranscriptService


@lru_cache
def get_config() -> AppConfig:
    return load_config(ENV_FILE)


def get_transcript_service(
    config: AppConfig = Depends(get_config),
) -> TranscriptService:
    return TranscriptService(config)


def get_template_service(
    config: AppConfig = Depends(get_config),
) -> TemplateService:
    return TemplateService(config)


def get_minutes_service(
    config: AppConfig = Depends(get_config),
) -> MinutesService:
    return MinutesService(config)


def get_generation_service(
    config: AppConfig = Depends(get_config),
) -> GenerationService:
    return GenerationService(config)


def get_export_service() -> ExportService:
    return ExportService()


def get_task_service(request: Request) -> TaskService:
    return request.app.state.task_service
