from __future__ import annotations

from pathlib import Path

from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor

from backend.models.config import AppConfig
from backend.models.domain import GeneratedMinutes
from backend.services.exceptions import ExternalAPIError, ValidationError
from backend.services.files.service import FileService
from backend.services.llm.client import build_chat_client
from backend.services.llm.completion import chat_completion_text, create_chat_completion
from backend.services.generation.output_names import output_name_for_generation
from backend.services.generation.prompts import (
    MEETING_FACTS_SYSTEM,
    MEETING_FACTS_USER,
    MINUTES_RENDER_SYSTEM,
    MINUTES_RENDER_USER,
    CHUNK_FACTS_SYSTEM,
    CHUNK_FACTS_USER,
    MERGE_FACTS_SYSTEM,
    MERGE_FACTS_USER
)


class GenerationService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._transcripts = FileService(config.transcript_dir)
        self._templates = FileService(config.template_dir)
        self._output = FileService(config.output_dir)

    def generate(
        self,
        *,
        transcript_name: str,
        template_name: str,
        output_name: str | None = None,
        output_path: Path | None = None,
    ) -> GeneratedMinutes:
        transcript_path = self._transcripts.resolve_path(transcript_name)
        template_path = self._templates.resolve_path(template_name)
        transcript = transcript_path.read_text(encoding="utf-8").strip()
        template = template_path.read_text(encoding="utf-8").strip()

        if not transcript:
            raise ValidationError(f"Transcript is empty: {transcript_path.name}")
        if not template:
            raise ValidationError(f"Template is empty: {template_path.name}")

        if output_path is None:
            resolved_name = output_name or output_name_for_generation()
            output_path = self._resolve_output_path(resolved_name)

        try:
            content = self._generate_minutes(transcript=transcript, template=template)
        except Exception as exc:
            raise ExternalAPIError(f"Error calling LLM API: {exc}") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content + "\n", encoding="utf-8")
        return GeneratedMinutes(output_name=output_path.name, content=content)

    def _resolve_output_path(self, output_name: str) -> Path:
        safe_name = self._output._sanitize_filename(output_name)
        return self._config.output_dir / safe_name

    def _chunk_transcript(self, transcript: str, max_words: int = 2000) -> list[str]:
        words = transcript.split()
        chunks = []
        for i in range(0, len(words), max_words):
            chunks.append(" ".join(words[i:i + max_words]))
        return chunks

    def _generate_minutes(self, *, transcript: str, template: str) -> str:
        client = self._client()

        chunks = self._chunk_transcript(transcript, max_words=2000)

        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(
                    self._complete, 
                    client, 
                    system_prompt=CHUNK_FACTS_SYSTEM, 
                    user_prompt=CHUNK_FACTS_USER.format(transcript=chunk)
                )
                for chunk in chunks
            ]
            raw_chunks_outputs = [future.result() for future in futures]

        combined_raw_notes = "\n\n--- Chunk ---\n\n".join(raw_chunks_outputs)
        structured_facts = self._complete(
            client,
            system_prompt=MERGE_FACTS_SYSTEM,
            user_prompt=MERGE_FACTS_USER.format(raw_notes=combined_raw_notes)
        )

        return self._render_minutes(client, template=template, facts=structured_facts)

    def _extract_meeting_facts(self, client: OpenAI, transcript: str) -> str:
        content = self._complete(
            client,
            system_prompt=MEETING_FACTS_SYSTEM,
            user_prompt=MEETING_FACTS_USER.format(transcript=transcript),
        )
        return self._clean_output(content)

    def _render_minutes(self, client: OpenAI, *, template: str, facts: str) -> str:
        content = self._complete(
            client,
            system_prompt=MINUTES_RENDER_SYSTEM,
            user_prompt=MINUTES_RENDER_USER.format(template=template, facts=facts),
        )
        return self._clean_output(content)

    def _client(self):
        return build_chat_client(self._config)

    def _complete(
        self,
        client: OpenAI,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        response = create_chat_completion(
            client,
            model=self._config.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self._config.temperature,
        )

        return chat_completion_text(response)

    @staticmethod
    def _clean_output(content: str) -> str:
        """Remove prompt delimiter lines the model sometimes echoes."""
        drop_prefixes = (
            "=== meeting minute template ===",
            "=== meeting transcript ===",
            "=== end ===",
            "<template>",
            "</template>",
            "<transcript>",
            "</transcript>",
            "<notes>",
            "</notes>",
            "<document>",
            "</document>",
        )
        drop_suffixes = (
            "=== end ===",
        )
        lines = content.splitlines()
        while lines:
            stripped = lines[0].strip()
            if not stripped:
                lines.pop(0)
                continue
            if stripped.lower() in drop_prefixes:
                lines.pop(0)
                continue
            break
        while lines:
            stripped = lines[-1].strip()
            if not stripped:
                lines.pop()
                continue
            if stripped.lower() in drop_suffixes:
                lines.pop()
                continue
            break
        return "\n".join(lines).strip()
