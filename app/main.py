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
from app.text_to_sql import OllamaError, OllamaUnavailableError, TextToSQLError, ask_database, build_prompt, generate_sql
from app.models import AskRequest, AskResponse, HealthResponse

from pathlib import Path
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ASK_TIMEOUT_SECONDS = float(os.getenv("ASK_TIMEOUT_SECONDS", "120"))
STATIC_DIR = Path(__file__).parent / "static"

WARMUP_MAX_RETRIES = int(os.getenv("WARMUP_MAX_RETRIES", "10"))
WARMUP_BACKOFF_SECONDS = float(os.getenv("WARMUP_BACKOFF_SECONDS", "5"))


async def _warm_up_model():
    """
    Tries to warm up the model, retrying with a fixed delay between
    attempts. This matters specifically under Docker: the `ollama`
    service's healthcheck only confirms its server is responding — not
    that the model has finished downloading (`ollama pull` can take
    minutes on a slow connection). Without this, `app` could start
    serving real questions before the model is ready, and a real
    question's own retry loop (MAX_RETRIES in ask_database) is tuned for
    correcting bad SQL, not for waiting out a multi-GB download — it
    would exhaust its few quick attempts long before the pull finishes.
    """
    warmup_prompt = build_prompt("How many rows are in the table?")
    for attempt in range(1, WARMUP_MAX_RETRIES + 1):
        try:
            await generate_sql(warmup_prompt)
            logger.info("Startup: Ollama model warmed up (attempt %d)", attempt)
            return
        except OllamaError as exc:
            logger.warning(
                "Startup: model warm-up attempt %d/%d failed: %s",
                attempt, WARMUP_MAX_RETRIES, exc,
            )
            if attempt < WARMUP_MAX_RETRIES:
                await asyncio.sleep(WARMUP_BACKOFF_SECONDS)

    logger.warning(
        "Startup: model warm-up did not succeed after %d attempts; "
        "will warm up on first request instead",
        WARMUP_MAX_RETRIES,
    )


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

    # Warm-up: loads the model into memory before the first real question
    # arrives, so that person doesn't pay the cold-start cost (~40s
    # measured locally). Retries with backoff instead of trying once —
    # see _warm_up_model() for why that matters under Docker.
    await _warm_up_model()

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
    except OllamaUnavailableError as exc:
        logger.error("Ollama unavailable for question '%s': %s", request.question, exc)
        raise HTTPException(
            status_code=503,
            detail="The language model is currently unavailable. Please try again shortly.",
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
