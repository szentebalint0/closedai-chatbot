import json
from typing import Any

from llm.content import extract_text_content
from prompts.system import ROUTER_SYSTEM_PROMPT

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
                        "description": "A direct answer for the user.",
                    }
                },
                "required": ["message"],
                "additionalProperties": False,
            },
        },
    },
]


def run_router_model(
    client: Any,
    model: str,
    messages: list[dict[str, str]],
) -> tuple[str | None, Any, str]:
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": ROUTER_SYSTEM_PROMPT}, *messages],
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
    if not tool_calls:
        text = extract_text_content(message)
        return "answer_directly", {"message": text}, text

    tool_call = tool_calls[0]
    function = getattr(tool_call, "function", None)
    tool_name = getattr(function, "name", None)
    raw_arguments = getattr(function, "arguments", "") or "{}"
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError:
        arguments = {}

    return tool_name, arguments, extract_text_content(message)
