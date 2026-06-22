from __future__ import annotations

from backend.models.config import AppConfig
from backend.schemas import HealthResponse


class HealthService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def get_health(self) -> HealthResponse:
        return HealthResponse(
            status="ok",
            llm_model=self._config.model,
            llm_provider="google-gemini",
            transcription_model=self._config.transcription_model,
            transcription_provider="google-gemini",
        )
