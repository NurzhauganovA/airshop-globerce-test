import asyncio
import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from redis.asyncio import Redis
from redis.exceptions import LockError
from starlette import status

from app.controllers.airlink_controller import airlink_controller
from app.controllers.internal import user_controller, customer_controller
from app.core.config import settings
from app.schemas.airlink_schemas import CreateOrderByAirlinkAndPhoneNumberResponse
from app.services.airlink.create_order import CreateOrderByAirlinkService

ORDER_RESPONSE_CACHE_PREFIX = "order:create:response:"
ORDER_RESPONSE_CACHE_TTL_SECONDS = 60
LOCK_TIMEOUT_SECONDS = 60
LOCK_BLOCKING_TIMEOUT_SECONDS = 2
LOCK_RETRY_DELAY_SECONDS = 0.1


@dataclass
class BaseIdempotencyKey:
    def cache_key(self, prefix: str) -> str:
        raise NotImplementedError

    def lock_key(self) -> str:
        raise NotImplementedError


@dataclass
class OrderIdempotencyKey(BaseIdempotencyKey):
    phone_number: str
    internal_order_id: str

    def cache_key(self, prefix: str) -> str:
        return f"{prefix}{self.phone_number}:{self.internal_order_id}"

    def lock_key(self) -> str:
        return f"order:idempotency:{self.phone_number}:{self.internal_order_id}"


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


class BaseIdempotencyService:

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
            key: BaseIdempotencyKey,
            **kwargs
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

            response = await self.operation(**kwargs)
            await self._cache.set(cache_key, response, self._cache_ttl_seconds)
            return response
        finally:
            await lock_manager.release()

    async def operation(self, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


class OrderCreationIdempotencyService(BaseIdempotencyService):

    @classmethod
    def create_service(
            cls,
            *,
            redis: Redis,
            key: OrderIdempotencyKey,
            lock_timeout=LOCK_TIMEOUT_SECONDS,
            blocking_timeout=LOCK_BLOCKING_TIMEOUT_SECONDS,
            retry_delay=LOCK_RETRY_DELAY_SECONDS,
    ) -> "OrderCreationIdempotencyService":
        cache = RedisJSONCache(redis)

        def lock_builder() -> RedisLockManager:
            return RedisLockManager(
                redis,
                key=key.lock_key(),
                lock_timeout_seconds=lock_timeout,
                blocking_timeout_seconds=blocking_timeout,
                retry_delay_seconds=retry_delay,
            )

        return OrderCreationIdempotencyService(
            cache=cache,
            lock_builder=lock_builder,
            cache_ttl_seconds=ORDER_RESPONSE_CACHE_TTL_SECONDS,
            cache_key_prefix=ORDER_RESPONSE_CACHE_PREFIX,
        )

    async def operation(self, **kwargs) -> dict[str, Any]:
        db = kwargs['db']
        try:
            db = kwargs['db']
            phone_number = kwargs['phone_number']
            airlink_id = kwargs['airlink_id']
            saleor_service = kwargs['saleor_service']

            user = user_controller.get_or_create_with_phone(
                db=db, phone_number=phone_number, commit=True
            )
            if not user.customer_profile:
                customer_controller.create_from_user(db=db, user=user, commit=True)

            airlink = airlink_controller.get(db, id=airlink_id)
            order_service = CreateOrderByAirlinkService(
                airlink=airlink,
                saleor_service=saleor_service,
                user=user,
                customer_id=user.customer_profile.id,
                customer_email=user.get_email_or_default,
                saleor_channel_id=settings.LINK_SALEOR_CHANNEL_ID,
            )
            saleor_order_id = await order_service.create_order()
            freedom_p2p_response = await order_service.create_freedom_p2p_order()
            order_service.create_transaction(
                db=db,
                saleor_order_id=saleor_order_id,
                freedom_p2p_order_id=freedom_p2p_response.get("refer", "")
            )

            response = CreateOrderByAirlinkAndPhoneNumberResponse(
                code=status.HTTP_200_OK,
                message="success",
                order_id=saleor_order_id,
            )
        except Exception as err:
            db.rollback()
            print(err)
            code = getattr(err, 'status_code', None) or status.HTTP_500_INTERNAL_SERVER_ERROR

            response = CreateOrderByAirlinkAndPhoneNumberResponse(
                code=code,
                message="error",
                order_id=None,
            )

        return response.model_dump()
