"""
WebSocket 모듈 테스트
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.core.websocket_manager import ConnectionManager
from app.main import app


# ─── ConnectionManager 단위 테스트 ─────────────────


class TestConnectionManager:
    """ConnectionManager 단위 테스트"""

    @pytest.mark.asyncio
    async def test_connect_and_count(self):
        """연결 등록 시 카운트 증가"""
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws, "ALL")
        assert mgr.connection_count == 1

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """연결 해제 시 카운트 감소"""
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws, "ALL")
        mgr.disconnect(ws, "ALL")
        assert mgr.connection_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent(self):
        """없는 연결 해제 시 에러 없음"""
        mgr = ConnectionManager()
        ws = AsyncMock()
        mgr.disconnect(ws, "ALL")  # No error
        assert mgr.connection_count == 0

    @pytest.mark.asyncio
    async def test_multiple_channels(self):
        """다중 채널 연결"""
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await mgr.connect(ws1, "ALL")
        await mgr.connect(ws2, "ICN")
        assert mgr.connection_count == 2
        assert set(mgr.channels) == {"ALL", "ICN"}

    @pytest.mark.asyncio
    async def test_broadcast_to_channel(self):
        """특정 채널 브로드캐스트"""
        mgr = ConnectionManager()
        ws_all = AsyncMock()
        ws_icn = AsyncMock()
        ws_pus = AsyncMock()

        await mgr.connect(ws_all, "ALL")
        await mgr.connect(ws_icn, "ICN")
        await mgr.connect(ws_pus, "PUS")

        data = {"type": "test", "msg": "hello"}
        await mgr.broadcast("ICN", data)

        # ICN 채널 + ALL 채널이 받아야 함
        assert ws_icn.send_text.called
        assert ws_all.send_text.called
        # PUS는 받으면 안 됨
        assert not ws_pus.send_text.called

    @pytest.mark.asyncio
    async def test_broadcast_all(self):
        """전체 브로드캐스트"""
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await mgr.connect(ws1, "ALL")
        await mgr.connect(ws2, "ICN")

        await mgr.broadcast_all({"type": "test"})

        assert ws1.send_text.called
        assert ws2.send_text.called

    @pytest.mark.asyncio
    async def test_send_personal(self):
        """개인 메시지 전송"""
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.send_personal(ws, {"type": "hello"})
        ws.send_json.assert_called_once_with({"type": "hello"})

    @pytest.mark.asyncio
    async def test_dead_connection_cleanup(self):
        """죽은 연결 자동 정리"""
        mgr = ConnectionManager()
        ws_alive = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_text.side_effect = Exception("Connection closed")

        await mgr.connect(ws_alive, "ALL")
        await mgr.connect(ws_dead, "ALL")
        assert mgr.connection_count == 2

        await mgr.broadcast_all({"type": "test"})

        # 죽은 연결이 정리됨
        assert mgr.connection_count == 1


# ─── WebSocket 엔드포인트 통합 테스트 ─────────────


class TestWebSocketEndpoints:
    """WebSocket 엔드포인트 통합 테스트"""

    def test_ws_risks_connect(self):
        """전체 위험지수 WS 연결"""
        client = TestClient(app)
        with client.websocket_connect("/api/v1/ws/risks") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["data"]["channel"] == "ALL"

    def test_ws_airport_connect(self):
        """특정 공항 WS 연결"""
        client = TestClient(app)
        with client.websocket_connect("/api/v1/ws/risks/ICN") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["data"]["channel"] == "ICN"

    def test_ws_ping_pong(self):
        """ping/pong heartbeat"""
        client = TestClient(app)
        with client.websocket_connect("/api/v1/ws/risks") as ws:
            # 연결 메시지 수신
            ws.receive_json()
            # ping 전송
            ws.send_text("ping")
            data = ws.receive_json()
            assert data["type"] == "heartbeat"
            assert "timestamp" in data


# ─── Redis Pub/Sub 테스트 ────────────────────────


class TestRedisPubSub:
    """Redis Pub/Sub 모킹 테스트"""

    def test_publish_sync_graceful_when_no_redis(self):
        """Redis 없을 때 publish_risk_update_sync 에러 없음"""
        from app.core import redis_pubsub
        redis_pubsub._redis_available = True

        # redis 모듈 import가 함수 내부에서 발생 → builtins.__import__ mock
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == "redis":
                raise ImportError("mock no redis")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            redis_pubsub.publish_risk_update_sync({"type": "test"})
            # 에러 없이 완료 (_redis_available=False 로 전환)

    @pytest.mark.asyncio
    async def test_publish_async_graceful_when_no_redis(self):
        """Redis 없을 때 publish_risk_update 에러 없음"""
        from app.core import redis_pubsub
        redis_pubsub._redis_available = True

        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == "aioredis":
                raise ImportError("mock no aioredis")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            await redis_pubsub.publish_risk_update({"type": "test"})
