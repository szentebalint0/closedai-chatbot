import json
from typing import Any

from llm.content import extract_text_content
from prompts.system import ROUTER_SYSTEM_PROMPT

ROUTER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_hot_products",
            "description": "Use this when the user asks for hot, top, popular, or most reserved products.",
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
            "description": "Use this when the user asks for a general product recommendation without specific filters.",
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
            "name": "get_product_by_name",
            "description": "Fetch one exact or near-exact product by product name or SKU.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Product name or SKU."},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search products by free text, brand, type, scale, category, SKU, or product attributes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Free text search query."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_products_by_category",
            "description": "List products in a category, such as race car, classic car, accessories, or a category name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Category name or category ID."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["category"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_stock",
            "description": "Fetch current stock and availability for a specific product by product_id, SKU, or name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Hotcakes product BVIN or SKU."},
                    "name": {"type": "string", "description": "Product name if product_id is unknown."},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_price",
            "description": "Fetch current price, list price, and discount status for a specific product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Hotcakes product BVIN or SKU."},
                    "name": {"type": "string", "description": "Product name if product_id is unknown."},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_discounted_products",
            "description": "List products that currently have a lower site price than list price. Use only for sale, discount, akcio, or kedvezmeny requests, not merely cheap products.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    "category": {"type": "string", "description": "Optional category filter."},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_budget_products",
            "description": "List the cheapest currently orderable products. Use for cheap, low-price, affordable, budget, olcso, olcsobb, or legolcsobb requests without an explicit price range. Optional query filters by brand, type, scale, SKU, color, or attributes; category is only for actual category names.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    "query": {"type": "string", "description": "Optional free-text product filter such as brand, type, scale, color, SKU, or attributes."},
                    "category": {"type": "string", "description": "Optional actual category name."},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_products_by_price_range",
            "description": "List products whose current price is inside a requested price range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_price": {"type": "number"},
                    "max_price": {"type": "number"},
                    "category": {"type": "string", "description": "Optional category filter."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": "Fetch a detailed product data sheet including description, properties, category, price, and stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Hotcakes product BVIN or SKU."},
                    "name": {"type": "string", "description": "Product name if product_id is unknown."},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_similar_products",
            "description": "Find similar products based on a selected product's category, manufacturer, and price.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Hotcakes product BVIN or SKU."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["product_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_products",
            "description": "Compare multiple products by IDs, SKUs, or names.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Hotcakes product BVINs or SKUs.",
                    },
                    "names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Product names if IDs are unknown.",
                    },
                },
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
