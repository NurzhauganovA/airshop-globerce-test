import asyncio
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

from redis.asyncio import Redis
from redis.exceptions import LockError


class AsyncJSONCache(Protocol):

    async def get(self, key: str) -> dict | None:
        ...

    async def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        ...


class RedisJSONCache:

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, key: str) -> dict | None:
        cached = await self._redis.get(key)
        try:
            return cached and json.loads(cached)
        except (TypeError, json.JSONDecodeError):
            return None

    async def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        await self._redis.set(key, json.dumps(value), ex=ttl_seconds)


@dataclass(frozen=True)
class OrderIdempotencyKey:
    phone_number: str
    internal_order_id: str

    def cache_key(self, prefix: str) -> str:
        return f"{prefix}{self.phone_number}:{self.internal_order_id}"

    def lock_key(self) -> str:
        return f"order:idempotency:{self.phone_number}:{self.internal_order_id}"


class RedisLockManager:

    def __init__(
            self,
            redis: Redis,
            key: str,
            *,
            lock_timeout_seconds: int,
            blocking_timeout_seconds: int,
            retry_delay_seconds: float,
    ) -> None:
        self._lock = redis.lock(key, timeout=lock_timeout_seconds)
        self._blocking_timeout_seconds = blocking_timeout_seconds
        self._retry_delay_seconds = retry_delay_seconds
        self._acquired = False

    async def acquire(self) -> None:
        while True:
            obtained = await self._lock.acquire(
                blocking=True, blocking_timeout=self._blocking_timeout_seconds
            )
            if obtained:
                self._acquired = True
                return
            await asyncio.sleep(self._retry_delay_seconds)

    async def release(self) -> None:
        if not self._acquired:
            return
        try:
            await self._lock.release()
        except LockError:
            pass
        finally:
            self._acquired = False


class OrderCreationIdempotencyService:

    def __init__(
            self,
            *,
            cache: AsyncJSONCache,
            lock_builder: Callable[[], RedisLockManager],
            cache_ttl_seconds: int,
            cache_key_prefix: str,
    ) -> None:
        self._cache = cache
        self._lock_builder = lock_builder
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache_key_prefix = cache_key_prefix

    async def execute(
            self,
            *,
            key: OrderIdempotencyKey,
            operation: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        cache_key = key.cache_key(self._cache_key_prefix)

        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        lock_manager = self._lock_builder()
        await lock_manager.acquire()
        try:
            cached = await self._cache.get(cache_key)
            if cached:
                return cached

            response = await operation()
            await self._cache.set(cache_key, response, self._cache_ttl_seconds)
            return response
        finally:
            await lock_manager.release()
