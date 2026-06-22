from __future__ import annotations

import re
import tempfile
from pathlib import Path

import fitz
import pypandoc

from backend.models.config import AppConfig
from backend.models.domain import TextDocument
from backend.services.exceptions import ExternalAPIError, ValidationError
from backend.services.generation.service import GenerationService
from backend.services.gemini.client import build_chat_client
from backend.services.templates.cleanup import sanitize_template_draft, strip_document_header
from backend.services.templates.document_chunks import split_document_structured
from backend.services.templates.preprocess import preprocess_extracted_text
from backend.services.templates.prompts import (
    TEMPLATE_CONVERSION_CHUNK_USER,
    TEMPLATE_CONVERSION_SYSTEM,
    TEMPLATE_CONVERSION_USER,
    TEMPLATE_REPAIR_SYSTEM,
    TEMPLATE_REPAIR_USER,
)

TEMPLATE_SOURCE_EXTENSIONS = {".docx", ".pdf"}
_CHUNK_PROMPT_OVERHEAD_CHARS = 700


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
        template = self._repair_template(template)
        resolved_name = output_name or f"{Path(filename).stem}.md"
        return TextDocument(name=resolved_name, content=template)

    def _convert_with_llm(
        self,
        extracted: str,
        *,
        page_texts: list[str] | None,
    ) -> str:
        max_input_chars = self._config.template_conversion_max_input_chars

        if len(extracted) <= max_input_chars:
            try:
                return self._generate_llm_template(
                    self._prepare_llm_source(extracted),
                    user_prompt_template=TEMPLATE_CONVERSION_USER,
                )
            except Exception as exc:
                if not self._is_context_length_error(exc):
                    raise ExternalAPIError(f"Error calling Gemini API: {exc}") from exc

        return self._convert_in_chunks(extracted, page_texts=page_texts)

    def _convert_in_chunks(
        self,
        extracted: str,
        *,
        page_texts: list[str] | None,
    ) -> str:
        max_input_chars = self._config.template_conversion_max_input_chars
        per_chunk_max = max(
            1024,
            max_input_chars - _CHUNK_PROMPT_OVERHEAD_CHARS,
        )
        structured_chunks = split_document_structured(
            extracted,
            max_chunk_chars=per_chunk_max,
            page_texts=page_texts,
        )
        if not structured_chunks:
            raise ExternalAPIError("Could not split document for template conversion.")

        templates: list[str] = []
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
                document_content=document_content,
            )
            try:
                templates.append(
                    self._generate_llm_template(
                        document_content,
                        user_prompt=user_prompt,
                    )
                )
            except Exception as exc:
                raise ExternalAPIError(
                    f"Error calling Gemini API for chunk {index}/{total}: {exc}"
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

        response = client.chat.completions.create(
            model=self._config.model,
            messages=[
                {"role": "system", "content": TEMPLATE_CONVERSION_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=min(self._config.temperature, 0.1),
            max_tokens=self._config.max_tokens,
        )

        content = response.choices[0].message.content
        if not content:
            raise ExternalAPIError("Model returned an empty response.")
        return self._clean_output(content.strip())

    def _repair_template(self, draft: str) -> str:
        sanitized = sanitize_template_draft(draft)
        if not sanitized:
            return sanitized

        client = build_chat_client(self._config)
        user_prompt = TEMPLATE_REPAIR_USER.format(draft=sanitized)
        try:
            response = client.chat.completions.create(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": TEMPLATE_REPAIR_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=self._config.max_tokens,
            )
        except Exception as exc:
            raise ExternalAPIError(f"Error calling Gemini API during template repair: {exc}") from exc

        content = response.choices[0].message.content
        if not content:
            return self._clean_output(sanitized)
        return self._clean_output(content.strip())

    @staticmethod
    def _aggregate_chunk_templates(templates: list[str]) -> str:
        parts: list[str] = []
        for index, part in enumerate(templates):
            cleaned = part.strip()
            if not cleaned:
                continue
            if index > 0:
                cleaned = strip_document_header(cleaned)
            parts.append(cleaned)
        return "\n\n".join(parts)

    @staticmethod
    def _is_context_length_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(
            marker in message
            for marker in (
                "maximum context length",
                "context length",
                "too many tokens",
                "max_model_len",
                "token limit",
                "context window",
            )
        )

    @staticmethod
    def _clean_output(content: str) -> str:
        cleaned = GenerationService._clean_output(content)
        cleaned = sanitize_template_draft(cleaned)
        cleaned = _strip_trailing_commentary(cleaned)
        cleaned = re.sub(r"</?document>", "", cleaned, flags=re.IGNORECASE).strip()
        drop_prefixes = (
            "<document>",
            "</document>",
            "```markdown",
            "```md",
            "```",
        )
        drop_suffixes = ("```",)
        lines = cleaned.splitlines()
        while lines:
            stripped = lines[0].strip().lower()
            if not stripped:
                lines.pop(0)
                continue
            if stripped in drop_prefixes:
                lines.pop(0)
                continue
            break
        while lines:
            stripped = lines[-1].strip().lower()
            if not stripped:
                lines.pop()
                continue
            if stripped in drop_suffixes:
                lines.pop()
                continue
            break
        return "\n".join(lines).strip()


_TRAILING_COMMENTARY_MARKERS = (
    "### self-check",
    "## self-check",
    "### final self-check",
    "## final self-check",
    "this template should be ready",
)


def _strip_trailing_commentary(content: str) -> str:
    lines = content.splitlines()
    cut = len(lines)
    for index, line in enumerate(lines):
        lowered = line.strip().lower()
        if any(lowered.startswith(marker) for marker in _TRAILING_COMMENTARY_MARKERS):
            cut = index
            break
    trimmed = lines[:cut]
    while trimmed and trimmed[-1].strip() == "```":
        trimmed.pop()
    return "\n".join(trimmed).strip()
