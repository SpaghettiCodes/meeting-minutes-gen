from __future__ import annotations

import tempfile
from pathlib import Path

import pypandoc

from backend.services.exceptions import ValidationError

_PDF_CSS_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "pdf.css"


class ExportService:
    @staticmethod
    def supported_formats() -> frozenset[str]:
        return frozenset({"docx", "pdf"})

    def export(self, *, content: str, filename: str, export_format: str) -> tuple[bytes, str]:
        if export_format not in self.supported_formats():
            formats = ", ".join(sorted(self.supported_formats()))
            raise ValidationError(f"Unsupported export format. Supported formats: {formats}")

        normalized = content.strip()
        if not normalized:
            raise ValidationError("Cannot export empty meeting minutes.")

        safe_stem = Path(filename).stem or "meeting_minutes"
        if export_format == "docx":
            return self._to_docx(normalized), f"{safe_stem}.docx"
        return self._to_pdf(normalized, title=safe_stem), f"{safe_stem}.pdf"

    def _to_docx(self, content: str) -> bytes:
        return self._run_pandoc(
            content, 
            output_format="docx"
        )

    def _to_pdf(self, content: str, *, title: str) -> bytes:
        if not _PDF_CSS_PATH.is_file():
            raise ValidationError("PDF stylesheet is missing on the server.")

        return self._run_pandoc(
            content,
            output_format="pdf",
            extra_args=[
                f"--metadata=title:{title}",
                "--pdf-engine=wkhtmltopdf",
                f"--css={_PDF_CSS_PATH}",
                "--pdf-engine-opt=--enable-local-file-access",
                "--pdf-engine-opt=--margin-top",
                "--pdf-engine-opt=20mm",
                "--pdf-engine-opt=--margin-bottom",
                "--pdf-engine-opt=20mm",
                "--pdf-engine-opt=--margin-left",
                "--pdf-engine-opt=15mm",
                "--pdf-engine-opt=--margin-right",
                "--pdf-engine-opt=15mm",
            ],
        )

    def _run_pandoc(
        self,
        content: str,
        *,
        output_format: str,
        extra_args: list[str] | None = None,
    ) -> bytes:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / f"output.{output_format}"
            try:
                pypandoc.convert_text(
                    content,
                    output_format,
                    format="markdown+hard_line_breaks+raw_html",
                    outputfile=str(output_path),
                    extra_args=extra_args or [],
                )
            except RuntimeError as exc:
                message = str(exc)
                if "pandoc" in message.lower() and "not found" in message.lower():
                    raise ValidationError(
                        "pandoc is not installed. Install pandoc to export meeting minutes."
                    ) from exc
                if "wkhtmltopdf" in message.lower() and "not found" in message.lower():
                    raise ValidationError(
                        "wkhtmltopdf is not installed. Install wkhtmltopdf to export PDFs."
                    ) from exc
                raise ValidationError(
                    f"Failed to create {output_format.upper()} export: {message}"
                ) from exc
            except OSError as exc:
                raise ValidationError(
                    f"Failed to create {output_format.upper()} export: {exc}"
                ) from exc

            if not output_path.is_file():
                raise ValidationError(
                    f"Failed to create {output_format.upper()} export: pandoc produced no output."
                )

            return output_path.read_bytes()
