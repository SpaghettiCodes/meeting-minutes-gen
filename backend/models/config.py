from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_LLM_BASE_URL = "http://localhost:8002/v1"
DEFAULT_LLM_MODEL = "default"
DEFAULT_WHISPERX_BASE_URL = "http://localhost:8000"
DEFAULT_TRANSCRIPTION_LANGUAGE = "en"


@dataclass(frozen=True)
class AppConfig:
    llm_base_url: str
    llm_model: str
    llm_api_key: str | None
    whisperx_base_url: str
    transcription_language: str
    temperature: float
    request_timeout: float
    whisperx_request_timeout: float
    template_conversion_sources_dir: Path
    transcription_sources_dir: Path
    transcript_dir: Path
    template_dir: Path
    output_dir: Path
    mongodb_uri: str
    mongodb_db: str
    mongodb_tasks_collection: str
    max_concurrent_generations: int


@dataclass(frozen=True)
class FileInfo:
    name: str
    size_bytes: int
    modified_at: datetime


def load_config() -> AppConfig:
    llm_base_url = (
        os.getenv("LLM_BASE_URL")
        or DEFAULT_LLM_BASE_URL
    )
    llm_model = (
        os.getenv("LLM_MODEL")
        or DEFAULT_LLM_MODEL
    )
    llm_api_key = os.getenv("LLM_API_KEY") or None
    whisperx_base_url = os.getenv("WHISPERX_BASE_URL") or DEFAULT_WHISPERX_BASE_URL
    transcription_language = (
        os.getenv("TRANSCRIPTION_LANGUAGE") or DEFAULT_TRANSCRIPTION_LANGUAGE
    )

    DATA_DIR = Path(os.getenv("DATA_DIR") or 'data')
    return AppConfig(
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        whisperx_base_url=whisperx_base_url,
        transcription_language=transcription_language,
        temperature=float(os.getenv("TEMPERATURE", "0.2")),
        request_timeout=float(os.getenv("LLM_REQUEST_TIMEOUT") or "600"),
        whisperx_request_timeout=float(os.getenv("WHISPERX_REQUEST_TIMEOUT") or "3600"),
        template_conversion_sources_dir=DATA_DIR / "template_sources",
        transcription_sources_dir=DATA_DIR / "transcription_sources",
        transcript_dir=DATA_DIR / "transcripts",
        template_dir=DATA_DIR / "templates",
        output_dir=DATA_DIR / "output",
        mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        mongodb_db=os.getenv("MONGODB_DB", "meeting_minutes"),
        mongodb_tasks_collection=os.getenv("MONGODB_TASKS_COLLECTION", "tasks"),
        max_concurrent_generations=int(os.getenv("MAX_CONCURRENT_GENERATIONS", "1")),
    )
