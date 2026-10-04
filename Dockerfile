# Dockerfile
#
# Builds the image for the `app` service: a FastAPI backend that serves
# both the JSON API and the static frontend. Does not include Ollama —
# that runs as a separate service, defined in docker-compose.yml.

FROM python:3.11-slim

WORKDIR /code

# Install dependencies first, in their own layer, so Docker can reuse
# this layer on rebuilds as long as requirements.txt hasn't changed —
# code changes alone won't force a slow pip install again.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the actual application code.
COPY app/ ./app/
COPY data/ ./data/

# Run as a non-root user: the app doesn't need root privileges, and
# limiting them reduces the blast radius if the container is ever
# compromised.
RUN useradd --create-home appuser && chown -R appuser:appuser /code
USER appuser

EXPOSE 8000

# No --reload here: that flag is a development convenience, not meant
# for a container that should run as a stable, predictable process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]