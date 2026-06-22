from __future__ import annotations

from backend.models.config import AppConfig, FileInfo
from backend.models.domain import SavedFile, TextDocument
from backend.services.files.service import FileService


class MinutesService:
    def __init__(self, config: AppConfig) -> None:
        self._files = FileService(config.output_dir)

    def list_minutes(self) -> list[FileInfo]:
        return self._files.list_files()

    def get_minutes(self, filename: str) -> TextDocument:
        return self._files.get_file(filename)

    def delete_minutes(self, filename: str) -> SavedFile:
        return self._files.delete_file(filename)
