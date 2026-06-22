from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
ENV_FILE = PROJECT_ROOT / ".env.backend"

DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_GEMINI_TRANSCRIPTION_MODEL = "gemini-2.0-flash"
DEFAULT_LLM_MAX_MODEL_LEN = 1_048_576


@dataclass(frozen=True)
class AppConfig:
    base_url: str
    model: str
    transcription_model: str
    api_key: str | None
    temperature: float
    max_tokens: int
    llm_max_model_len: int
    request_timeout: float
    template_conversion_max_input_chars: int
    template_conversion_sources_dir: Path
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

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("VLLM_API_KEY")
    model = (
        os.getenv("GEMINI_MODEL")
        or os.getenv("LLM_MODEL")
        or os.getenv("VLLM_MODEL")
        or DEFAULT_GEMINI_MODEL
    )
    transcription_model = (
        os.getenv("GEMINI_TRANSCRIPTION_MODEL")
        or os.getenv("WHISPER_MODEL")
        or model
    )
    base_url = (
        os.getenv("GEMINI_BASE_URL")
        or os.getenv("VLLM_BASE_URL")
        or DEFAULT_GEMINI_BASE_URL
    )

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY must be set in .env "
            "(get one at https://aistudio.google.com/apikey)"
        )

    def resolve_dir(key: str, default: str) -> Path:
        path = Path(os.getenv(key, default))
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    output_dir = resolve_dir("OUTPUT_DIR", "data/output")
    max_tokens = int(os.getenv("MAX_TOKENS", "8192"))

    return AppConfig(
        base_url=base_url,
        model=model,
        transcription_model=transcription_model,
        api_key=api_key,
        temperature=float(os.getenv("TEMPERATURE", "0.2")),
        max_tokens=max_tokens,
        llm_max_model_len=int(os.getenv("LLM_MAX_MODEL_LEN", str(DEFAULT_LLM_MAX_MODEL_LEN))),
        request_timeout=float(
            os.getenv("GEMINI_REQUEST_TIMEOUT")
            or os.getenv("VLLM_REQUEST_TIMEOUT")
            or "600"
        ),
        template_conversion_max_input_chars=_template_conversion_max_input_chars(max_tokens),
        template_conversion_sources_dir=resolve_dir(
            "TEMPLATE_CONVERSION_SOURCES_DIR",
            "data/template_sources",
        ),
        transcript_dir=resolve_dir("TRANSCRIPT_DIR", "data/transcripts"),
        template_dir=resolve_dir("TEMPLATE_DIR", "data/templates"),
        output_dir=output_dir,
        mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        mongodb_db=os.getenv("MONGODB_DB", "meeting_minutes"),
        mongodb_tasks_collection=os.getenv("MONGODB_TASKS_COLLECTION", "tasks"),
        max_concurrent_generations=int(os.getenv("MAX_CONCURRENT_GENERATIONS", "1")),
    )


def _template_conversion_max_input_chars(max_tokens: int) -> int:
    explicit = os.getenv("TEMPLATE_CONVERSION_MAX_INPUT_CHARS")
    if explicit:
        return max(1024, int(explicit))

    max_model_len = int(os.getenv("LLM_MAX_MODEL_LEN", str(DEFAULT_LLM_MAX_MODEL_LEN)))
    prompt_overhead_tokens = 2400
    input_tokens = max(1024, max_model_len - max_tokens - prompt_overhead_tokens)
    return int(input_tokens * 3.0)
