"""
app/models.py

Modelos Pydantic que definen la forma de los datos que entran y salen
por la API. En esta fase solo existe el modelo de respuesta de /health;
los modelos de pregunta/respuesta en lenguaje natural se agregan en la
fase donde se construye ese endpoint.
"""

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    database_connected: bool

class AskRequest(BaseModel):
    # Strips whitespace from `question` before validation runs, so a
    # request with only spaces (e.g. {"question": "   "}) fails
    # min_length instead of silently passing as "valid".
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1)


class AskResponse(BaseModel):
    question: str
    sql: str
    columns: list[str]
    rows: list[list]
    attempts: int