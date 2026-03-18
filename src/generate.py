import os
from typing import Any

from data.router_tools import resolve_tool_call, run_router
from llm.client import get_llm
from llm.formatter import run_formatter_model

def _build_messages(
    question: str,
    history: list[Any] | None,
    history_window: int,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    default_context = (os.getenv("SYSTEM_PROMPT") or "").strip()
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
    return messages

def _run_formatter(
    client: Any,
    model: str,
    question: str,
    route_name: str,
    route_payload: dict[str, Any],
    tool_data: Any,
) -> str:
    return run_formatter_model(
        client=client,
        model=model,
        question=question,
        route_name=route_name,
        route_payload=route_payload,
        tool_data=tool_data,
    )

def generate_response(
    question: str,
    history: list[Any] | None = None,
    history_window: int = 4,
) -> dict[str, Any]:
    client = get_llm()
    model = os.getenv("LLM_MODEL")
    if not model:
        raise RuntimeError("Missing LLM_MODEL environment variable")

    messages = _build_messages(question=question, history=history, history_window=history_window)
    route_name, route_payload, route_text = run_router(client=client, model=model, messages=messages)
    route_name, route_payload, tool_data = resolve_tool_call(
        route_name=route_name,
        route_payload=route_payload,
        route_text=route_text,
    )

    answer = _run_formatter(
        client=client,
        model=model,
        question=question,
        route_name=route_name,
        route_payload=route_payload,
        tool_data=tool_data,
    )

    return {
        "answer": answer or route_payload.get("message", "") if isinstance(route_payload, dict) else "",
        "tool_used": route_name,
        "data": tool_data,
    }
