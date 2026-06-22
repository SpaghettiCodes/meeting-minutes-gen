from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
ENV_FILE = PROJECT_ROOT / ".env.backend"

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


def load_config(env_file: Path | None = None) -> AppConfig:
    env_path = env_file or ENV_FILE
    if env_path.is_file():
        load_dotenv(env_path)
    else:
        project_env = PROJECT_ROOT / ".env"
        if project_env.is_file():
            load_dotenv(project_env)

    llm_base_url = (
        os.getenv("LLM_BASE_URL")
        or os.getenv("VLLM_BASE_URL")
        or DEFAULT_LLM_BASE_URL
    )
    llm_model = (
        os.getenv("LLM_MODEL")
        or os.getenv("VLLM_MODEL")
        or DEFAULT_LLM_MODEL
    )
    llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("VLLM_API_KEY") or None
    whisperx_base_url = os.getenv("WHISPERX_BASE_URL") or DEFAULT_WHISPERX_BASE_URL
    transcription_language = (
        os.getenv("TRANSCRIPTION_LANGUAGE") or DEFAULT_TRANSCRIPTION_LANGUAGE
    )

    def resolve_dir(key: str, default: str) -> Path:
        path = Path(os.getenv(key, default))
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    output_dir = resolve_dir("OUTPUT_DIR", "data/output")

    return AppConfig(
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        whisperx_base_url=whisperx_base_url,
        transcription_language=transcription_language,
        temperature=float(os.getenv("TEMPERATURE", "0.2")),
        request_timeout=float(os.getenv("LLM_REQUEST_TIMEOUT") or "600"),
        whisperx_request_timeout=float(os.getenv("WHISPERX_REQUEST_TIMEOUT") or "3600"),
        template_conversion_sources_dir=resolve_dir(
            "TEMPLATE_CONVERSION_SOURCES_DIR",
            "data/template_sources",
        ),
        transcription_sources_dir=resolve_dir(
            "TRANSCRIPTION_SOURCES_DIR",
            "data/transcription_sources",
        ),
        transcript_dir=resolve_dir("TRANSCRIPT_DIR", "data/transcripts"),
        template_dir=resolve_dir("TEMPLATE_DIR", "data/templates"),
        output_dir=output_dir,
        mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        mongodb_db=os.getenv("MONGODB_DB", "meeting_minutes"),
        mongodb_tasks_collection=os.getenv("MONGODB_TASKS_COLLECTION", "tasks"),
        max_concurrent_generations=int(os.getenv("MAX_CONCURRENT_GENERATIONS", "1")),
    )
