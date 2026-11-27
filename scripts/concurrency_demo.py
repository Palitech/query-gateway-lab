"""Send 10 concurrent requests to each demo endpoint and print the total time.

Start the server first:  uv run fastapi dev --port 8002
Then run:               uv run python scripts/concurrency_demo.py
"""

import asyncio
import time

import httpx2

BASE_URL = "http://127.0.0.1:8002"
CONCURRENT_REQUESTS = 10
# httpx2 defaults to a 5s timeout. The blocking endpoint makes the last
# request wait ~20s, so allow much longer.
TIMEOUT_SECONDS = 60


async def time_endpoint(client: httpx2.AsyncClient, path: str) -> float:
    start = time.perf_counter()
    responses = await asyncio.gather(
        *(client.get(path) for _ in range(CONCURRENT_REQUESTS))
    )
    elapsed = time.perf_counter() - start
    for response in responses:
        response.raise_for_status()
    return elapsed


async def main() -> None:
    async with httpx2.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT_SECONDS) as client:
        for path in ("/demo/blocking", "/demo/to-thread"):
            elapsed = await time_endpoint(client, path)
            print(f"{path:<18} {CONCURRENT_REQUESTS} requests in {elapsed:5.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
