import json
from typing import Any

from llm.content import extract_text_content
from prompts.system import FORMATTER_SYSTEM_PROMPT


def run_formatter_model(
    client: Any,
    model: str,
    question: str,
    route_name: str,
    route_payload: dict[str, Any],
    tool_data: Any,
) -> str:
    formatter_input = {
        "user_question": question,
        "route_name": route_name,
        "sql_result": tool_data,
        "direct_answer": route_payload.get("message", ""),
    }

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": FORMATTER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(formatter_input, ensure_ascii=True),
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

    return extract_text_content(message)
