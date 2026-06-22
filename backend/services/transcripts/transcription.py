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

_WHISPER_UPLOAD_NAME = "audio.wav"


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
                whisper_path = self._prepare_whisper_wav(media_path, tmp_path)
                content = self._call_whisper(whisper_path)
            except RuntimeError as exc:
                raise ExternalAPIError(str(exc)) from exc
            except Exception as exc:
                raise ExternalAPIError(
                    f"Error calling Whisper transcription API: {exc}"
                ) from exc

        output_name = f"{Path(filename).stem}.txt"
        return TextDocument(name=output_name, content=content)

    def _prepare_whisper_wav(self, media_path: Path, tmp_dir: Path) -> Path:
        output_path = tmp_dir / _WHISPER_UPLOAD_NAME

        # Probe input first
        probe = ffmpeg.probe(str(media_path))
        audio_streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
        if not audio_streams:
            raise RuntimeError(f"No audio stream found in '{media_path.name}'.")

        self._transcode_to_wav(media_path, output_path)

        # Verify output duration
        out_probe = ffmpeg.probe(str(output_path))
        duration = float(out_probe["format"].get("duration", 0))
        if duration < 0.1:
            raise RuntimeError(f"Transcoded WAV is too short ({duration:.2f}s).")

        return output_path

    @staticmethod
    def _transcode_to_wav(input_path: Path, output_path: Path) -> None:
        try:
            (
                ffmpeg.input(str(input_path))
                .output(
                    str(output_path),
                    format="wav",
                    acodec="pcm_s16le",
                    ar=16000,
                    ac=1,
                    vn=None,
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


    def _call_whisper(self, wav_path: Path) -> str:
        if not wav_path.is_file() or wav_path.stat().st_size == 0:
            raise RuntimeError("Media file is empty.")

        client = OpenAI(
            api_key=self._config.whisper_api_key or "not-needed",
            base_url=self._config.whisper_base_url,
        )

        with wav_path.open("rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model=self._config.transcription_model,
                file=(wav_path.name, audio_file, "audio/wav"),
            )

        text = transcript.text.strip()
        if not text:
            raise RuntimeError("Whisper returned an empty transcript.")
        return text