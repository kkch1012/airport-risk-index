"""
Redis 캐시 데코레이터 — Redis 없으면 graceful 패스스루
"""

import json
import hashlib
import logging
import functools
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis():
    """Redis 클라이언트 반환 (lazy init, 실패 시 None)"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis as redis_lib
        from app.config import settings

        _redis_client = redis_lib.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
        )
        _redis_client.ping()
        logger.info("Redis cache connected: %s", settings.REDIS_URL)
        return _redis_client
    except Exception:
        logger.debug("Redis not available, caching disabled")
        _redis_client = False  # sentinel: tried and failed
        return None


def _make_key(prefix: str, *args, **kwargs) -> str:
    """캐시 키 생성"""
    raw = f"{prefix}:{args}:{sorted(kwargs.items())}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"ari:cache:{prefix}:{h}"


def cache_result(prefix: str, ttl_seconds: int = 300):
    """
    async 함수 결과를 Redis에 캐싱하는 데코레이터.
    Redis 없으면 그냥 함수를 실행합니다.

    Usage:
        @cache_result("dashboard", ttl_seconds=300)
        async def get_dashboard(): ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            r = _get_redis()
            if not r:
                return await func(*args, **kwargs)

            key = _make_key(prefix, *args, **kwargs)

            # 캐시 조회
            try:
                cached = r.get(key)
                if cached:
                    logger.debug("Cache HIT: %s", key)
                    return json.loads(cached)
            except Exception:
                pass

            # 함수 실행
            result = await func(*args, **kwargs)

            # 캐시 저장
            try:
                r.setex(key, ttl_seconds, json.dumps(result, default=str))
                logger.debug("Cache SET: %s (ttl=%ds)", key, ttl_seconds)
            except Exception:
                pass

            return result
        return wrapper
    return decorator


def invalidate_cache(prefix: str) -> int:
    """특정 prefix의 캐시 무효화. 삭제된 키 수 반환."""
    r = _get_redis()
    if not r:
        return 0

    try:
        pattern = f"ari:cache:{prefix}:*"
        keys = list(r.scan_iter(match=pattern, count=100))
        if keys:
            deleted = r.delete(*keys)
            logger.info("Cache invalidated: %s (%d keys)", prefix, deleted)
            return deleted
        return 0
    except Exception:
        logger.debug("Cache invalidation failed for %s", prefix)
        return 0


def invalidate_all() -> int:
    """모든 캐시 무효화"""
    r = _get_redis()
    if not r:
        return 0

    try:
        pattern = "ari:cache:*"
        keys = list(r.scan_iter(match=pattern, count=500))
        if keys:
            deleted = r.delete(*keys)
            logger.info("All cache invalidated: %d keys", deleted)
            return deleted
        return 0
    except Exception:
        return 0
