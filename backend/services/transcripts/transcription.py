from __future__ import annotations

from pathlib import Path

import httpx

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

        try:
            result = self._call_whisperx(filename, raw)
            content = self._format_transcript(filename, result)
        except httpx.HTTPError as exc:
            raise ExternalAPIError(f"Error calling WhisperX service: {exc}") from exc
        except RuntimeError as exc:
            raise ExternalAPIError(str(exc)) from exc
        except Exception as exc:
            raise ExternalAPIError(f"Error during transcription: {exc}") from exc

        output_name = f"{Path(filename).stem}.txt"
        return TextDocument(name=output_name, content=content)

    def _call_whisperx(self, filename: str, raw: bytes) -> dict:
        if not self._config.hf_token:
            raise RuntimeError(
                "HF_TOKEN is not set. Add it to .env for WhisperX speaker diarization."
            )

        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.lower()
        mime_type = _MEDIA_MIME_TYPES.get(suffix, "application/octet-stream")
        url = f"{self._config.whisperx_base_url.rstrip('/')}/diarize"

        response = httpx.post(
            url,
            files={"file": (safe_name, raw, mime_type)},
            data={
                "hf_token": self._config.hf_token,
                "language": self._config.transcription_language,
            },
            timeout=self._config.whisperx_request_timeout,
        )

        if response.status_code >= 400:
            raise RuntimeError(
                f"WhisperX returned {response.status_code}: {response.text.strip()}"
            )

        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("WhisperX returned an unexpected response.")
        return payload

    def _format_transcript(self, filename: str, result: dict) -> str:
        segments = result.get("segments", [])
        if not segments:
            raise RuntimeError("WhisperX returned no segments.")

        speakers = sorted(
            {
                str(segment.get("speaker"))
                for segment in segments
                if segment.get("speaker")
            }
        )

        lines = [
            "============================================================",
            "TRANSCRIPTION REPORT WITH SPEAKER DIARIZATION",
            "============================================================",
            f"Source File: {Path(filename).name}",
            f"Detected Language: {result.get('language', self._config.transcription_language)}",
            f"Number of Speakers: {len(speakers)}",
        ]
        if speakers:
            lines.append(f"Speakers: {', '.join(speakers)}")
        lines.extend(
            [
                "Timing Format: Relative (MM:SS from start)",
                "============================================================",
                "",
                "TRANSCRIPTION BY SPEAKER:",
                "==============================",
                "",
            ]
        )

        current_speaker = None
        for segment in segments:
            speaker = str(segment.get("speaker") or "Unknown")
            text = str(segment.get("text", "")).strip()
            if not text:
                continue

            start = self._fmt_time(float(segment.get("start", 0)))
            end = self._fmt_time(float(segment.get("end", 0)))

            if speaker != current_speaker:
                lines.append("")
                lines.append(f"[{speaker}]")
                current_speaker = speaker

            lines.append(f"({start} - {end}) {text}")

        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        total = max(0, int(seconds))
        minutes, secs = divmod(total, 60)
        return f"{minutes:02d}:{secs:02d}"
