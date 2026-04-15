"""Redis-backed session/PKCE store."""

from __future__ import annotations

import os
from typing import Optional

import redis.asyncio as aioredis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

_redis: Optional[aioredis.Redis] = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def set(key: str, value: str, ttl: int = 3600) -> None:
    await get_redis().setex(key, ttl, value)


async def get(key: str) -> Optional[str]:
    return await get_redis().get(key)


async def delete(key: str) -> None:
    await get_redis().delete(key)


async def close() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
