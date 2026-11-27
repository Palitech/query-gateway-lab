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

## 6. mypy for type checking

- **Decision:** mypy in `strict` mode on `src/`, configured in `[tool.mypy]` in `pyproject.toml`.
- **Why:** pure Python, installs through `uv` like everything else, and is the reference checker most reviewers know. `strict` costs nothing to turn on while the code base is small.
- **Alternative:** pyright. Faster and stricter by default, but its PyPI package is a wrapper that downloads Node.js.

## 7. Actions pinned to commit SHAs

- **Decision:** every `uses:` in `.github/workflows` points at a full commit SHA, with the tag in a comment.
- **Why:** a tag is a movable label, so if an action's repo is compromised, `@v7` can be pointed at new code. A SHA can't change. Dependabot's `github-actions` updates bump the SHA and the comment together.
- **Alternative:** tag pins (`@v7`). Easier to read, but you trust the action's maintainers on every run.

## 8. gitleaks as a pinned binary in CI

- **Decision:** CI downloads the gitleaks release tarball for a fixed version, checks its SHA-256 against the published checksums file, and runs `gitleaks git` over the full history (`fetch-depth: 0`). Locally, the pre-commit hook scans staged changes.
- **Why:** no third-party action in the path, no licence question (`gitleaks-action` needs a key for organisation repos), and the checksum proves the binary is the published one.
- **Alternative:** `gitleaks/gitleaks-action`. Less YAML, but adds a dependency with write-capable features we don't need.

## 9. Security tools as dev dependencies

- **Decision:** `pre-commit`, `mypy`, `bandit` and `pip-audit` live in the `dev` dependency group.
- **Why:** versions are pinned in `uv.lock`, so local runs and CI use the same versions, and Dependabot updates them like any other package.
- **Alternative:** run them ad hoc with `uvx`. Nothing to install, but versions float between runs.
- **pip-audit detail:** `pip-audit --locked` reads only `pylock.toml` (PEP 751), not `uv.lock` (checked in the installed 2.10.1 source). CI exports the lock with `uv export --format requirements-txt`, which includes hashes, then audits it with `--disable-pip` so the exact pins are checked without resolving again.
