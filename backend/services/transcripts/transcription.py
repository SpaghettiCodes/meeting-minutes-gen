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

        suffix = Path(filename).suffix.lower()
        with tempfile.TemporaryDirectory() as tmp_dir:
            media_path = Path(tmp_dir) / f"upload{suffix}"
            media_path.write_bytes(raw)
            try:
                content = self._transcribe_media_file(media_path)
            except RuntimeError as exc:
                raise ExternalAPIError(str(exc)) from exc
            except Exception as exc:
                raise ExternalAPIError(
                    f"Error calling Whisper transcription API: {exc}"
                ) from exc

        output_name = f"{Path(filename).stem}.txt"
        return TextDocument(name=output_name, content=content)

    def _transcribe_media_file(self, media_path: Path) -> str:
        if media_path.suffix.lower() in VIDEO_EXTENSIONS:
            with tempfile.TemporaryDirectory() as tmp_dir:
                audio_path = Path(tmp_dir) / "audio.wav"
                self._extract_audio(media_path, audio_path)
                return self._call_whisper(audio_path)

        return self._call_whisper(media_path)

    def _extract_audio(self, video_path: Path, audio_path: Path) -> None:
        try:
            (
                ffmpeg.input(str(video_path))
                .output(
                    str(audio_path),
                    format="wav",
                    acodec="pcm_s16le",
                    ar=16000,
                    ac=1,
                )
                .overwrite_output()
                .run(capture_stderr=True)
            )
        except ffmpeg.Error as exc:
            detail = (exc.stderr or b"").decode(errors="replace").strip()
            detail = detail or "Unknown ffmpeg error"
            raise RuntimeError(f"Failed to extract audio from video: {detail}") from exc

    def _call_whisper(self, audio_path: Path) -> str:
        if not audio_path.is_file() or audio_path.stat().st_size == 0:
            raise RuntimeError("Audio file is empty.")

        client = OpenAI(
            api_key=self._config.whisper_api_key or "not-needed",
            base_url=self._config.whisper_base_url.rstrip("/"),
            timeout=self._config.request_timeout,
        )
        with audio_path.open("rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=self._config.transcription_model,
                file=audio_file,
            )

        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Whisper returned an empty transcript.")
        return text
