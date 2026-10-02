# NL-to-SQL App

System that lets a user ask questions in natural language about a CSV
dataset and get a correct answer, without writing SQL. The natural
language to SQL translation runs on a small language model hosted
locally via Ollama (no external API).

## Overview

The system loads a CSV into a SQL database and exposes it through an API.
A locally hosted model translates the user's natural language question
into a SQL query, which is validated and executed safely against the
database. The result is returned to the user.

## Tech stack

- Python
- FastAPI
- Ollama (local LLM inference)
- SQLite
- Pydantic
- JavaScript + `fetch` (frontend, decoupled from the API)
- Docker + Docker Compose

## Project status

🚧 In progress. See repository branches for feature-by-feature
development history.

## Local installation

```bash
git clone <repo-url>
cd nl-to-sql-app
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash)
pip install -r requirements.txt
cp .env.example .env
```

_(Full `docker compose up` installation instructions pending.)_

## Environment variables

| Variable | Description |
|---|---|
| `OLLAMA_HOST` | Base URL of the Ollama inference API |
| `OLLAMA_MODEL` | Name of the local model used for text-to-SQL |
| `DATABASE_PATH` | Path to the SQLite database file |
| `CSV_PATH` | Path to the source CSV dataset |
| `MAX_QUERY_RESULTS` | Max rows returned by any generated query |
| `QUERY_TIMEOUT_SECONDS` | Execution timeout for generated queries |

## Run

_(Coming soon — full run instructions, including Docker.)_

## Testing the API

A Postman collection is included to test `/ask`, `/health` and
`/internal/query` independently from the UI:
- [Postman collection](postman/nl-to-sql-app.postman_collection.json) (import into Postman)
- [Published documentation](https://documenter.getpostman.com/view/58034286/2sBYHNWiNK) (view in browser, no Postman account needed)

## Project structure

app/
├── main.py # FastAPI endpoints
├── db.py # CSV loading, connection, and query execution
├── text_to_sql.py # Prompt building, Ollama call, SQL validation
├── models.py # Pydantic request/response models
└── static/ # Frontend (HTML/CSS/JS)
data/
└── data.csv
tests/
└── test_sql_validation.py


## Architecture and trade-offs

_(Pending — Phase 7.)_

## Scalability

_(Pending — Phase 7.)_

## Author

Camila Chirino Castell —
💻 Portfolio: [camilachirinocastell-portfolio.netlify.app](https://camilachirinocastell-portfolio.netlify.app)
🐙 GitHub: [github.com/camilachirinocastell](https://github.com/camilachirinocastell)
👤 LinkedIn: [www.linkedin.com/in/camila-chirino-castell](https://www.linkedin.com/in/camila-chirino-castell)
