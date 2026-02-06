"""
WebSocket 엔드포인트

실시간 위험지수 스트리밍.
"""

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()

HEARTBEAT_INTERVAL = 30  # 초


@router.websocket("/risks")
async def ws_all_risks(websocket: WebSocket):
    """전체 위험지수 실시간 스트림"""
    await manager.connect(websocket, channel="ALL")

    # 연결 확인 메시지
    await manager.send_personal(websocket, {
        "type": "connected",
        "timestamp": datetime.now().isoformat(),
        "data": {"channel": "ALL", "message": "Connected to risk updates stream"},
    })

    try:
        while True:
            # heartbeat 또는 클라이언트 메시지 대기
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=HEARTBEAT_INTERVAL,
                )
                # 클라이언트에서 ping 보내면 pong 응답
                if data == "ping":
                    await manager.send_personal(websocket, {
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat(),
                    })
            except asyncio.TimeoutError:
                # 타임아웃 시 서버에서 heartbeat 전송
                await manager.send_personal(websocket, {
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat(),
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel="ALL")
    except Exception:
        manager.disconnect(websocket, channel="ALL")


@router.websocket("/risks/{airport_code}")
async def ws_airport_risks(websocket: WebSocket, airport_code: str):
    """특정 공항 위험지수 실시간 스트림"""
    channel = airport_code.upper()
    await manager.connect(websocket, channel=channel)

    await manager.send_personal(websocket, {
        "type": "connected",
        "timestamp": datetime.now().isoformat(),
        "data": {"channel": channel, "message": f"Connected to {channel} risk updates"},
    })

    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=HEARTBEAT_INTERVAL,
                )
                if data == "ping":
                    await manager.send_personal(websocket, {
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat(),
                    })
            except asyncio.TimeoutError:
                await manager.send_personal(websocket, {
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat(),
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel=channel)
    except Exception:
        manager.disconnect(websocket, channel=channel)
