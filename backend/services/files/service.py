from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend.models.config import FileInfo
from backend.models.domain import SavedFile, TextDocument
from backend.services.exceptions import NotFoundError, ValidationError

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".text"}


class FileService:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    @property
    def directory(self) -> Path:
        return self._directory

    def list_files(self) -> list[FileInfo]:
        if not self._directory.is_dir():
            return []

        files: list[FileInfo] = []
        for path in sorted(self._directory.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_EXTENSIONS or path.name.startswith("."):
                continue
            stat = path.stat()
            files.append(
                FileInfo(
                    name=path.name,
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                )
            )
        return files

    def get_file(self, filename: str) -> TextDocument:
        path = self._resolve_path(filename)
        content = path.read_text(encoding="utf-8").strip()
        return TextDocument(name=path.name, content=content)

    def save_file(self, filename: str, content: str) -> SavedFile:
        if not content.strip():
            raise ValidationError("File content is empty.")

        safe_name = self._sanitize_filename(filename)
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / safe_name
        path.write_text(content.strip() + "\n", encoding="utf-8")
        return SavedFile(name=path.name)

    def delete_file(self, filename: str) -> SavedFile:
        path = self._resolve_path(filename)
        name = path.name
        path.unlink()
        return SavedFile(name=name)

    def resolve_path(self, filename: str) -> Path:
        return self._resolve_path(filename)

    def _resolve_path(self, filename: str) -> Path:
        safe_name = self._sanitize_filename(filename)
        path = self._directory / safe_name
        if not path.is_file():
            raise NotFoundError(f"File not found: {safe_name}")
        return path

    def _sanitize_filename(self, filename: str) -> str:
        name = Path(filename).name
        if not name or name.startswith("."):
            raise ValidationError("Invalid filename.")
        if Path(name).suffix.lower() not in TEXT_EXTENSIONS:
            extensions = ", ".join(sorted(TEXT_EXTENSIONS))
            raise ValidationError(
                f"Unsupported file type. Supported extensions: {extensions}"
            )
        return name
