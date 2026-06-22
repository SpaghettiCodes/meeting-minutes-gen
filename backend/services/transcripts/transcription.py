from __future__ import annotations

import tempfile
from pathlib import Path

import ffmpeg
from google import genai
from google.genai import types

from backend.models.config import AppConfig
from backend.models.domain import TextDocument
from backend.services.exceptions import ExternalAPIError, ValidationError

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".mpeg", ".mpg"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".opus"}
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

_AUDIO_MIME_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".aac": "audio/aac",
    ".opus": "audio/opus",
}

_TRANSCRIPTION_PROMPT = """\
Transcribe this audio verbatim.

Rules:
- Output plain text only.
- If multiple speakers are clearly distinct, label them Speaker 1, Speaker 2, etc.
- Do not summarize or omit spoken content.
- Do not add commentary before or after the transcript.
"""


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
                raise ExternalAPIError(f"Error calling Gemini transcription API: {exc}") from exc

        output_name = f"{Path(filename).stem}.txt"
        return TextDocument(name=output_name, content=content)

    def _transcribe_media_file(self, media_path: Path) -> str:
        if media_path.suffix.lower() in VIDEO_EXTENSIONS:
            with tempfile.TemporaryDirectory() as tmp_dir:
                audio_path = Path(tmp_dir) / "audio.wav"
                self._extract_audio(media_path, audio_path)
                return self._call_gemini(audio_path)

        return self._call_gemini(media_path)

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

    def _call_gemini(self, audio_path: Path) -> str:
        if not self._config.api_key:
            raise ExternalAPIError("GEMINI_API_KEY is not set.")

        mime_type = _AUDIO_MIME_TYPES.get(audio_path.suffix.lower(), "audio/wav")
        audio_bytes = audio_path.read_bytes()
        if not audio_bytes:
            raise RuntimeError("Audio file is empty.")

        client = genai.Client(api_key=self._config.api_key)
        response = client.models.generate_content(
            model=self._config.transcription_model,
            contents=types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=_TRANSCRIPTION_PROMPT),
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                ],
            ),
        )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty transcript.")
        return text
