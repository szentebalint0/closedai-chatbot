import os
from typing import Any

from openai_config import get_llm


def generate_response(
    question: str,
    history: list[Any] | None = None,
    history_window: int = 4,
) -> str:
    client = get_llm()
    messages: list[dict[str, str]] = []

    default_context = os.getenv("SYSTEM_PROMPT", "").strip()
    if default_context:
        messages.append({"role": "system", "content": default_context})

    if history and history_window > 0:
        recent_history = history[-history_window:]
        for item in recent_history:
            role = getattr(item, "role", None)
            content = getattr(item, "content", None)
            if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
                messages.append({"role": role, "content": content.strip()})

    messages.append({"role": "user", "content": question})

    completion = client.chat.completions.create(
        model=os.getenv("LLM_MODEL"),
        messages=messages,
    )

    choices = getattr(completion, "choices", None) or []
    if not choices:
        return ""

    message = getattr(choices[0], "message", None)
    if message is None:
        return ""

    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            text = getattr(part, "text", None)
            if text:
                text_parts.append(text)
        return "".join(text_parts)

    return ""
