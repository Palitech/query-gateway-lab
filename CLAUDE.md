# query-gateway-lab

A learning project. It is a small version of a governed query gateway: AI agents and HTTP callers send SQL, and the gateway checks it before it runs on a data source.

The owner (TJ) is preparing to explain every line of this code in a job interview. Optimize for code he can understand and defend, not for cleverness.

## Request flow

1. Caller sends a query, a target source, and a bearer token.
2. `auth` validates the JWT: key from JWKS by `kid`, signature, then `iss`, `aud`, `exp`, scopes.
3. `guard` parses the SQL with sqlglot using an explicit dialect. Allow only one read-only SELECT.
4. `scope` collects every table in the parsed query and checks each against the caller's allowlist.
5. `executor` runs the blocking driver call off the event loop, in a read-only transaction, with a statement timeout and a row limit.
6. A `Backend` adapter (Postgres, then Databricks) borrows a pooled connection and returns rows.
7. Logs, metrics, and traces record caller, decision, and latency. Never result rows.

## Layout

```
src/query_gateway/
  api.py            # FastAPI app and routes
  auth.py           # JWT / JWKS validation (FastAPI dependency)
  guard.py          # SQL parsing and read-only rules
  scope.py          # table allowlist enforcement
  executor.py       # threadpool execution, timeouts, row limit
  backends/
    base.py         # Backend Protocol
    postgres.py     # psycopg2 + connection pool
    databricks.py   # databricks-sql-connector
  observability.py  # JSON logging, metrics, tracing
tests/
docs/decisions.md   # short notes: decision, why, alternatives
```

## Stack

Python 3.12, uv, FastAPI, pydantic v2, sqlglot, psycopg2-binary, databricks-sql-connector, PyJWT, pytest, pytest-asyncio, pytest-cov, ruff. Postgres runs in Docker.

Ask before adding any other dependency.

## Rules

- **Synthetic data only.** No real names, no real records, no credentials in code. Secrets come from environment variables.
- **Never block the event loop.** psycopg2 and the Databricks connector are blocking. Never call them directly inside an `async def` handler. Use `asyncio.to_thread` or a plain `def` route.
- **Parse, don't pattern-match.** The guard works on the sqlglot syntax tree. No regex checks on SQL text.
- **Always pass a dialect** to sqlglot (`postgres`, `databricks`).
- **Deny by default.** Unknown statement types, parse errors, and unknown tables are rejected.
- **Never log query results.** Log a hash of the query, not the full text.
- **Check current docs, not memory.** Before choosing a library, version, command, or API, check current docs (Context7) or PyPI metadata, or read the installed package source. Say what you checked.
- **Tests:** TJ writes the guard tests in `tests/test_guard.py`. Do not change or delete those tests without asking. Coverage must stay at 80% or higher.

## How to work with TJ

- Before writing code, state the plan in a few lines and wait for approval on anything non-trivial.
- Keep each change small enough to review in a few minutes.
- For each non-obvious choice, explain why in one or two sentences, and add an entry to `docs/decisions.md`.
- When there are two reasonable approaches, name both and say which you recommend.
- TJ keeps `AI_REVIEW_LOG.md`. Do not edit it.

## Commands

```
uv sync
uv run pytest --cov=query_gateway --cov-fail-under=80
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pre-commit install          # once per clone
uv run pre-commit run --all-files
docker compose up -d postgres
uv run fastapi dev --port 8002
uv run python scripts/concurrency_demo.py
```