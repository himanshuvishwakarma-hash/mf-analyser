"""Thin Redis cache helper.

Used for hot-path API reads where the underlying data updates at most once
per nightly Celery refresh (spec section 2.3 step 3 - 24h TTL).

All cache operations degrade gracefully: if Redis is unreachable the
function falls through to the loader and logs a warning. The API remains
correct, only slower.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import redis
from redis.exceptions import RedisError

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

_DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24 hours

_client: redis.Redis | None = None


def get_client() -> redis.Redis | None:
    """Lazy-initialised Redis client. Returns None if Redis is unreachable."""
    global _client
    if _client is not None:
        return _client
    try:
        settings = get_settings()
        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        _client.ping()
        return _client
    except RedisError as e:  # pragma: no cover
        logger.warning("redis unavailable, cache disabled: %s", e)
        _client = None
        return None


def get_or_set(key: str, loader: Callable[[], Any], ttl: int = _DEFAULT_TTL_SECONDS) -> Any:
    """Return cached JSON-deserialisable value, or compute + cache it."""
    client = get_client()
    if client is None:
        return loader()
    try:
        cached = client.get(key)
        if cached is not None:
            return json.loads(cached)
        value = loader()
        client.setex(key, ttl, json.dumps(value, default=str))
        return value
    except RedisError as e:  # pragma: no cover
        logger.warning("redis op failed (%s), falling back to loader", e)
        return loader()


def invalidate(prefix: str) -> int:
    """Delete every key matching prefix*. Returns count of removed keys."""
    client = get_client()
    if client is None:
        return 0
    try:
        keys = list(client.scan_iter(match=f"{prefix}*"))
        if not keys:
            return 0
        return int(client.delete(*keys))
    except RedisError as e:  # pragma: no cover
        logger.warning("redis invalidate failed: %s", e)
        return 0
