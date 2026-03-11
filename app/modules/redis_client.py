import json
import redis.asyncio as redis
from typing import Optional


REDIS_URL = "redis://redis:6379"
STATE_TTL = 60 * 60 * 24  # 24 hours


def state_key(phone_number: str) -> str:
    return f"client__{phone_number}"


class RedisClient:
    def __init__(self, url: str = REDIS_URL):
        self._redis = redis.from_url(url, decode_responses=True)

    async def get_state(self, phone_number: str) -> Optional[list[str]]:
        raw = await self._redis.get(state_key(phone_number))
        return json.loads(raw) if raw else None

    async def set_state(self, phone_number: str, messages: list[str], ttl: int = STATE_TTL) -> None:
        await self._redis.set(state_key(phone_number), json.dumps(messages), ex=ttl)

    async def append_state(self, phone_number: str, message: str, ttl: int = STATE_TTL) -> list[str]:
        messages = await self.get_state(phone_number) or []
        messages.append(message)
        await self.set_state(phone_number, messages, ttl)
        return messages

    async def delete_state(self, phone_number: str) -> None:
        await self._redis.delete(state_key(phone_number))

    async def aclose(self) -> None:
        await self._redis.aclose()


# FastAPI dependency
redis_client = RedisClient()

async def get_redis_client() -> RedisClient:
    return redis_client