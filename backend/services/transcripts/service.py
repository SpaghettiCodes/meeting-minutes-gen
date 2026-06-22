from __future__ import annotations

from backend.models.config import AppConfig, FileInfo
from backend.models.domain import SavedFile, TextDocument
from backend.services.exceptions import ValidationError
from backend.services.files.service import FileService
from backend.services.transcripts.transcription import TranscriptionService


class TranscriptService:
    def __init__(self, config: AppConfig) -> None:
        self._files = FileService(config.transcript_dir)
        self._transcription = TranscriptionService(config)

    def list_transcripts(self) -> list[FileInfo]:
        return self._files.list_files()

    def get_transcript(self, filename: str) -> TextDocument:
        return self._files.get_file(filename)

    def upload_transcript(self, filename: str, content: str) -> SavedFile:
        if not filename:
            raise ValidationError("Filename is required.")
        return self._files.save_file(filename, content)

    def transcribe_to_file(self, filename: str, raw: bytes, *, output_name: str) -> SavedFile:
        if not filename:
            raise ValidationError("Filename is required.")
        document = self._transcription.transcribe(filename, raw)
        return self._files.save_file(output_name, document.content)

    def delete_transcript(self, filename: str) -> SavedFile:
        return self._files.delete_file(filename)
