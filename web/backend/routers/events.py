"""SSE endpoint for real-time job progress."""

import asyncio
import json
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from ..config import settings

router = APIRouter(tags=["events"])


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: UUID):
    """Server-Sent Events stream for job progress."""

    async def event_generator():
        r = aioredis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        channel = f"job:{job_id}:progress"
        await pubsub.subscribe(channel)

        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0,
                )
                if message and message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    yield {"event": "progress", "data": data}

                    # Close stream on terminal status
                    try:
                        parsed = json.loads(data)
                        if parsed.get("status") in ("completed", "failed"):
                            yield {"event": "done", "data": data}
                            return
                    except json.JSONDecodeError:
                        pass
                else:
                    # Send keepalive
                    yield {"event": "ping", "data": ""}
                    await asyncio.sleep(1)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await r.close()

    return EventSourceResponse(event_generator())
