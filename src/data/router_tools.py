from typing import Any

from data.sql_tools import get_hot_products
from llm.router import run_router_model


def run_router(
    client: Any,
    model: str,
    messages: list[dict[str, str]],
) -> tuple[str | None, Any, str]:
    return run_router_model(client=client, model=model, messages=messages)


def resolve_tool_call(
    route_name: str | None,
    route_payload: Any,
    route_text: str,
) -> tuple[str, dict[str, Any], Any]:
    if route_name == "get_hot_products":
        return route_name, route_payload if isinstance(route_payload, dict) else {}, {"products": get_hot_products()}

    if route_name:
        return "", {"message": "Tool is not implemented yet."}, None

    return "", {
        "message": (route_payload.get("message") if isinstance(route_payload, dict) else "") or route_text
    }, None
