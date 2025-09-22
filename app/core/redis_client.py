# app/core/redis.py

import redis.asyncio as redis
from app.core.config import settings

redis_pool = redis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_redis_client() -> redis.Redis:
    """Dependency to get a Redis client from the connection pool."""
    return redis_pool
