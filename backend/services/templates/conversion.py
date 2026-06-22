from __future__ import annotations

import tempfile
from pathlib import Path

import fitz
import pypandoc

from backend.models.config import AppConfig
from backend.models.domain import TextDocument
from backend.services.exceptions import ExternalAPIError, ValidationError
from backend.services.llm.client import build_chat_client
from backend.services.llm.completion import (
    chat_completion_text,
    create_chat_completion,
    is_retriable_length_error,
)
from backend.services.templates.cleanup import ensure_batch_end_marker, strip_batch_markers
from backend.services.templates.document_chunks import split_document_structured
from backend.services.templates.preprocess import preprocess_extracted_text
from backend.services.templates.prompts import (
    TEMPLATE_CONVERSION_CHUNK_USER,
    TEMPLATE_CONVERSION_SYSTEM,
    TEMPLATE_CONVERSION_USER,
)

TEMPLATE_SOURCE_EXTENSIONS = {".docx", ".pdf"}
_CHUNK_PROMPT_OVERHEAD_CHARS = 1200
_FALLBACK_CHUNK_CHARS = 12_000
_PRIOR_TEMPLATE_MAX_CHARS = 48_000


class TemplateConversionService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    @staticmethod
    def is_convertible_filename(filename: str) -> bool:
        return Path(filename).suffix.lower() in TEMPLATE_SOURCE_EXTENSIONS

    @staticmethod
    def supported_extensions() -> set[str]:
        return TEMPLATE_SOURCE_EXTENSIONS

    def convert(self, filename: str, raw: bytes, *, output_name: str | None = None) -> TextDocument:
        if not filename:
            raise ValidationError("Filename is required.")
        if not raw:
            raise ValidationError("Uploaded file is empty.")

        suffix = Path(filename).suffix.lower()
        if suffix not in TEMPLATE_SOURCE_EXTENSIONS:
            extensions = ", ".join(sorted(TEMPLATE_SOURCE_EXTENSIONS))
            raise ValidationError(
                f"Unsupported template source type. Supported extensions: {extensions}"
            )

        try:
            extracted, page_texts = self._extract_text(raw, suffix)
        except ValidationError:
            raise
        except Exception as exc:
            raise ExternalAPIError(f"Failed to read document: {exc}") from exc

        if not extracted:
            raise ValidationError(
                "Could not extract any text from the document. "
                "The file may be scanned/image-only or empty."
            )

        extracted = preprocess_extracted_text(extracted)
        if page_texts is not None:
            page_texts = [preprocess_extracted_text(page) for page in page_texts]

        template = self._convert_with_llm(extracted, page_texts=page_texts)
        resolved_name = output_name or f"{Path(filename).stem}.md"
        return TextDocument(name=resolved_name, content=template)

    def _convert_with_llm(
        self,
        extracted: str,
        *,
        page_texts: list[str] | None,
    ) -> str:
        prepared = self._prepare_llm_source(extracted)
        try:
            return self._generate_llm_template(
                prepared,
                user_prompt_template=TEMPLATE_CONVERSION_USER,
            )
        except Exception as exc:
            if not is_retriable_length_error(exc):
                raise ExternalAPIError(f"Error calling LLM API: {exc}") from exc

        return self._convert_in_chunks(extracted, page_texts=page_texts)

    def _convert_in_chunks(
        self,
        extracted: str,
        *,
        page_texts: list[str] | None,
    ) -> str:
        per_chunk_max = max(
            1024,
            _FALLBACK_CHUNK_CHARS - _CHUNK_PROMPT_OVERHEAD_CHARS,
        )
        structured_chunks = split_document_structured(
            extracted,
            max_chunk_chars=per_chunk_max,
            page_texts=page_texts,
        )
        if not structured_chunks:
            raise ExternalAPIError("Could not split document for template conversion.")

        templates: list[str] = []
        prior_batches: list[str] = []
        total = len(structured_chunks)
        for index, chunk in enumerate(structured_chunks, start=1):
            document_content = self._prepare_llm_source(chunk.content)
            section_titles = ", ".join(chunk.section_titles)
            if chunk.includes_document_header:
                header_instruction = (
                    "Include the document header (Date/Time, Location, Chairperson, etc.) "
                    "in this chunk."
                )
            else:
                header_instruction = (
                    "Do NOT output the document header (Date/Time, Location, Chairperson, etc.)."
                )
            user_prompt = TEMPLATE_CONVERSION_CHUNK_USER.format(
                part_index=index,
                part_count=total,
                section_titles=section_titles,
                header_instruction=header_instruction,
                prior_template=self._format_prior_template(prior_batches),
                document_content=document_content,
            )
            try:
                batch = self._generate_llm_template(
                    document_content,
                    user_prompt=user_prompt,
                )
                batch = ensure_batch_end_marker(batch)
                prior_batches.append(strip_batch_markers(batch))
                templates.append(batch)
            except Exception as exc:
                raise ExternalAPIError(
                    f"Error calling LLM API for chunk {index}/{total}: {exc}"
                ) from exc

        return self._aggregate_chunk_templates(templates)

    def _extract_text(self, raw: bytes, suffix: str) -> tuple[str, list[str] | None]:
        if suffix == ".docx":
            return self._extract_docx(raw), None
        page_texts = self._extract_pdf_pages(raw)
        return "\n\n".join(page_texts), page_texts

    @staticmethod
    def _extract_docx(raw: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".docx") as tmp:
            tmp.write(raw)
            tmp.flush()
            return pypandoc.convert_file(
                tmp.name,
                "markdown",
                format="docx",
                extra_args=[
                    "--wrap=none",
                    "--markdown-headings=atx",
                ],
            )

    @staticmethod
    def _extract_pdf_pages(raw: bytes) -> list[str]:
        with fitz.open(stream=raw, filetype="pdf") as document:
            pages = [page.get_text("text").strip() for page in document]
        return [page for page in pages if page]

    @staticmethod
    def _prepare_llm_source(extracted: str) -> str:
        return f"<document>\n{extracted}\n</document>"

    def _generate_llm_template(
        self,
        document_content: str,
        *,
        user_prompt: str | None = None,
        user_prompt_template: str = TEMPLATE_CONVERSION_USER,
    ) -> str:
        client = build_chat_client(self._config)

        if user_prompt is None:
            user_prompt = user_prompt_template.format(
                document_content=document_content,
            )

        response = create_chat_completion(
            client,
            model=self._config.llm_model,
            messages=[
                {"role": "system", "content": TEMPLATE_CONVERSION_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=min(self._config.temperature, 0.1),
        )

        return self._clean_output(chat_completion_text(response))

    @staticmethod
    def _format_prior_template(prior_batches: list[str]) -> str:
        if not prior_batches:
            return "None — this is the first chunk."

        combined = "\n\n".join(
            f"--- Batch {index} ---\n{strip_batch_markers(batch)}"
            for index, batch in enumerate(prior_batches, start=1)
        )
        if len(combined) <= _PRIOR_TEMPLATE_MAX_CHARS:
            return combined

        trimmed_batches: list[str] = []
        remaining = _PRIOR_TEMPLATE_MAX_CHARS
        for batch in reversed(prior_batches):
            section = f"--- Batch ---\n{strip_batch_markers(batch)}"
            if len(section) > remaining:
                if remaining > 512:
                    trimmed_batches.insert(0, section[-remaining:])
                break
            trimmed_batches.insert(0, section)
            remaining -= len(section) + 2

        note = (
            "[Earlier batches truncated for length. "
            "Do not repeat any section heading shown below.]\n\n"
        )
        return note + "\n\n".join(trimmed_batches)

    @staticmethod
    def _aggregate_chunk_templates(templates: list[str]) -> str:
        parts = [
            strip_batch_markers(part.strip())
            for part in templates
            if strip_batch_markers(part.strip())
        ]
        return "\n\n".join(parts)

    @staticmethod
    def _clean_output(content: str) -> str:
        return content.strip()
