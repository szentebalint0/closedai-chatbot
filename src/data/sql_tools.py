import html
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text

from database import get_engine

PRODUCT_TABLE = "[dbo].[hcc_Product]"
PRODUCT_TRANSLATION_TABLE = "[dbo].[hcc_ProductTranslations]"
CATEGORY_TABLE = "[dbo].[hcc_Category]"
CATEGORY_TRANSLATION_TABLE = "[dbo].[hcc_CategoryTranslations]"
PRODUCT_CATEGORY_TABLE = "[dbo].[hcc_ProductXCategory]"
INVENTORY_TABLE = "[dbo].[hcc_ProductInventory]"
MANUFACTURER_TABLE = "[dbo].[hcc_Manufacturer]"
PRODUCT_TYPE_TABLE = "[dbo].[hcc_ProductType]"
PRODUCT_TYPE_TRANSLATION_TABLE = "[dbo].[hcc_ProductTypeTranslations]"
PRODUCT_PROPERTY_TABLE = "[dbo].[hcc_ProductProperty]"
PRODUCT_PROPERTY_TRANSLATION_TABLE = "[dbo].[hcc_ProductPropertyTranslations]"
PRODUCT_PROPERTY_VALUE_TABLE = "[dbo].[hcc_ProductPropertyValue]"
PRODUCT_PROPERTY_VALUE_TRANSLATION_TABLE = "[dbo].[hcc_ProductPropertyValueTranslations]"
LINE_ITEM_TABLE = "[dbo].[hcc_LineItem]"
ORDER_TABLE = "[dbo].[hcc_Order]"

MAX_LIMIT = 20
DEFAULT_LIMIT = 5
MAX_SEARCH_TOKENS = 8
ACTIVE_PRODUCT_CONDITION = "p.Status = 1"
TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
HTML_BLOCK_PATTERN = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
WHITESPACE_PATTERN = re.compile(r"\s+")
SEARCH_STOP_TOKENS = {
    "a",
    "az",
    "egy",
    "es",
    "vagy",
    "modell",
    "model",
    "auto",
    "car",
    "termek",
    "product",
    "keres",
    "keresek",
    "mutass",
    "ajanlj",
    "ajanl",
    "ajanlas",
    "olcso",
    "olcsobb",
    "olcsot",
    "legolcsobb",
    "budget",
    "cheap",
    "cheaper",
    "cheapest",
    "szeretnek",
    "van",
    "ar",
    "ara",
    "keszlet",
    "raktar",
    "raktaron",
}
SEARCH_TOKEN_SYNONYMS = {
    "arany": ["gold"],
    "barna": ["brown"],
    "ezust": ["silver"],
    "feher": ["white"],
    "fekete": ["black"],
    "kek": ["blue"],
    "klasszikus": ["classic"],
    "lila": ["purple"],
    "narancs": ["orange"],
    "piros": ["red"],
    "sarga": ["yellow"],
    "szurke": ["grey", "gray"],
    "verseny": ["race", "racing"],
    "versenyauto": ["race", "racing"],
    "voros": ["red"],
    "zold": ["green"],
}

