"""
models.py

Modelos Pydantic que definen la forma de los datos que entran y salen
por la API. En esta fase solo existe el modelo de respuesta de /health;
los modelos de pregunta/respuesta en lenguaje natural se agregan en la
fase donde se construye ese endpoint.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database_connected: bool