"""
WebSocket 연결 관리자

채널 기반 WebSocket 연결 관리. 클라이언트는 "ALL" 또는 특정 공항코드 채널에 구독합니다.
"""

import json
import logging
from typing import Any, Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 연결 관리"""

    def __init__(self):
        # {channel: [WebSocket, ...]}
        self._connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str = "ALL"):
        """WebSocket 연결 수락 및 채널 등록"""
        await websocket.accept()
        if channel not in self._connections:
            self._connections[channel] = []
        self._connections[channel].append(websocket)
        logger.info("[WS] Connected: channel=%s (total=%d)", channel, self.connection_count)

    def disconnect(self, websocket: WebSocket, channel: str = "ALL"):
        """WebSocket 연결 해제"""
        if channel in self._connections:
            try:
                self._connections[channel].remove(websocket)
            except ValueError:
                pass
            if not self._connections[channel]:
                del self._connections[channel]
        logger.info("[WS] Disconnected: channel=%s (total=%d)", channel, self.connection_count)

    async def broadcast(self, channel: str, data: dict):
        """특정 채널에 브로드캐스트 (+ ALL 채널에도 전송)"""
        targets = set()

        # 특정 채널 구독자
        if channel in self._connections:
            targets.update(self._connections[channel])

        # ALL 채널 구독자 (항상 전달)
        if channel != "ALL" and "ALL" in self._connections:
            targets.update(self._connections["ALL"])

        await self._send_to_many(targets, data)

    async def broadcast_all(self, data: dict):
        """모든 연결에 브로드캐스트"""
        targets = set()
        for conns in self._connections.values():
            targets.update(conns)
        await self._send_to_many(targets, data)

    async def send_personal(self, websocket: WebSocket, data: dict):
        """특정 클라이언트에 메시지 전송"""
        try:
            await websocket.send_json(data)
        except Exception:
            logger.debug("[WS] Failed to send personal message")

    @property
    def connection_count(self) -> int:
        """총 연결 수"""
        return sum(len(conns) for conns in self._connections.values())

    @property
    def channels(self) -> List[str]:
        """활성 채널 목록"""
        return list(self._connections.keys())

    async def _send_to_many(self, targets: set, data: dict):
        """여러 클라이언트에 메시지 전송 (실패 시 개별 무시)"""
        dead = []
        message = json.dumps(data, ensure_ascii=False, default=str)

        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        # 끊어진 연결 정리 (dict 복사본으로 안전하게 순회)
        if dead:
            dead_set = set(dead)
            for channel in list(self._connections.keys()):
                conns = self._connections.get(channel)
                if conns is None:
                    continue
                self._connections[channel] = [c for c in conns if c not in dead_set]
                if not self._connections[channel]:
                    del self._connections[channel]


# 싱글톤 인스턴스
manager = ConnectionManager()