GET_HOT_PRODUCTS_SQL = f"""SELECT TOP 5
    ranked.product_id,
    p.SKU AS sku,
    ptx.ProductName AS name,
    cat.categories AS categories,
    CAST(ROUND(p.SitePrice, 0) AS DECIMAL(18, 0)) AS price,
    CAST(p.IsAvailableForSale AS bit) AS is_available_for_sale,
    CAST(0 AS bit) AS stock_is_tracked,
    CASE
        WHEN p.IsAvailableForSale = 0 THEN 'not_available'
        ELSE 'available'
    END AS availability_status,
    ranked.popularity_rank
FROM (
    SELECT
        li.ProductId AS product_id,
        ROW_NUMBER() OVER (ORDER BY SUM(li.Quantity) DESC, li.ProductName) AS popularity_rank
    FROM {LINE_ITEM_TABLE} li
    INNER JOIN {ORDER_TABLE} o
        ON o.bvin = li.OrderBvin
        AND o.StoreId = li.StoreId
    INNER JOIN {PRODUCT_TABLE} p
        ON p.bvin = li.ProductId
        AND p.StoreId = li.StoreId
    WHERE o.IsPlaced = 1
        AND {ACTIVE_PRODUCT_CONDITION}
    GROUP BY li.ProductId, li.ProductName
) ranked
INNER JOIN {PRODUCT_TABLE} p
    ON p.bvin = ranked.product_id
OUTER APPLY (
    SELECT TOP 1 tr.ProductName
    FROM {PRODUCT_TRANSLATION_TABLE} tr
    WHERE tr.ProductId = p.bvin
    ORDER BY
        CASE
            WHEN tr.Culture IN ('hu-HU', 'hu') THEN 0
            WHEN tr.Culture IN ('en-US', 'en') THEN 1
            ELSE 2
        END,
        tr.ProductTranslationId
) ptx
OUTER APPLY (
    SELECT STUFF((
        SELECT ', ' + COALESCE(c_name.Name, CONVERT(nvarchar(36), c.bvin))
        FROM {PRODUCT_CATEGORY_TABLE} pxc
        INNER JOIN {CATEGORY_TABLE} c
            ON c.bvin = pxc.CategoryId
            AND c.StoreId = pxc.StoreId
        OUTER APPLY (
            SELECT TOP 1 ctr.Name
            FROM {CATEGORY_TRANSLATION_TABLE} ctr
            WHERE ctr.CategoryId = c.bvin
            ORDER BY
                CASE
                    WHEN ctr.Culture IN ('hu-HU', 'hu') THEN 0
                    WHEN ctr.Culture IN ('en-US', 'en') THEN 1
                    ELSE 2
                END,
                ctr.CategoryTranslationId
        ) c_name
        WHERE pxc.ProductId = p.bvin
            AND pxc.StoreId = p.StoreId
            AND c.Hidden = 0
        ORDER BY pxc.SortOrder, c_name.Name
        FOR XML PATH(''), TYPE
    ).value('.', 'nvarchar(max)'), 1, 2, '') AS categories
) cat
ORDER BY ranked.popularity_rank"""

PRODUCT_SUMMARY_FIELDS = """
    p.bvin AS product_id,
    p.SKU AS sku,
    ptx.ProductName AS name,
    ptx.ShortDescription AS short_description,
    cat.categories AS categories,
    m.DisplayName AS manufacturer,
    pttx.ProductTypeName AS product_type,
    CAST(ROUND(p.SitePrice, 0) AS DECIMAL(18, 0)) AS price,
    CAST(ROUND(NULLIF(p.ListPrice, 0), 0) AS DECIMAL(18, 0)) AS list_price,
    CAST(
        ROUND(
            CASE
                WHEN p.ListPrice > p.SitePrice AND p.ListPrice > 0
                    THEN p.ListPrice - p.SitePrice
                ELSE 0
            END,
            0
        ) AS DECIMAL(18, 0)
    ) AS discount_amount,
    CAST(
        CASE
            WHEN p.ListPrice > p.SitePrice AND p.ListPrice > 0 THEN 1
            ELSE 0
        END AS bit
    ) AS is_discounted,
    CAST(p.IsAvailableForSale AS bit) AS is_available_for_sale,
    CAST(
        CASE
            WHEN inv.quantity_available IS NULL THEN 0
            ELSE 1
        END AS bit
    ) AS stock_is_tracked,
    inv.quantity_on_hand,
    inv.quantity_reserved,
    inv.quantity_available,
    CASE
        WHEN p.IsAvailableForSale = 0 THEN 'not_available'
        WHEN inv.quantity_available IS NULL THEN 'available'
        WHEN inv.quantity_available <= 0 THEN 'out_of_stock'
        WHEN inv.low_stock_point IS NOT NULL
            AND inv.quantity_available <= inv.low_stock_point THEN 'low_stock'
        ELSE 'in_stock'
    END AS availability_status
""".strip()

PRODUCT_DETAIL_FIELDS = f"""{PRODUCT_SUMMARY_FIELDS},
    CAST(LEFT(ptx.LongDescription, 4000) AS nvarchar(4000)) AS long_description,
    ptx.MetaTitle AS meta_title,
    ptx.MetaDescription AS meta_description,
    ptx.Keywords AS keywords,
    p.ImageFileSmall AS image_small,
    p.ImageFileMedium AS image_medium,
    p.RewriteUrl AS rewrite_url,
    p.ShippingWeight AS shipping_weight,
    p.ShippingLength AS shipping_length,
    p.ShippingWidth AS shipping_width,
    p.ShippingHeight AS shipping_height,
    props.properties AS properties"""

