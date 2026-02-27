"""
Redis Pub/Sub 모듈

Celery 워커(다른 프로세스)에서 위험지수 업데이트를 publish하면,
FastAPI 서버가 subscribe하여 WebSocket 클라이언트에 전달합니다.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

RISK_UPDATES_CHANNEL = "risk_updates"

# Redis 가용 여부 플래그
_redis_available = True


_async_redis_pool = None


async def _get_async_redis():
    """비동기 Redis 커넥션 풀 (싱글톤)"""
    global _async_redis_pool
    if _async_redis_pool is not None:
        return _async_redis_pool
    try:
        import aioredis
        from app.config import settings
        _async_redis_pool = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return _async_redis_pool
    except Exception:
        return None


async def publish_risk_update(data: dict):
    """Redis에 위험지수 업데이트 publish (async)"""
    global _redis_available
    if not _redis_available:
        return

    try:
        redis = await _get_async_redis()
        if not redis:
            _redis_available = False
            return
        message = json.dumps(data, ensure_ascii=False, default=str)
        await redis.publish(RISK_UPDATES_CHANNEL, message)
        logger.debug("[PubSub] Published risk update to Redis")
    except Exception:
        _redis_available = False
        logger.debug("[PubSub] Redis unavailable, skipping publish")


def publish_risk_update_sync(data: dict):
    """Redis에 위험지수 업데이트 publish (sync — Celery 태스크용)"""
    global _redis_available
    if not _redis_available:
        return

    try:
        import redis as redis_lib
        from app.config import settings

        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        message = json.dumps(data, ensure_ascii=False, default=str)
        r.publish(RISK_UPDATES_CHANNEL, message)
        r.close()
        logger.debug("[PubSub] Published risk update (sync)")
    except Exception:
        _redis_available = False
        logger.debug("[PubSub] Redis unavailable (sync), skipping")


async def start_redis_subscriber(callback: Callable[[dict], Any]):
    """
    Redis 채널 구독 시작 (FastAPI startup에서 호출).
    수신 메시지마다 callback(data) 호출.
    """
    global _redis_available

    try:
        import aioredis
        from app.config import settings

        redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe(RISK_UPDATES_CHANNEL)

        logger.info("[PubSub] Subscribed to channel: %s", RISK_UPDATES_CHANNEL)

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await callback(data)
                except Exception:
                    logger.exception("[PubSub] Error processing message")

    except Exception:
        _redis_available = False
        logger.info("[PubSub] Redis not available — WebSocket will work without real-time push")
