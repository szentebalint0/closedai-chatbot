import json
from typing import Any

from llm.content import extract_text_content
from prompts.system import ROUTER_SYSTEM_PROMPT

ROUTER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_hot_products",
            "description": "Use this if the user asks for the most popular products",
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
            "name": "get_recommendation",
            "description": "Use this if the user ask for any recommendation about products",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    }
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
        reasoning_effort= "none" #Can be "xhigh", "high", "medium", "low", "minimal" or "none" (OpenAI-style)#Can be "xhigh", "high", "medium", "low", "minimal" or "none" (OpenAI-style)
    )

    choices = getattr(completion, "choices", None) or []
    if not choices:
        return None, {}, ""

    message = getattr(choices[0], "message", None)
    if message is None:
        return None, {}, ""

    tool_calls = getattr(message, "tool_calls", None) or []
    if not tool_calls:
        text = extract_text_content(message)
        return None, {}, text

    tool_call = tool_calls[0]
    function = getattr(tool_call, "function", None)
    tool_name = getattr(function, "name", None)
    raw_arguments = getattr(function, "arguments", "") or "{}"
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError:
        arguments = {}

    return tool_name, arguments, extract_text_content(message)
