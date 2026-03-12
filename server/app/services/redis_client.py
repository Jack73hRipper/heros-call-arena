"""
Redis Client — Connection management for match state storage.

For Phase 1, the in-memory match manager handles state directly.
This module provides the Redis connection for action queues and session tracking
once we scale beyond single-process.
"""

from __future__ import annotations

import redis.asyncio as redis

from app.config import settings


class RedisManager:
    """Manages async Redis connection lifecycle."""

    def __init__(self):
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis. Silently continues if Redis is unavailable (dev mode)."""
        try:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            print(f"[Redis] Connected to {settings.REDIS_URL}")
        except Exception as e:
            print(f"[Redis] Connection failed ({e}) — running without Redis (in-memory only)")
            self._redis = None

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.close()
            print("[Redis] Disconnected")

    @property
    def client(self) -> redis.Redis | None:
        return self._redis

    @property
    def is_connected(self) -> bool:
        return self._redis is not None


redis_manager = RedisManager()
