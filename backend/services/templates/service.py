from __future__ import annotations

from backend.models.config import AppConfig, FileInfo
from backend.models.domain import SavedFile, TextDocument
from backend.services.exceptions import ValidationError
from backend.services.files.service import FileService
from backend.services.templates.conversion import TemplateConversionService


class TemplateService:
    def __init__(self, config: AppConfig) -> None:
        self._files = FileService(config.template_dir)
        self._conversion = TemplateConversionService(config)

    def list_templates(self) -> list[FileInfo]:
        return self._files.list_files()

    def get_template(self, filename: str) -> TextDocument:
        return self._files.get_file(filename)

    def upload_template(self, filename: str, content: str) -> SavedFile:
        if not filename:
            raise ValidationError("Filename is required.")
        return self._files.save_file(filename, content)

    def convert_from_document(
        self,
        filename: str,
        raw: bytes,
        output_name: str | None = None,
    ) -> TextDocument:
        document = self._conversion.convert(filename, raw, output_name=output_name)
        saved = self._files.save_file(document.name, document.content)
        return TextDocument(name=saved.name, content=document.content)

    def delete_template(self, filename: str) -> SavedFile:
        return self._files.delete_file(filename)
