"""
app/main.py

API entry point: instantiates FastAPI, loads the CSV into SQLite on
startup, and exposes /health, /ask (natural language queries), and an
internal endpoint for testing raw SQL queries.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.db import CSVLoadError, execute_query, health_check, load_csv_to_db
from app.text_to_sql import OllamaError, TextToSQLError, ask_database, build_prompt, generate_sql
from app.models import AskRequest, AskResponse, HealthResponse

from pathlib import Path
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ASK_TIMEOUT_SECONDS = float(os.getenv("ASK_TIMEOUT_SECONDS", "120"))
STATIC_DIR = Path(__file__).parent / "static"

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


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    logger.info("Received question: %s", request.question)

    try:
        result = await asyncio.wait_for(
            ask_database(request.question),
            timeout=ASK_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error(
            "Question timed out after %.0fs: %s", ASK_TIMEOUT_SECONDS, request.question
        )
        raise HTTPException(
            status_code=504,
            detail=(
                f"The request took too long to process (over "
                f"{ASK_TIMEOUT_SECONDS:.0f}s). Try rephrasing your question."
            ),
        )
    except TextToSQLError as exc:
        logger.error("Failed to produce SQL for question '%s': %s", request.question, exc)
        raise HTTPException(status_code=422, detail=str(exc))

    logger.info(
        "Resolved question in %d attempt(s): %s -> %s",
        result["attempts"],
        request.question,
        result["sql"],
    )

    return AskResponse(
        question=request.question,
        sql=result["sql"],
        columns=result["columns"],
        rows=result["rows"],
        attempts=result["attempts"],
    )

# Must stay last: a mount at "/" matches every path, so any route
# registered after it would never be reached.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")