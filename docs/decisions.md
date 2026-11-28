# Decisions

Short notes: decision, why, alternatives.

## 1. List dependencies explicitly instead of `fastapi[standard]`

- **Decision:** depend on `fastapi`, `fastapi-cli` and `uvicorn[standard]` directly.
- **Why:** in FastAPI 0.165.0 the `standard` extra also installs OpenTelemetry, `pydantic-settings`, `fastapi-cloud-cli`, `jinja2`, `fastar` and more. Listing only what we use keeps every line of `pyproject.toml` explainable. OpenTelemetry and settings get added on purpose when we reach those steps.
- **Alternative:** `fastapi[standard]`. It's one line, but it brings about a dozen packages we didn't choose.

## 2. `httpx2` for the load script

- **Decision:** dev dependency `httpx2`, not `httpx`.
- **Why:** `httpx2` is the pydantic-maintained fork. Starlette 1.10's `TestClient` imports `httpx2` first and falls back to `httpx`, so it's what the stack itself uses. It's listed explicitly because the script imports it directly.
- **Note:** its default timeout is 5s. The script sets 60s because the blocking demo makes the last request wait about 20s.

## 3. A deliberately blocking demo endpoint

- **Decision:** `/demo/blocking` calls `time.sleep` inside `async def`, which breaks our own rule on purpose.
- **Why:** it makes the cost visible. One event-loop thread serves all requests, so 10 concurrent calls are serialised (~20s), compared with ~2s for `/demo/to-thread`. Both endpoints are temporary.

## 4. `asyncio.to_thread` vs a plain `def` route

- **Both are valid** ways to keep blocking driver calls off the loop.
- `asyncio.to_thread` uses the default executor, which has `min(32, cpu_count + 4)` threads. A plain `def` route runs in Starlette/AnyIO's threadpool, which has its own limit.
- **Recommendation for the gateway:** `async def` routes that call `asyncio.to_thread` for only the blocking part. Auth and parsing stay on the loop, and the threaded section is explicit in the code.

## 5. Postgres 18 with secrets from `.env`

- **Decision:** `postgres:18` image. The password comes from `POSTGRES_PASSWORD` in a gitignored `.env`, and compose refuses to start without it.
- **Why 18:** current stable major; 19.0 is brand new. From 18 on, the image's `PGDATA` is version-specific (`/var/lib/postgresql/18/docker`), so the volume mounts at `/var/lib/postgresql`.
- **Data:** one `orders` table with 20 generated rows. Customer and product are codes, never names.
