"""WebSocket 메시지 스키마"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class WSAirportRisk(BaseModel):
    airport_code: str
    airport_name: str
    total_score: float
    risk_level: str
    categories: Optional[Dict[str, Any]] = None


class WSSummary(BaseModel):
    total_airports: int
    high_risk_count: int
    average_score: float


class WSRiskData(BaseModel):
    airports: List[WSAirportRisk]
    summary: WSSummary


class WSMessage(BaseModel):
    type: str  # risk_update, heartbeat, connected, error
    timestamp: str
    data: Optional[Any] = None
