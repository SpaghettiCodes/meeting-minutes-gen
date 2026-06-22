from __future__ import annotations

import tempfile
from pathlib import Path

import ffmpeg
from openai import OpenAI

from backend.models.config import AppConfig
from backend.models.domain import TextDocument
from backend.services.exceptions import ExternalAPIError, ValidationError

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".mpeg", ".mpg"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".opus"}
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

# vLLM reads uploads from memory (BytesIO). MP4/M4A/WebM fail there — use ffmpeg first.
_VLLM_DIRECT_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".mpeg", ".mpg"}

_MEDIA_MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".mpeg": "audio/mpeg",
    ".mpg": "audio/mpeg",
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
            tmp_path = Path(tmp_dir)
            media_path = tmp_path / safe_name
            media_path.write_bytes(raw)
            try:
                whisper_path, upload_name, mime_type = self._prepare_whisper_file(
                    media_path,
                    tmp_path,
                )
                content = self._call_whisper(whisper_path, upload_name, mime_type)
            except RuntimeError as exc:
                raise ExternalAPIError(str(exc)) from exc
            except Exception as exc:
                raise ExternalAPIError(
                    f"Error calling Whisper transcription API: {exc}"
                ) from exc

        output_name = f"{Path(filename).stem}.txt"
        return TextDocument(name=output_name, content=content)

    def _prepare_whisper_file(
        self,
        media_path: Path,
        tmp_dir: Path,
    ) -> tuple[Path, str, str]:
        suffix = media_path.suffix.lower()
        if suffix in _VLLM_DIRECT_EXTENSIONS:
            mime_type = _MEDIA_MIME_TYPES.get(suffix, "application/octet-stream")
            return media_path, media_path.name, mime_type

        output_path = tmp_dir / "whisper-input.mp3"
        self._transcode_to_mp3(media_path, output_path)
        return output_path, "audio.mp3", "audio/mpeg"

    @staticmethod
    def _transcode_to_mp3(input_path: Path, output_path: Path) -> None:
        try:
            (
                ffmpeg.input(str(input_path))
                .output(
                    str(output_path),
                    vn=None,
                    acodec="libmp3lame",
                    ar=16000,
                    ac=1,
                    audio_bitrate="64k",
                )
                .overwrite_output()
                .run(capture_stderr=True)
            )
        except ffmpeg.Error as exc:
            detail = (exc.stderr or b"").decode(errors="replace").strip()
            detail = detail or "Unknown ffmpeg error"
            raise RuntimeError(f"Failed to prepare audio for Whisper: {detail}") from exc

        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("ffmpeg produced an empty audio file.")

    def _call_whisper(
        self,
        media_path: Path,
        upload_name: str,
        mime_type: str,
    ) -> str:
        if not media_path.is_file() or media_path.stat().st_size == 0:
            raise RuntimeError("Media file is empty.")

        client = OpenAI(
            api_key=self._config.whisper_api_key or "not-needed",
            base_url=self._config.whisper_base_url.rstrip("/"),
            timeout=self._config.request_timeout,
        )
        with media_path.open("rb") as media_file:
            response = client.audio.transcriptions.create(
                model=self._config.transcription_model,
                file=(upload_name, media_file, mime_type),
            )

        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Whisper returned an empty transcript.")
        return text
