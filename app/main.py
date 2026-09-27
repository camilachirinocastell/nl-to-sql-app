"""
app/main.py

Entry point de la API: instancia FastAPI, carga el CSV en SQLite al
arrancar el servicio, y expone /health y un endpoint interno para
probar consultas SQL directas mientras no existe el flujo en
lenguaje natural.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.db import CSVLoadError, execute_query, health_check, load_csv_to_db
from app.models import HealthResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Se carga el CSV una sola vez, al levantar el proceso. Si falla, se
    # loguea pero no se frena el arranque: /health va a reportar el
    # problema en vez de que el contenedor muera sin explicación.
    try:
        rows = load_csv_to_db()
        logger.info("Startup: %d rows loaded into the database", rows)
    except CSVLoadError as exc:
        logger.error("Startup: failed to load CSV: %s", exc)
    yield


app = FastAPI(title="NL-to-SQL App", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", database_connected=health_check())


class InternalQueryRequest(BaseModel):
    sql: str


@app.post("/internal/query")
def internal_query(request: InternalQueryRequest):
    # Endpoint interno para probar la capa de datos por HTTP. Todavía no
    # valida el SQL recibido (eso se agrega antes de conectarlo a
    # cualquier fuente que no sea de confianza, como un modelo).
    try:
        return execute_query(request.sql)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))