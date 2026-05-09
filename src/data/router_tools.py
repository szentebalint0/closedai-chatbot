from typing import Any, Callable

from data.sql_tools import (
    compare_products,
    get_discounted_products,
    get_hot_products,
    get_product_by_name,
    get_product_details,
    get_product_price,
    get_product_stock,
    get_products_by_category,
    get_products_by_price_range,
    get_recommendation,
    get_similar_products,
    search_products,
)
from llm.router import run_router_model

ToolHandler = Callable[[dict[str, Any]], Any]


def run_router(
    client: Any,
    model: str,
    messages: list[dict[str, str]],
) -> tuple[str | None, Any, str]:
    return run_router_model(client=client, model=model, messages=messages)


def _missing_result(message: str) -> dict[str, Any]:
    return {"message": message}


TOOL_HANDLERS: dict[str, ToolHandler] = {
    "get_hot_products": lambda payload: {"products": get_hot_products()},
    "get_recommendation": lambda payload: {"products": get_recommendation()},
    "get_product_by_name": lambda payload: {
        "product": get_product_by_name(payload.get("name", ""))
    },
    "search_products": lambda payload: {
        "products": search_products(
            query=payload.get("query", ""),
            limit=payload.get("limit"),
        )
    },
    "get_products_by_category": lambda payload: {
        "products": get_products_by_category(
            category=payload.get("category", ""),
            limit=payload.get("limit"),
        )
    },
    "get_product_stock": lambda payload: {
        "stock": get_product_stock(
            product_id=payload.get("product_id"),
            name=payload.get("name"),
        )
    },
    "get_product_price": lambda payload: {
        "price": get_product_price(
            product_id=payload.get("product_id"),
            name=payload.get("name"),
        )
    },
    "get_discounted_products": lambda payload: {
        "products": get_discounted_products(
            limit=payload.get("limit"),
            category=payload.get("category"),
        )
    },
    "get_products_by_price_range": lambda payload: {
        "products": get_products_by_price_range(
            min_price=payload.get("min_price"),
            max_price=payload.get("max_price"),
            category=payload.get("category"),
            limit=payload.get("limit"),
        )
    },
    "get_product_details": lambda payload: {
        "product": get_product_details(
            product_id=payload.get("product_id"),
            name=payload.get("name"),
        )
    },
    "get_similar_products": lambda payload: {
        "products": get_similar_products(
            product_id=payload.get("product_id", ""),
            limit=payload.get("limit"),
        )
    },
    "compare_products": lambda payload: {
        "products": compare_products(
            product_ids=payload.get("product_ids"),
            names=payload.get("names"),
        )
    },
}


def resolve_tool_call(
    route_name: str | None,
    route_payload: Any,
    route_text: str,
) -> tuple[str, dict[str, Any], Any]:
    if not route_name:
        return "", {
            "message": (route_payload.get("message") if isinstance(route_payload, dict) else "") or route_text
        }, None

    payload = route_payload if isinstance(route_payload, dict) else {}
    handler = TOOL_HANDLERS.get(route_name)
    if handler is None:
        return "", _missing_result("Tool is not implemented yet."), None

    try:
        tool_data = handler(payload)
    except ValueError as exc:
        return "", _missing_result(str(exc)), None

    return route_name, payload, tool_data