PRODUCT_FROM_FRAGMENT = f"""
FROM {PRODUCT_TABLE} p
OUTER APPLY (
    SELECT TOP 1
        tr.ProductName,
        tr.ShortDescription,
        tr.LongDescription,
        tr.MetaTitle,
        tr.MetaDescription,
        tr.Keywords
    FROM {PRODUCT_TRANSLATION_TABLE} tr
    WHERE tr.ProductId = p.bvin
    ORDER BY
        CASE
            WHEN tr.Culture IN ('hu-HU', 'hu') THEN 0
            WHEN tr.Culture IN ('en-US', 'en') THEN 1
            ELSE 2
        END,
        tr.ProductTranslationId
) ptx
LEFT JOIN {MANUFACTURER_TABLE} m
    ON m.bvin = p.ManufacturerID
    AND m.StoreId = p.StoreId
LEFT JOIN {PRODUCT_TYPE_TABLE} pt
    ON pt.bvin = p.ProductTypeId
    AND pt.StoreId = p.StoreId
OUTER APPLY (
    SELECT TOP 1 tr.ProductTypeName
    FROM {PRODUCT_TYPE_TRANSLATION_TABLE} tr
    WHERE tr.ProductTypeId = pt.bvin
    ORDER BY
        CASE
            WHEN tr.Culture IN ('hu-HU', 'hu') THEN 0
            WHEN tr.Culture IN ('en-US', 'en') THEN 1
            ELSE 2
        END,
        tr.ProductTypeTranslationId
) pttx
OUTER APPLY (
    SELECT
        SUM(pi.QuantityOnHand) AS quantity_on_hand,
        SUM(pi.QuantityReserved) AS quantity_reserved,
        SUM(pi.QuantityAvailableForSale) AS quantity_available,
        MAX(pi.LowStockPoint) AS low_stock_point
    FROM {INVENTORY_TABLE} pi
    WHERE pi.ProductBvin = p.bvin
        AND pi.StoreId = p.StoreId
) inv
OUTER APPLY (
    SELECT STUFF((
        SELECT ', ' + COALESCE(c_name.Name, CONVERT(nvarchar(36), c.bvin))
        FROM {PRODUCT_CATEGORY_TABLE} pxc
        INNER JOIN {CATEGORY_TABLE} c
            ON c.bvin = pxc.CategoryId
            AND c.StoreId = pxc.StoreId
        OUTER APPLY (
            SELECT TOP 1 ctr.Name
            FROM {CATEGORY_TRANSLATION_TABLE} ctr
            WHERE ctr.CategoryId = c.bvin
            ORDER BY
                CASE
                    WHEN ctr.Culture IN ('hu-HU', 'hu') THEN 0
                    WHEN ctr.Culture IN ('en-US', 'en') THEN 1
                    ELSE 2
                END,
                ctr.CategoryTranslationId
        ) c_name
        WHERE pxc.ProductId = p.bvin
            AND pxc.StoreId = p.StoreId
            AND c.Hidden = 0
        ORDER BY pxc.SortOrder, c_name.Name
        FOR XML PATH(''), TYPE
    ).value('.', 'nvarchar(max)'), 1, 2, '') AS categories
) cat
""".strip()

PRODUCT_PROPERTIES_APPLY = f"""
OUTER APPLY (
    SELECT STUFF((
        SELECT '; '
            + COALESCE(NULLIF(ppt.DisplayName, ''), pp.PropertyName)
            + ': '
            + COALESCE(NULLIF(ppvt.PropertyLocalizableValue, ''), ppv.PropertyValue)
        FROM {PRODUCT_PROPERTY_VALUE_TABLE} ppv
        INNER JOIN {PRODUCT_PROPERTY_TABLE} pp
            ON pp.Id = ppv.PropertyId
            AND pp.StoreId = ppv.StoreId
        OUTER APPLY (
            SELECT TOP 1 ptr.DisplayName
            FROM {PRODUCT_PROPERTY_TRANSLATION_TABLE} ptr
            WHERE ptr.ProductPropertyId = pp.Id
            ORDER BY
                CASE
                    WHEN ptr.Culture IN ('hu-HU', 'hu') THEN 0
                    WHEN ptr.Culture IN ('en-US', 'en') THEN 1
                    ELSE 2
                END,
                ptr.ProductPropertyTranslationId
        ) ppt
        OUTER APPLY (
            SELECT TOP 1 pvtr.PropertyLocalizableValue
            FROM {PRODUCT_PROPERTY_VALUE_TRANSLATION_TABLE} pvtr
            WHERE pvtr.ProductPropertyValueId = ppv.Id
            ORDER BY
                CASE
                    WHEN pvtr.Culture IN ('hu-HU', 'hu') THEN 0
                    WHEN pvtr.Culture IN ('en-US', 'en') THEN 1
                    ELSE 2
                END,
                pvtr.ProductPropertyValueTranslationId
        ) ppvt
        WHERE ppv.ProductBvin = p.bvin
            AND ppv.StoreId = p.StoreId
            AND pp.DisplayOnSite = 1
            AND NULLIF(LTRIM(RTRIM(COALESCE(ppvt.PropertyLocalizableValue, ppv.PropertyValue))), '') IS NOT NULL
        ORDER BY COALESCE(NULLIF(ppt.DisplayName, ''), pp.PropertyName)
        FOR XML PATH(''), TYPE
    ).value('.', 'nvarchar(max)'), 1, 2, '') AS properties
) props
""".strip()


