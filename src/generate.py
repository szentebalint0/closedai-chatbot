import os
import json
from typing import Any

from openai_config import get_llm
from sql_tools import get_hot_products

ROUTER_SYSTEM_PROMPT = """
You are a routing assistant for a sales chatbot.
Decide whether to call a tool or answer directly.

Available tools:
- get_hot_products: use when the user asks about hot, top, most reserved, or popular products.
- answer_directly: use when no tool is needed.

Prefer get_hot_products only when it clearly matches the user's request.
""".strip()

FORMATTER_SYSTEM_PROMPT = """
You write the final frontend answer.
Return a concise helpful answer grounded only in the provided inputs.
If products are provided, summarize the result and mention the most relevant items.
Do not invent data that is not present.
""".strip()

ROUTER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_hot_products",
            "description": "Fetch the top 5 hottest products ordered by QuantityReserved descending.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "answer_directly",
            "description": "Use this when no SQL tool is needed and a normal answer is enough.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "A direct draft answer for the user.",
                    }
                },
                "required": ["message"],
                "additionalProperties": False,
            },
        },
    },
]


def _extract_text_content(message: Any) -> str:
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


def _run_router(
    client: Any,
    model: str,
    messages: list[dict[str, str]],
) -> tuple[str | None, Any, str]:
    router_messages = [{"role": "system", "content": ROUTER_SYSTEM_PROMPT}, *messages]
    completion = client.chat.completions.create(
        model=model,
        messages=router_messages,
        tools=ROUTER_TOOLS,
        tool_choice="auto",
        reasoning_effort="none",
    )

    choices = getattr(completion, "choices", None) or []
    if not choices:
        return "answer_directly", {"message": ""}, ""

    message = getattr(choices[0], "message", None)
    if message is None:
        return "answer_directly", {"message": ""}, ""

    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        tool_call = tool_calls[0]
        function = getattr(tool_call, "function", None)
        tool_name = getattr(function, "name", None)
        raw_arguments = getattr(function, "arguments", "") or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            arguments = {}
        return tool_name, arguments, _extract_text_content(message)

    return "answer_directly", {"message": _extract_text_content(message)}, _extract_text_content(message)


def _run_formatter(
    client: Any,
    model: str,
    question: str,
    route_name: str,
    route_payload: dict[str, Any],
    tool_data: Any,
) -> str:
    formatter_payload = {
        "question": question,
        "route_name": route_name,
        "route_payload": route_payload,
        "tool_data": tool_data,
    }
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": FORMATTER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(formatter_payload, ensure_ascii=True),
            },
        ],
        reasoning_effort="none",
    )

    choices = getattr(completion, "choices", None) or []
    if not choices:
        return ""

    message = getattr(choices[0], "message", None)
    if message is None:
        return ""

    return _extract_text_content(message)

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
    route_name, route_payload, route_text = _run_router(client=client, model=model, messages=messages)

    tool_data: Any = None
    if route_name == "get_hot_products":
        tool_data = {"products": get_hot_products()}
    else:
        route_name = "answer_directly"
        route_payload = {
            "message": (route_payload.get("message") if isinstance(route_payload, dict) else "") or route_text
        }

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
