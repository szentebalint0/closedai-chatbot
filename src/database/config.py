import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


DB_CONNECTION_STRING_ENV = "DB_CONNECTION_STRING"


def get_database_url() -> str:
    load_dotenv()
    connection_string = os.getenv(DB_CONNECTION_STRING_ENV)
    if not connection_string:
        raise RuntimeError(f"Missing {DB_CONNECTION_STRING_ENV} environment variable")

    return f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}"
