"""
app/db.py

Data access layer: SQLite connection, CSV-to-SQLite loading, and raw SQL
execution. This module knows nothing about HTTP or FastAPI — that lives
in main.py. Separation of concerns, per section 4 of the build doc.
"""

import os
import re
import sqlite3
import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/data.db")
CSV_PATH = os.getenv("CSV_PATH", "./data/data.csv")

TABLE_NAME = "products"

# Single source of truth for the table schema: maps the final column name
# used throughout the app to its source CSV column and SQLite type.
# text_to_sql.py will import this same SCHEMA in Phase 2 to inject the
# table structure into the model's prompt — defined once here (DRY),
# see section 4 of the build doc.
SCHEMA = {
    "item_id":          {"source": "idPublicacion",     "sql_type": "TEXT PRIMARY KEY"},
    "title":            {"source": "articuloTitulo",     "sql_type": "TEXT NOT NULL"},
    "price":            {"source": "nuevoPrecio",        "sql_type": "REAL"},
    "previous_price":   {"source": "precioAnterior",     "sql_type": "REAL"},
    "discount_pct":     {"source": "precioDiscount",     "sql_type": "REAL"},
    "free_shipping":    {"source": "envioGratis",        "sql_type": "INTEGER"},
    "official_store":   {"source": "esTiendaOficial",    "sql_type": "INTEGER"},
    "in_stock":         {"source": "enStock",            "sql_type": "INTEGER"},
    "seller_name":      {"source": "Vendedor",           "sql_type": "TEXT"},
    "units_sold":       {"source": "cantidadVendida",    "sql_type": "REAL"},
    "rating":           {"source": "produtoReviews",     "sql_type": "REAL"},
    "reviews_count":    {"source": "numeroEvaluaciones", "sql_type": "REAL"},
    "installments_text":{"source": "installments",       "sql_type": "TEXT"},
    "shipping_text":    {"source": "Envio",              "sql_type": "TEXT"},
    "product_link":     {"source": "zProductoLink",      "sql_type": "TEXT"},
    "image_url":        {"source": "imgDireccion",       "sql_type": "TEXT"},
}


class CSVLoadError(Exception):
    """Raised when the source CSV can't be loaded or mapped to SCHEMA."""


def _parse_discount_pct(value):
    """Turn a string like '10% OFF' into the float 10.0. None if missing/unparseable."""
    if pd.isna(value):
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", str(value))
    return float(match.group(1)) if match else None


def _to_nullable_bool(value):
    """Turn pandas True/False/NaN into 1/0/None for SQLite storage."""
    if pd.isna(value):
        return None
    return 1 if bool(value) else 0


def load_csv_to_db(csv_path: str = CSV_PATH, db_path: str = DATABASE_PATH) -> int:
    """
    Read the source CSV, map/clean its columns according to SCHEMA, and
    load it into a fresh SQLite table. Meant to run once at startup, not
    on every query.

    Returns the number of rows loaded.
    Raises CSVLoadError if the file is missing, empty, malformed, or
    missing a column that SCHEMA expects.
    """
    path = Path(csv_path)
    if not path.exists():
        raise CSVLoadError(f"CSV file not found at '{csv_path}'")

    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        raise CSVLoadError(f"CSV file at '{csv_path}' is empty")
    except pd.errors.ParserError as exc:
        raise CSVLoadError(f"CSV file at '{csv_path}' is malformed: {exc}")

    if df.empty:
        raise CSVLoadError(f"CSV file at '{csv_path}' has no rows")

    missing = [info["source"] for info in SCHEMA.values() if info["source"] not in df.columns]
    if missing:
        raise CSVLoadError(f"CSV is missing expected columns: {missing}")

    clean = pd.DataFrame()
    for final_name, info in SCHEMA.items():
        source_col = info["source"]
        if final_name == "discount_pct":
            clean[final_name] = df[source_col].apply(_parse_discount_pct)
        elif final_name in ("free_shipping", "official_store", "in_stock"):
            clean[final_name] = df[source_col].apply(_to_nullable_bool)
        else:
            clean[final_name] = df[source_col]

    if clean["item_id"].duplicated().any():
        logger.warning("Duplicate item_id values found in CSV; keeping first occurrence")
        clean = clean.drop_duplicates(subset="item_id", keep="first")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        columns_sql = ", ".join(f"{name} {info['sql_type']}" for name, info in SCHEMA.items())
        conn.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
        conn.execute(f"CREATE TABLE {TABLE_NAME} ({columns_sql})")
        clean.to_sql(TABLE_NAME, conn, if_exists="append", index=False)
        conn.commit()
    finally:
        conn.close()

    logger.info("Loaded %d rows into '%s' from '%s'", len(clean), TABLE_NAME, csv_path)
    return len(clean)


def get_connection(db_path: str = DATABASE_PATH) -> sqlite3.Connection:
    """
    Open a read-only connection to the SQLite database. Read-only because
    query execution (this service, and the text-to-SQL service in Phase 2)
    should never be able to modify the data — see section 5.1 of the
    build doc for the full rationale.
    """
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def execute_query(sql: str, db_path: str = DATABASE_PATH) -> dict:
    """
    Execute a raw SQL string and return {"columns": [...], "rows": [...]}.

    NOTE: this does NOT validate or sanitize the SQL yet — that's
    explicitly deferred to Phase 2 (see section 5.1: SQL injection
    prevention). In this phase it's called directly from tests/dev
    scripts, not exposed as its own HTTP route.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
    finally:
        conn.close()
    return {"columns": columns, "rows": rows}


def health_check(db_path: str = DATABASE_PATH) -> bool:
    """Used by GET /health: can we open the DB and run a trivial query?"""
    try:
        result = execute_query("SELECT 1", db_path=db_path)
        return result["rows"] == [(1,)]
    except Exception:
        return False