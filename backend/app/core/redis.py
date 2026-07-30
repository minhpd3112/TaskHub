from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings

redis_client: Redis = aioredis.from_url(  # type: ignore[no-untyped-call]
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Dependency for providing an async Redis client instance."""
    yield redis_client
