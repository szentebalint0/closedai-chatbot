from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from database import get_engine

GET_HOT_PRODUCTS_SQL = """SELECT TOP 5
    ProductName,
    CAST(ROUND(BasePrice, 0) AS DECIMAL(10,0)) AS Price
    FROM DNN.dbo.hcc_LineItem
    ORDER BY QuantityReserved DESC"""


def _to_json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def get_hot_products() -> list[dict[str, Any]]:
    engine = get_engine()
    with engine.connect() as connection:
        result = connection.execute(text(GET_HOT_PRODUCTS_SQL))
        rows = result.mappings().all()

    return [
        {key: _to_json_value(value) for key, value in row.items()}
        for row in rows
    ]
