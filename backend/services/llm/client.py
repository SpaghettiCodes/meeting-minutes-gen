from __future__ import annotations

from openai import OpenAI

from backend.models.config import AppConfig


def build_chat_client(config: AppConfig) -> OpenAI:
    return OpenAI(
        api_key=config.llm_api_key or "not-needed",
        base_url=config.llm_base_url.rstrip("/"),
        timeout=config.request_timeout,
    )
