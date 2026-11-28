"""FastAPI app and routes.

The /demo routes exist only to show why blocking calls must stay off the
event loop. They will be removed once the real query route exists.
"""

import asyncio
import time

from fastapi import FastAPI

app = FastAPI(title="query-gateway")

DEMO_SLEEP_SECONDS = 2


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/demo/blocking")
async def demo_blocking() -> dict[str, str]:
    """Deliberately WRONG: breaks the 'never block the event loop' rule.

    time.sleep blocks the single event-loop thread, so no other request
    can be handled until it returns. 10 concurrent calls take ~20s.
    """
    time.sleep(DEMO_SLEEP_SECONDS)  # noqa: ASYNC251 - deliberate, see docstring
    return {"endpoint": "blocking"}


@app.get("/demo/to-thread")
async def demo_to_thread() -> dict[str, str]:
    """Correct: runs the blocking call in a worker thread.

    The event loop awaits the thread and keeps serving other requests
    meanwhile. 10 concurrent calls take ~2s.
    """
    await asyncio.to_thread(time.sleep, DEMO_SLEEP_SECONDS)
    return {"endpoint": "to-thread"}
