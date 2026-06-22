from __future__ import annotations

from typing import Any

from openai import OpenAI
from openai.types.chat import ChatCompletion


class LLMResponseError(Exception):
    """LLM response unusable — caller may retry with smaller input."""


def create_chat_completion(
    client: OpenAI,
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int | None = None,
) -> ChatCompletion:
    """Call chat completions like llama.cpp UI — omit max_tokens unless explicitly set."""
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return client.chat.completions.create(**kwargs)


def extract_message_text(message) -> str | None:
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()

    extras = getattr(message, "model_extra", None) or {}
    for key in ("reasoning_content", "reasoning", "thinking"):
        value = extras.get(key) or getattr(message, key, None)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def chat_completion_text(response: ChatCompletion) -> str:
    if not response.choices:
        raise LLMResponseError("Model returned no choices.")

    choice = response.choices[0]
    text = extract_message_text(choice.message)
    if text:
        return text

    finish_reason = getattr(choice, "finish_reason", None)
    if finish_reason == "length":
        raise LLMResponseError(
            "Model hit output/context limit before returning text "
            f"(finish_reason=length). Try a smaller input or raise llama.cpp context size."
        )

    detail = f" (finish_reason={finish_reason})" if finish_reason else ""
    raise LLMResponseError(f"Model returned an empty response{detail}.")


def is_retriable_length_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "finish_reason=length",
            "output/context limit",
            "maximum context length",
            "context length",
            "too many tokens",
            "max_model_len",
            "token limit",
            "context window",
        )
    )