def _to_json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _clean_html_text(value: str, max_length: int = 1200) -> str:
    without_blocks = HTML_BLOCK_PATTERN.sub(" ", value)
    without_tags = HTML_TAG_PATTERN.sub(" ", without_blocks)
    cleaned = WHITESPACE_PATTERN.sub(" ", html.unescape(without_tags)).strip()
    return cleaned[:max_length].strip()


def _clean_row_value(key: str, value: Any) -> Any:
    json_value = _to_json_value(value)
    if not isinstance(json_value, str):
        return json_value
    if key in {"long_description", "short_description", "meta_description", "properties"}:
        return _clean_html_text(json_value)
    return json_value


def _run_query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    engine = get_engine()
    with engine.connect() as connection:
        result = connection.execute(text(sql), params or {})
        rows = result.mappings().all()

    return [
        {key: _clean_row_value(key, value) for key, value in row.items()}
        for row in rows
    ]


def _first_or_none(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return rows[0] if rows else None


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _escape_like_value(value: str) -> str:
    return (
        value
        .replace("~", "~~")
        .replace("[", "~[")
        .replace("%", "~%")
        .replace("_", "~_")
    )


def _like_pattern(value: str) -> str:
    return f"%{_escape_like_value(value)}%"


def _prefix_like_pattern(value: str) -> str:
    return f"{_escape_like_value(value)}%"


def _normalize_search_token(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value.casefold())
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _search_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for match in TOKEN_PATTERN.findall(value):
        token = match.strip()
        normalized = _normalize_search_token(token)
        if not normalized or normalized in seen:
            continue
        if normalized in SEARCH_STOP_TOKENS:
            continue
        if len(token) < 2 and not token.isdigit():
            continue
        seen.add(normalized)
        tokens.append(token)
        if len(tokens) >= MAX_SEARCH_TOKENS:
            break
    return tokens


def _token_alternatives(token: str) -> list[str]:
    alternatives: list[str] = []
    seen: set[str] = set()
    for value in [token, _normalize_search_token(token), *SEARCH_TOKEN_SYNONYMS.get(_normalize_search_token(token), [])]:
        value = value.strip()
        normalized = value.casefold()
        if not value or normalized in seen:
            continue
        seen.add(normalized)
        alternatives.append(value)
    return alternatives


def _coerce_limit(value: Any, default: int = DEFAULT_LIMIT, maximum: int = MAX_LIMIT) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, maximum))


