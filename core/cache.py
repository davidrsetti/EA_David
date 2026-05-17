from __future__ import annotations

import json, logging, time, functools
from typing import Any, Callable

logger = logging.getLogger(__name__)

# In-memory fallback store: {key: (value, expires_at)}
_mem_cache: dict[str, tuple[Any, float]] = {}
_redis_client = None
_redis_available = False


def _get_redis():
    global _redis_client, _redis_available
    if _redis_client is not None:
        return _redis_client
    try:
        import redis as _redis
        from nexus.config.settings import settings
        host = settings.redis.host
        port = settings.redis.port
        r = _redis.Redis(host=host, port=port, decode_responses=True, socket_connect_timeout=2)
        r.ping()
        _redis_client = r
        _redis_available = True
        logger.info("Redis cache connected at %s:%s", host, port)
    except Exception:
        _redis_available = False
    return _redis_client


def get(key: str) -> Any | None:
    """Get value from cache. Returns None on miss."""
    r = _get_redis()
    if r and _redis_available:
        try:
            raw = r.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            pass
    if key in _mem_cache:
        val, exp = _mem_cache[key]
        if exp == 0 or time.time() < exp:
            return val
        del _mem_cache[key]
    return None


def set(key: str, value: Any, ttl: int = 300) -> None:
    """Set value in cache with TTL in seconds."""
    r = _get_redis()
    if r and _redis_available:
        try:
            r.setex(key, ttl, json.dumps(value, default=str))
            return
        except Exception:
            pass
    _mem_cache[key] = (value, time.time() + ttl if ttl > 0 else 0)


def delete(key: str) -> None:
    r = _get_redis()
    if r and _redis_available:
        try:
            r.delete(key)
        except Exception:
            pass
    _mem_cache.pop(key, None)


def clear_pattern(pattern: str) -> int:
    """Delete all keys matching pattern (glob). Returns count deleted."""
    count = 0
    r = _get_redis()
    if r and _redis_available:
        try:
            keys = r.keys(pattern)
            if keys:
                count = r.delete(*keys)
            return count
        except Exception:
            pass
    import fnmatch
    to_delete = [k for k in list(_mem_cache.keys()) if fnmatch.fnmatch(k, pattern)]
    for k in to_delete:
        del _mem_cache[k]
    return len(to_delete)


def cached(ttl: int = 300, key_prefix: str = ""):
    """Decorator that caches function results. Key = prefix:args_hash."""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            import hashlib
            raw = json.dumps([args, kwargs], default=str, sort_keys=True)
            h   = hashlib.md5(raw.encode()).hexdigest()[:12]
            key = f"{key_prefix or fn.__name__}:{h}"
            hit = get(key)
            if hit is not None:
                return hit
            result = fn(*args, **kwargs)
            set(key, result, ttl=ttl)
            return result
        return wrapper
    return decorator


def is_redis_available() -> bool:
    _get_redis()
    return _redis_available


def stats() -> dict:
    return {
        "backend": "redis" if _redis_available else "in-memory",
        "in_memory_keys": len(_mem_cache),
    }
