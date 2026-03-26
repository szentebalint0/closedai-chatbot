import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

def get_database_url() -> str:
    load_dotenv()
    connection_string = os.getenv("DB_CONNECTION_STRING")
    if not connection_string:
        raise RuntimeError(f"Missing connection string environment variable")

    return f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}"
