from __future__ import annotations

from openai import OpenAI

from backend.models.config import AppConfig
from backend.services.exceptions import ExternalAPIError


def build_chat_client(config: AppConfig) -> OpenAI:
    if not config.api_key:
        raise ExternalAPIError(
            "GEMINI_API_KEY is not set. Add it to .env (get one at https://aistudio.google.com/apikey)."
        )
    return OpenAI(
        api_key=config.api_key,
        base_url=config.base_url.rstrip("/"),
        timeout=config.request_timeout,
    )
