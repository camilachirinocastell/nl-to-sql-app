"""
app/main.py

API entry point: instantiates FastAPI, loads the CSV into SQLite on
startup, and exposes /health and an internal endpoint for testing raw
SQL queries while the natural language flow doesn't exist yet.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.db import CSVLoadError, execute_query, health_check, load_csv_to_db
from app.text_to_sql import OllamaError, build_prompt, generate_sql
from app.models import HealthResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The CSV is loaded once, when the process starts. If it fails, it's
    # logged but doesn't stop startup: /health will report the problem
    # instead of the container dying without explanation.
    try:
        rows = load_csv_to_db()
        logger.info("Startup: %d rows loaded into the database", rows)
    except CSVLoadError as exc:
        logger.error("Startup: failed to load CSV: %s", exc)

    # Warm-up: loads the model into memory before the first real
    # question arrives, so that person doesn't pay the cold-start cost
    # (~40s measured locally). If Ollama isn't reachable yet, log it as
    # a warning and keep starting up anyway — the first real question
    # will just pay the cold-start cost itself, same as before this
    # existed.
    try:
        warmup_prompt = build_prompt("How many rows are in the table?")
        await generate_sql(warmup_prompt)
        logger.info("Startup: Ollama model warmed up")
    except OllamaError as exc:
        logger.warning(
            "Startup: model warm-up failed, will warm up on first request instead: %s",
            exc,
        )

    yield


app = FastAPI(title="NL-to-SQL App", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", database_connected=health_check())


class InternalQueryRequest(BaseModel):
    sql: str


@app.post("/internal/query")
def internal_query(request: InternalQueryRequest):
    # Internal endpoint to test the data layer over HTTP. Doesn't
    # validate the received SQL yet (that gets added before connecting
    # it to any untrusted source, like a model).
    try:
        return execute_query(request.sql)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))