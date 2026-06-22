from __future__ import annotations

import tempfile
from pathlib import Path

from openai import OpenAI

from backend.models.config import AppConfig
from backend.models.domain import TextDocument
from backend.services.exceptions import ExternalAPIError, ValidationError

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".mpeg", ".mpg"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".opus"}
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

_MEDIA_MIME_TYPES = {
    ".mp4": "video/mp4",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mpeg": "video/mpeg",
    ".mpg": "video/mpeg",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".aac": "audio/aac",
    ".opus": "audio/opus",
}


class TranscriptionService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    @staticmethod
    def is_media_filename(filename: str) -> bool:
        return Path(filename).suffix.lower() in MEDIA_EXTENSIONS

    @staticmethod
    def supported_media_extensions() -> set[str]:
        return MEDIA_EXTENSIONS

    def transcribe(self, filename: str, raw: bytes) -> TextDocument:
        if not filename:
            raise ValidationError("Filename is required.")
        if not self.is_media_filename(filename):
            extensions = ", ".join(sorted(MEDIA_EXTENSIONS))
            raise ValidationError(
                f"Unsupported media type. Supported extensions: {extensions}"
            )
        if not raw:
            raise ValidationError("Uploaded file is empty.")

        safe_name = Path(filename).name
        with tempfile.TemporaryDirectory() as tmp_dir:
            media_path = Path(tmp_dir) / safe_name
            media_path.write_bytes(raw)
            try:
                content = self._call_whisper(media_path)
            except RuntimeError as exc:
                raise ExternalAPIError(str(exc)) from exc
            except Exception as exc:
                raise ExternalAPIError(
                    f"Error calling Whisper transcription API: {exc}"
                ) from exc

        output_name = f"{Path(filename).stem}.txt"
        return TextDocument(name=output_name, content=content)

    def _call_whisper(self, media_path: Path) -> str:
        if not media_path.is_file() or media_path.stat().st_size == 0:
            raise RuntimeError("Media file is empty.")

        suffix = media_path.suffix.lower()
        mime_type = _MEDIA_MIME_TYPES.get(suffix, "application/octet-stream")

        client = OpenAI(
            api_key=self._config.whisper_api_key or "not-needed",
            base_url=self._config.whisper_base_url.rstrip("/"),
            timeout=self._config.request_timeout,
        )
        with media_path.open("rb") as media_file:
            response = client.audio.transcriptions.create(
                model=self._config.transcription_model,
                file=(media_path.name, media_file, mime_type),
            )

        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Whisper returned an empty transcript.")
        return text
