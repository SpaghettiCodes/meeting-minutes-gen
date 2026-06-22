from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from openai import OpenAI

from backend.models.config import AppConfig
from backend.models.domain import GeneratedMinutes
from backend.services.exceptions import ExternalAPIError, ValidationError
from backend.services.files.service import FileService
from backend.services.gemini.client import build_chat_client
from backend.services.generation.output_names import output_name_for_generation
from backend.services.generation.prompts import (
    MEETING_FACTS_SYSTEM,
    MEETING_FACTS_USER,
    MINUTES_RENDER_SYSTEM,
    MINUTES_RENDER_USER,
)

# Conservative estimate — better to truncate early than hit context limits.
_CHARS_PER_TOKEN = 3.0
_COMPLETION_MARGIN_TOKENS = 384
_TRUNCATION_NOTE = (
    "\n\nNote: content was truncated to fit the model context window. "
    "Use all information available in the excerpt."
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
            raise ExternalAPIError(f"Error calling Gemini API: {exc}") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content + "\n", encoding="utf-8")
        return GeneratedMinutes(output_name=output_path.name, content=content)

    def _resolve_output_path(self, output_name: str) -> Path:
        safe_name = self._output._sanitize_filename(output_name)
        return self._config.output_dir / safe_name

    def _generate_minutes(self, *, transcript: str, template: str) -> str:
        client = self._client()
        facts = self._extract_meeting_facts(client, transcript)
        return self._render_minutes(client, template=template, facts=facts)

    def _max_prompt_tokens(self) -> int:
        return max(
            512,
            self._config.llm_max_model_len
            - self._config.max_tokens
            - _COMPLETION_MARGIN_TOKENS,
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, int(len(text) / _CHARS_PER_TOKEN))

    @staticmethod
    def _truncate_text_to_tokens(text: str, max_tokens: int) -> tuple[str, bool]:
        max_chars = max(0, int(max_tokens * _CHARS_PER_TOKEN))
        if len(text) <= max_chars:
            return text, False
        return text[:max_chars], True

    def _fit_variable_content(
        self,
        *,
        system_prompt: str,
        build_user_prompt: Callable[[str], str],
        content: str,
    ) -> tuple[str, bool]:
        max_prompt_tokens = self._max_prompt_tokens()
        system_tokens = self._estimate_tokens(system_prompt)
        wrapper_tokens = self._estimate_tokens(build_user_prompt(""))
        variable_budget = max(
            128,
            max_prompt_tokens - system_tokens - wrapper_tokens,
        )

        working, truncated = self._truncate_text_to_tokens(content, variable_budget)
        user_prompt = build_user_prompt(working)
        total_tokens = system_tokens + self._estimate_tokens(user_prompt)

        while total_tokens > max_prompt_tokens and len(working) > 256:
            variable_budget = max(128, int(variable_budget * 0.85))
            working, was_truncated = self._truncate_text_to_tokens(
                content,
                variable_budget,
            )
            truncated = truncated or was_truncated
            user_prompt = build_user_prompt(working)
            total_tokens = system_tokens + self._estimate_tokens(user_prompt)

        return user_prompt, truncated

    def _fit_two_part_content(
        self,
        *,
        system_prompt: str,
        build_user_prompt: Callable[[str, str], str],
        primary: str,
        secondary: str,
    ) -> tuple[str, bool]:
        max_prompt_tokens = self._max_prompt_tokens()
        system_tokens = self._estimate_tokens(system_prompt)
        wrapper_tokens = self._estimate_tokens(build_user_prompt("", ""))
        remaining = max(256, max_prompt_tokens - system_tokens - wrapper_tokens)

        primary_tokens = self._estimate_tokens(primary)
        secondary_tokens = self._estimate_tokens(secondary)
        truncated = False

        if primary_tokens + secondary_tokens <= remaining:
            fitted_primary, fitted_secondary = primary, secondary
        elif primary_tokens >= remaining:
            fitted_primary, truncated = self._truncate_text_to_tokens(
                primary,
                remaining,
            )
            fitted_secondary = ""
        else:
            fitted_primary = primary
            secondary_budget = remaining - primary_tokens
            fitted_secondary, truncated = self._truncate_text_to_tokens(
                secondary,
                secondary_budget,
            )

        user_prompt = build_user_prompt(fitted_primary, fitted_secondary)
        total_tokens = system_tokens + self._estimate_tokens(user_prompt)
        while total_tokens > max_prompt_tokens and len(fitted_secondary) > 128:
            secondary_budget = max(
                64,
                self._estimate_tokens(fitted_secondary) - 256,
            )
            fitted_secondary, was_truncated = self._truncate_text_to_tokens(
                secondary,
                secondary_budget,
            )
            truncated = truncated or was_truncated
            user_prompt = build_user_prompt(fitted_primary, fitted_secondary)
            total_tokens = system_tokens + self._estimate_tokens(user_prompt)

        return user_prompt, truncated

    def _extract_meeting_facts(self, client: OpenAI, transcript: str) -> str:
        user_prompt, truncated = self._fit_variable_content(
            system_prompt=MEETING_FACTS_SYSTEM,
            build_user_prompt=lambda text: MEETING_FACTS_USER.format(transcript=text),
            content=transcript,
        )
        if truncated:
            user_prompt = user_prompt.replace(
                "</transcript>",
                f"{_TRUNCATION_NOTE}\n</transcript>",
            )

        content = self._complete(
            client,
            system_prompt=MEETING_FACTS_SYSTEM,
            user_prompt=user_prompt,
        )
        return self._clean_output(content)

    def _render_minutes(self, client: OpenAI, *, template: str, facts: str) -> str:
        user_prompt, truncated = self._fit_two_part_content(
            system_prompt=MINUTES_RENDER_SYSTEM,
            build_user_prompt=lambda tmpl, notes: MINUTES_RENDER_USER.format(
                template=tmpl,
                facts=notes,
            ),
            primary=template,
            secondary=facts,
        )
        if truncated:
            user_prompt = user_prompt.replace(
                "</notes>",
                f"{_TRUNCATION_NOTE}\n</notes>",
            )

        content = self._complete(
            client,
            system_prompt=MINUTES_RENDER_SYSTEM,
            user_prompt=user_prompt,
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
        response = client.chat.completions.create(
            model=self._config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )

        content = response.choices[0].message.content
        if not content:
            raise ExternalAPIError("Model returned an empty response.")
        return content.strip()

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
