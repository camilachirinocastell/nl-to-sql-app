"""
app/text_to_sql.py

Builds the prompt sent to the language model: injects the real database
schema (pulled from db.SCHEMA, the single source of truth) plus a few
worked examples, so a small general-purpose model has enough context to
produce valid SQL for this specific table.
"""
import os
import re
import sqlite3
import httpx
from app.db import SCHEMA, TABLE_NAME, execute_query

# --- Prompt construction -----------------------------------------------

SYSTEM_INSTRUCTIONS = """You are a SQL generator. Your only task is to \
translate a natural language question into a single, read-only SQLite \
SELECT statement for the table described below.

Rules:
- Output only the SQL query. No explanation, no markdown formatting.
- Only SELECT statements are allowed. Never generate INSERT, UPDATE, \
DELETE, DROP, ALTER, ATTACH, PRAGMA, or CREATE.
- Only one statement per query. Never chain statements with semicolons.
- Only use the table and columns listed below. Never invent a column \
that isn't listed.
"""

FEW_SHOT_EXAMPLES = """Examples:

Question: How many products are currently in stock?
SQL: SELECT COUNT(*) FROM products WHERE in_stock = 1;

Question: What are the 5 cheapest products?
SQL: SELECT title, price FROM products ORDER BY price ASC LIMIT 5;

Question: Which seller has the most listings?
SQL: SELECT seller_name, COUNT(*) AS listing_count FROM products \
GROUP BY seller_name ORDER BY listing_count DESC LIMIT 1;
"""


def _format_schema() -> str:
    """Renders db.SCHEMA as a plain-text table description for the prompt."""
    lines = [f"Table: {TABLE_NAME}"]
    for column_name, info in SCHEMA.items():
        lines.append(f"- {column_name} ({info['sql_type']})")
    return "\n".join(lines)


def build_prompt(question: str) -> str:
    """
    Assembles the full prompt: system instructions, the real schema,
    worked examples, and the user's question, in that order.
    """
    return (
        f"{SYSTEM_INSTRUCTIONS}\n"
        f"{_format_schema()}\n\n"
        f"{FEW_SHOT_EXAMPLES}\n"
        f"Question: {question}\n"
        f"SQL:"
    )


"""
    Calls the local Ollama API with the prompt from build_prompt() and
extracts a clean SQL string from the model's raw response.
"""

# --- Calling the model ---------------------------------------------------

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))

class OllamaError(Exception):
    """Raised when the Ollama API can't be reached or returns an error."""


def _extract_sql(raw_response: str) -> str:
    """
    Pulls a clean SQL statement out of the model's raw text response.
    Small models often wrap the query in a markdown code fence even when
    told not to — this strips that, and trims anything after the first
    semicolon so a stray sentence tacked on by the model doesn't get
    treated as part of the query.
    """
    text = raw_response.strip()
    fence_match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    semicolon_index = text.find(";")
    if semicolon_index != -1:
        text = text[: semicolon_index + 1]

    return text.strip()


def generate_sql(prompt: str, timeout: float = OLLAMA_TIMEOUT_SECONDS) -> str:
    """
    Sends the prompt to the local Ollama API and returns a cleaned-up
    SQL string. Raises OllamaError if the service is unreachable or
    responds with an error — callers decide how to handle that (e.g.
    reporting it through /health-style error responses).
    """
    try:
        response = httpx.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise OllamaError(f"Failed to reach Ollama at '{OLLAMA_HOST}': {exc}")

    raw_text = response.json().get("response", "")
    if not raw_text:
        raise OllamaError("Ollama returned an empty response")

    return _extract_sql(raw_text)

"""

SQL validator: acts as an independent security layer that never trusts
the model's output, regardless of what the prompt asked for. See section
5.1 of the build doc for the full threat model.
"""
# --- Validation (independent security layer) ------------------------------
MAX_QUERY_RESULTS = int(os.getenv("MAX_QUERY_RESULTS", "100"))

FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "ATTACH", "PRAGMA", "CREATE", "REPLACE", "TRUNCATE",
)


class SQLValidationError(Exception):
    """Raised when generated SQL fails the security/structure checks."""


def validate_sql(sql: str) -> str:
    """
    Validates generated SQL against a strict allowlist and returns a safe
    version of it (with a result limit enforced). Raises
    SQLValidationError on any violation — column/table existence is
    intentionally NOT checked here: SQLite itself will reject an unknown
    column at execution time, and that real error is what feeds the
    retry loop, instead of duplicating schema knowledge in two places.
    """
    cleaned = sql.strip().rstrip(";").strip()

    if not cleaned:
        raise SQLValidationError("Empty SQL query")

    if not re.match(r"(?is)^select\b", cleaned):
        raise SQLValidationError("Only SELECT statements are allowed")

    if ";" in cleaned:
        raise SQLValidationError("Multiple statements are not allowed")

    upper = cleaned.upper()
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper):
            raise SQLValidationError(f"Forbidden keyword detected: {keyword}")

    if not re.search(rf"\bFROM\s+{re.escape(TABLE_NAME)}\b", cleaned, re.IGNORECASE):
        raise SQLValidationError(f"Query must select from the '{TABLE_NAME}' table")

    if not re.search(r"\bLIMIT\s+\d+", cleaned, re.IGNORECASE):
        cleaned = f"{cleaned} LIMIT {MAX_QUERY_RESULTS}"

    return cleaned


"""

Retry loop: ties together prompt building, model calls, validation, and
execution. If the SQL fails validation or execution, the real error is
fed back to the model so it can correct itself, up to a fixed number of
attempts.
"""


MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))


class TextToSQLError(Exception):
    """Raised when no valid SQL could be produced after all retries."""


def _build_retry_prompt(original_prompt: str, failed_sql: str, error: str) -> str:
    """Appends the failed attempt and its real error to the original prompt."""
    return (
        f"{original_prompt} {failed_sql}\n\n"
        f"That query failed with this error: {error}\n"
        f"Fix the query and respond with only the corrected SQL.\n"
        f"SQL:"
    )


def ask_database(question: str) -> dict:
    """
    Runs the full text-to-SQL flow for one question: build prompt, call
    the model, validate, execute — retrying with the real error as
    feedback if any step fails. Returns the same shape as
    db.execute_query(): {"columns": [...], "rows": [...], "sql": "..."}.
    """
    prompt = build_prompt(question)
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        raw_sql = None
        try:
            raw_sql = generate_sql(prompt)
            safe_sql = validate_sql(raw_sql)
            result = execute_query(safe_sql)
            result["sql"] = safe_sql
            return result
        except OllamaError as exc:
            last_error = str(exc)
            failed_sql = "(the model did not return a query)"
        except SQLValidationError as exc:
            last_error = str(exc)
            failed_sql = raw_sql
        except sqlite3.OperationalError as exc:
            # Real SQLite errors (e.g. "no such column") also feed the retry.
            last_error = str(exc)
            failed_sql = raw_sql

        if attempt < MAX_RETRIES:
            prompt = _build_retry_prompt(prompt, failed_sql, last_error)

    raise TextToSQLError(
        f"Could not produce valid SQL after {MAX_RETRIES} attempts. Last error: {last_error}"
    )