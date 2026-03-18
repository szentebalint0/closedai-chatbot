from typing import Any


def extract_text_content(message: Any) -> str:
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