def _coerce_price(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    return [
        item.strip()
        for item in str(value).split(",")
        if item.strip()
    ]


def _text_match_condition(pattern_param: str) -> str:
    return f"""(
        ptx.ProductName LIKE :{pattern_param} ESCAPE '~'
        OR p.SKU LIKE :{pattern_param} ESCAPE '~'
        OR ptx.ShortDescription LIKE :{pattern_param} ESCAPE '~'
        OR ptx.LongDescription LIKE :{pattern_param} ESCAPE '~'
        OR ptx.Keywords LIKE :{pattern_param} ESCAPE '~'
        OR m.DisplayName LIKE :{pattern_param} ESCAPE '~'
        OR pttx.ProductTypeName LIKE :{pattern_param} ESCAPE '~'
        OR EXISTS (
            SELECT 1
            FROM {PRODUCT_CATEGORY_TABLE} pxc_search
            INNER JOIN {CATEGORY_TABLE} c_search
                ON c_search.bvin = pxc_search.CategoryId
                AND c_search.StoreId = pxc_search.StoreId
            INNER JOIN {CATEGORY_TRANSLATION_TABLE} ct_search
                ON ct_search.CategoryId = c_search.bvin
            WHERE pxc_search.ProductId = p.bvin
                AND pxc_search.StoreId = p.StoreId
                AND ct_search.Name LIKE :{pattern_param} ESCAPE '~'
        )
        OR EXISTS (
            SELECT 1
            FROM {PRODUCT_PROPERTY_VALUE_TABLE} ppv_search
            INNER JOIN {PRODUCT_PROPERTY_TABLE} pp_search
                ON pp_search.Id = ppv_search.PropertyId
                AND pp_search.StoreId = ppv_search.StoreId
            LEFT JOIN {PRODUCT_PROPERTY_TRANSLATION_TABLE} ppt_search
                ON ppt_search.ProductPropertyId = pp_search.Id
            LEFT JOIN {PRODUCT_PROPERTY_VALUE_TRANSLATION_TABLE} ppvt_search
                ON ppvt_search.ProductPropertyValueId = ppv_search.Id
            WHERE ppv_search.ProductBvin = p.bvin
                AND ppv_search.StoreId = p.StoreId
                AND (
                    ppv_search.PropertyValue LIKE :{pattern_param} ESCAPE '~'
                    OR ppvt_search.PropertyLocalizableValue LIKE :{pattern_param} ESCAPE '~'
                    OR ppt_search.DisplayName LIKE :{pattern_param} ESCAPE '~'
                    OR pp_search.PropertyName LIKE :{pattern_param} ESCAPE '~'
                )
        )
    )"""


def _tokenized_text_match_condition(
    value: str,
    params: dict[str, Any],
    prefix: str,
) -> str:
    tokens = _search_tokens(value)
    if not tokens:
        return ""

    token_conditions: list[str] = []
    for index, token in enumerate(tokens):
        alternative_conditions: list[str] = []
        for alternative_index, alternative in enumerate(_token_alternatives(token)):
            key = f"{prefix}_token_{index}_{alternative_index}"
            params[key] = _like_pattern(alternative)
            alternative_conditions.append(_text_match_condition(key))
        token_conditions.append("(" + " OR ".join(alternative_conditions) + ")")

    return "(" + " AND ".join(token_conditions) + ")"


def _category_name_match_condition(pattern_param: str) -> str:
    return f"""EXISTS (
        SELECT 1
        FROM {CATEGORY_TRANSLATION_TABLE} ct_filter
        WHERE ct_filter.CategoryId = c_filter.bvin
            AND ct_filter.Name LIKE :{pattern_param} ESCAPE '~'
    )"""


def _product_identity_condition(
    product_id: str | None,
    name: str | None,
    params: dict[str, Any],
) -> str:
    conditions: list[str] = []
    if product_id:
        params["product_id"] = product_id
        conditions.append("(CONVERT(nvarchar(36), p.bvin) = :product_id OR p.SKU = :product_id)")
    if name:
        params["name"] = name
        params["name_pattern"] = _like_pattern(name)
        conditions.append(
            "(ptx.ProductName = :name OR p.SKU = :name OR ptx.ProductName LIKE :name_pattern ESCAPE '~')"
        )
        tokenized_condition = _tokenized_text_match_condition(name, params, "name")
        if tokenized_condition:
            conditions.append(tokenized_condition)
    if not conditions:
        raise ValueError("Hianyzik a termek azonositoja vagy neve.")
    return "(" + " OR ".join(conditions) + ")"


def _category_filter_condition(category: str, params: dict[str, Any]) -> str:
    params["category"] = category
    params["category_pattern"] = _like_pattern(category)
    category_name_conditions = [_category_name_match_condition("category_pattern")]
    tokens = _search_tokens(category)
    if tokens:
        for index, token in enumerate(tokens):
            alternative_conditions: list[str] = []
            for alternative_index, alternative in enumerate(_token_alternatives(token)):
                key = f"category_token_{index}_{alternative_index}"
                params[key] = _like_pattern(alternative)
                alternative_conditions.append(_category_name_match_condition(key))
            category_name_conditions.append("(" + " OR ".join(alternative_conditions) + ")")

    return f"""EXISTS (
        SELECT 1
        FROM {PRODUCT_CATEGORY_TABLE} pxc_filter
        INNER JOIN {CATEGORY_TABLE} c_filter
            ON c_filter.bvin = pxc_filter.CategoryId
            AND c_filter.StoreId = pxc_filter.StoreId
        WHERE pxc_filter.ProductId = p.bvin
            AND pxc_filter.StoreId = p.StoreId
            AND c_filter.Hidden = 0
            AND (
                CONVERT(nvarchar(36), c_filter.bvin) = :category
                OR {category_name_conditions[0]}
                OR ({" AND ".join(category_name_conditions[1:]) if len(category_name_conditions) > 1 else "1 = 0"})
            )
    )"""


def _search_condition(query: str, params: dict[str, Any]) -> str:
    params["query"] = query
    params["query_pattern"] = _like_pattern(query)
    full_phrase_condition = _text_match_condition("query_pattern")
    tokenized_condition = _tokenized_text_match_condition(query, params, "query")
    if not tokenized_condition:
        return full_phrase_condition
    return f"({full_phrase_condition} OR {tokenized_condition})"


def get_hot_products() -> list[dict[str, Any]]:
    return _run_query(GET_HOT_PRODUCTS_SQL)


def get_product_by_name(name: str) -> dict[str, Any] | None:
    name = _clean_text(name)
    if not name:
        raise ValueError("Hianyzik a termek neve.")

    params: dict[str, Any] = {}
    identity_condition = _product_identity_condition(None, name, params)
    sql = f"""SELECT TOP 1
    {PRODUCT_SUMMARY_FIELDS}
{PRODUCT_FROM_FRAGMENT}
WHERE {ACTIVE_PRODUCT_CONDITION}
    AND {identity_condition}
ORDER BY
    CASE
        WHEN ptx.ProductName = :name THEN 0
        WHEN p.SKU = :name THEN 1
        WHEN ptx.ProductName LIKE :name_pattern ESCAPE '~' THEN 2
        ELSE 3
    END,
    ptx.ProductName"""
    return _first_or_none(_run_query(sql, params))


def search_products(query: str, limit: Any = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    query = _clean_text(query)
    if not query:
        raise ValueError("Hianyzik a keresesi kifejezes.")

    params: dict[str, Any] = {"limit": _coerce_limit(limit)}
    search_condition = _search_condition(query, params)
    params["query_prefix"] = _prefix_like_pattern(query)

    sql = f"""SELECT TOP (:limit)
    {PRODUCT_SUMMARY_FIELDS}
{PRODUCT_FROM_FRAGMENT}
WHERE {ACTIVE_PRODUCT_CONDITION}
    AND {search_condition}
ORDER BY
    CASE
        WHEN ptx.ProductName = :query THEN 0
        WHEN p.SKU = :query THEN 1
        WHEN ptx.ProductName LIKE :query_prefix ESCAPE '~' THEN 2
        WHEN ptx.ProductName LIKE :query_pattern ESCAPE '~' THEN 3
        ELSE 4
    END,
    ptx.ProductName"""
    return _run_query(sql, params)


def get_products_by_category(
    category: str,
    limit: Any = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    category = _clean_text(category)
    if not category:
        raise ValueError("Hianyzik a kategoria.")

    params: dict[str, Any] = {"limit": _coerce_limit(limit)}
    category_condition = _category_filter_condition(category, params)

    sql = f"""SELECT TOP (:limit)
    {PRODUCT_SUMMARY_FIELDS}
{PRODUCT_FROM_FRAGMENT}
WHERE {ACTIVE_PRODUCT_CONDITION}
    AND {category_condition}
ORDER BY ptx.ProductName"""
    return _run_query(sql, params)


def get_product_stock(
    product_id: str | None = None,
    name: str | None = None,
) -> dict[str, Any] | None:
    params: dict[str, Any] = {}
    identity_condition = _product_identity_condition(
        _clean_text(product_id) or None,
        _clean_text(name) or None,
        params,
    )

    sql = f"""SELECT TOP 1
    p.bvin AS product_id,
    p.SKU AS sku,
    ptx.ProductName AS name,
    CAST(p.IsAvailableForSale AS bit) AS is_available_for_sale,
    CAST(
        CASE
            WHEN inv.quantity_available IS NULL THEN 0
            ELSE 1
        END AS bit
    ) AS stock_is_tracked,
    inv.quantity_on_hand,
    inv.quantity_reserved,
    inv.quantity_available,
    CASE
        WHEN p.IsAvailableForSale = 0 THEN 'not_available'
        WHEN inv.quantity_available IS NULL THEN 'available'
        WHEN inv.quantity_available <= 0 THEN 'out_of_stock'
        WHEN inv.low_stock_point IS NOT NULL
            AND inv.quantity_available <= inv.low_stock_point THEN 'low_stock'
        ELSE 'in_stock'
    END AS availability_status,
    inv.low_stock_point
{PRODUCT_FROM_FRAGMENT}
WHERE {ACTIVE_PRODUCT_CONDITION}
    AND {identity_condition}
ORDER BY ptx.ProductName"""
    return _first_or_none(_run_query(sql, params))


def get_product_price(
    product_id: str | None = None,
    name: str | None = None,
) -> dict[str, Any] | None:
    params: dict[str, Any] = {}
    identity_condition = _product_identity_condition(
        _clean_text(product_id) or None,
        _clean_text(name) or None,
        params,
    )

    sql = f"""SELECT TOP 1
    p.bvin AS product_id,
    p.SKU AS sku,
    ptx.ProductName AS name,
    CAST(ROUND(p.SitePrice, 0) AS DECIMAL(18, 0)) AS price,
    CAST(ROUND(NULLIF(p.ListPrice, 0), 0) AS DECIMAL(18, 0)) AS list_price,
    CAST(
        ROUND(
            CASE
                WHEN p.ListPrice > p.SitePrice AND p.ListPrice > 0
                    THEN p.ListPrice - p.SitePrice
                ELSE 0
            END,
            0
        ) AS DECIMAL(18, 0)
    ) AS discount_amount,
    CAST(
        CASE
            WHEN p.ListPrice > p.SitePrice AND p.ListPrice > 0 THEN 1
            ELSE 0
        END AS bit
    ) AS is_discounted
{PRODUCT_FROM_FRAGMENT}
WHERE {ACTIVE_PRODUCT_CONDITION}
    AND {identity_condition}
ORDER BY ptx.ProductName"""
    return _first_or_none(_run_query(sql, params))


def get_discounted_products(
    limit: Any = DEFAULT_LIMIT,
    category: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": _coerce_limit(limit)}
    conditions = [
        ACTIVE_PRODUCT_CONDITION,
        "p.ListPrice > p.SitePrice",
        "p.ListPrice > 0",
    ]

    category = _clean_text(category)
    if category:
        conditions.append(_category_filter_condition(category, params))

    sql = f"""SELECT TOP (:limit)
    {PRODUCT_SUMMARY_FIELDS}
{PRODUCT_FROM_FRAGMENT}
WHERE {" AND ".join(conditions)}
ORDER BY
    (p.ListPrice - p.SitePrice) DESC,
    ptx.ProductName"""
    return _run_query(sql, params)


def get_products_by_price_range(
    min_price: Any = None,
    max_price: Any = None,
    category: str | None = None,
    limit: Any = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    min_value = _coerce_price(min_price)
    max_value = _coerce_price(max_price)
    if min_value is None and max_value is None:
        raise ValueError("Hianyzik a minimum vagy maximum ar.")
    if min_value is not None and max_value is not None and min_value > max_value:
        min_value, max_value = max_value, min_value

    params: dict[str, Any] = {"limit": _coerce_limit(limit, default=10)}
    conditions = [ACTIVE_PRODUCT_CONDITION]
    if min_value is not None:
        params["min_price"] = min_value
        conditions.append("p.SitePrice >= :min_price")
    if max_value is not None:
        params["max_price"] = max_value
        conditions.append("p.SitePrice <= :max_price")

    category = _clean_text(category)
    if category:
        conditions.append(_category_filter_condition(category, params))

    sql = f"""SELECT TOP (:limit)
    {PRODUCT_SUMMARY_FIELDS}
{PRODUCT_FROM_FRAGMENT}
WHERE {" AND ".join(conditions)}
ORDER BY p.SitePrice ASC, ptx.ProductName"""
    return _run_query(sql, params)


def get_budget_products(
    limit: Any = DEFAULT_LIMIT,
    query: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": _coerce_limit(limit, default=10)}
    conditions = [
        ACTIVE_PRODUCT_CONDITION,
        "p.IsAvailableForSale = 1",
        "p.SitePrice > 0",
    ]

    query = _clean_text(query)
    if query:
        conditions.append(_search_condition(query, params))

    category = _clean_text(category)
    if category:
        conditions.append(_category_filter_condition(category, params))

    sql = f"""SELECT TOP (:limit)
    {PRODUCT_SUMMARY_FIELDS}
{PRODUCT_FROM_FRAGMENT}
WHERE {" AND ".join(conditions)}
ORDER BY p.SitePrice ASC, ptx.ProductName"""
    return _run_query(sql, params)


def get_product_details(
    product_id: str | None = None,
    name: str | None = None,
) -> dict[str, Any] | None:
    params: dict[str, Any] = {}
    identity_condition = _product_identity_condition(
        _clean_text(product_id) or None,
        _clean_text(name) or None,
        params,
    )

    sql = f"""SELECT TOP 1
    {PRODUCT_DETAIL_FIELDS}
{PRODUCT_FROM_FRAGMENT}
{PRODUCT_PROPERTIES_APPLY}
WHERE {ACTIVE_PRODUCT_CONDITION}
    AND {identity_condition}
ORDER BY ptx.ProductName"""
    return _first_or_none(_run_query(sql, params))


def get_similar_products(product_id: str, limit: Any = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    product_id = _clean_text(product_id)
    if not product_id:
        raise ValueError("Hianyzik a termek azonositoja.")

    params: dict[str, Any] = {
        "product_id": product_id,
        "limit": _coerce_limit(limit),
    }
    sql = f"""WITH target AS (
    SELECT TOP 1
        p.bvin,
        p.StoreId,
        p.SitePrice,
        p.ManufacturerID
    FROM {PRODUCT_TABLE} p
    WHERE {ACTIVE_PRODUCT_CONDITION}
        AND (CONVERT(nvarchar(36), p.bvin) = :product_id OR p.SKU = :product_id)
)
SELECT TOP (:limit)
    {PRODUCT_SUMMARY_FIELDS}
{PRODUCT_FROM_FRAGMENT}
CROSS JOIN target t
WHERE {ACTIVE_PRODUCT_CONDITION}
    AND p.bvin <> t.bvin
    AND (
        p.ManufacturerID = t.ManufacturerID
        OR ABS(p.SitePrice - t.SitePrice) <=
            CASE WHEN t.SitePrice > 0 THEN t.SitePrice * 0.25 ELSE 5000 END
        OR EXISTS (
            SELECT 1
            FROM {PRODUCT_CATEGORY_TABLE} target_cat
            INNER JOIN {PRODUCT_CATEGORY_TABLE} product_cat
                ON product_cat.CategoryId = target_cat.CategoryId
                AND product_cat.StoreId = target_cat.StoreId
            WHERE target_cat.ProductId = t.bvin
                AND product_cat.ProductId = p.bvin
                AND product_cat.StoreId = p.StoreId
        )
    )
ORDER BY
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM {PRODUCT_CATEGORY_TABLE} target_cat
            INNER JOIN {PRODUCT_CATEGORY_TABLE} product_cat
                ON product_cat.CategoryId = target_cat.CategoryId
                AND product_cat.StoreId = target_cat.StoreId
            WHERE target_cat.ProductId = t.bvin
                AND product_cat.ProductId = p.bvin
                AND product_cat.StoreId = p.StoreId
        ) THEN 0
        ELSE 1
    END,
    CASE WHEN p.ManufacturerID = t.ManufacturerID THEN 0 ELSE 1 END,
    ABS(p.SitePrice - t.SitePrice),
    ptx.ProductName"""
    return _run_query(sql, params)


def compare_products(
    product_ids: list[str] | str | None = None,
    names: list[str] | str | None = None,
) -> list[dict[str, Any]]:
    ids = _as_list(product_ids)[:5]
    product_names = _as_list(names)[:5]
    if not ids and not product_names:
        raise ValueError("Hianyoznak az osszehasonlitando termekek.")

    params: dict[str, Any] = {"limit": max(1, min(len(ids) + len(product_names), MAX_LIMIT))}
    conditions: list[str] = []

    if ids:
        id_placeholders: list[str] = []
        for index, product_id in enumerate(ids):
            key = f"product_id_{index}"
            params[key] = product_id
            id_placeholders.append(f":{key}")
        conditions.append(
            f"(CONVERT(nvarchar(36), p.bvin) IN ({', '.join(id_placeholders)}) OR p.SKU IN ({', '.join(id_placeholders)}))"
        )

    for index, product_name in enumerate(product_names):
        key = f"name_{index}"
        params[key] = _like_pattern(product_name)
        condition = f"ptx.ProductName LIKE :{key} ESCAPE '~'"
        tokenized_condition = _tokenized_text_match_condition(product_name, params, key)
        if tokenized_condition:
            condition = f"({condition} OR {tokenized_condition})"
        conditions.append(condition)

    sql = f"""SELECT TOP (:limit)
    {PRODUCT_DETAIL_FIELDS}
{PRODUCT_FROM_FRAGMENT}
{PRODUCT_PROPERTIES_APPLY}
WHERE {ACTIVE_PRODUCT_CONDITION}
    AND ({" OR ".join(conditions)})
ORDER BY ptx.ProductName"""
    return _run_query(sql, params)


def get_recommendation() -> list[dict[str, Any]]:
    return get_hot_products()
