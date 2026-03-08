from collections.abc import Iterator
import os
from typing import Any

from openai_config import get_llm



def generate_response_stream(
    question: str,
    context: str | None = None,
    history: list[Any] | None = None,
    history_window: int = 6,
) -> Iterator[str]:
    client = get_llm()
    messages: list[dict[str, str]] = []

    default_context = os.getenv("SYSTEM_PROMPT", "").strip()
    if default_context:
        messages.append({"role": "system", "content": default_context})

    if context and context.strip():
        messages.append({"role": "system", "content": f"Additional context:\n{context.strip()}"})

    if history and history_window > 0:
        recent_history = history[-(history_window * 2) :]
        for item in recent_history:
            role = getattr(item, "role", None)
            content = getattr(item, "content", None)
            if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
                messages.append({"role": role, "content": content.strip()})

    messages.append({"role": "user", "content": question})

    stream = client.chat.completions.create(
        model=os.getenv("LLM_MODEL"),
        messages=messages,
        stream=True,
    )

    for chunk in stream:
        # Some streamed events can have no choices or no content delta.
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue

        delta_obj = getattr(choices[0], "delta", None)
        if delta_obj is None:
            continue

        delta = getattr(delta_obj, "content", None)
        if delta is None:
            continue

        if isinstance(delta, str):
            if delta:
                yield delta
            continue

        if isinstance(delta, list):
            for part in delta:
                text = getattr(part, "text", None)
                if text:
                    yield text
