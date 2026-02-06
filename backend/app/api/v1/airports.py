"""
공항 관련 API 엔드포인트
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional

from app.schemas.airports import AirportDetail, AirportListResponse, RegionListResponse

router = APIRouter()


# 임시 공항 데이터 (DB 연결 전)
AIRPORTS = [
    {"code": "ICN", "name": "인천국제공항", "region": "수도권", "latitude": 37.4602, "longitude": 126.4407},
    {"code": "GMP", "name": "김포국제공항", "region": "수도권", "latitude": 37.5583, "longitude": 126.7906},
    {"code": "PUS", "name": "김해국제공항", "region": "영남권", "latitude": 35.1796, "longitude": 128.9382},
    {"code": "CJU", "name": "제주국제공항", "region": "제주권", "latitude": 33.5104, "longitude": 126.4914},
    {"code": "TAE", "name": "대구국제공항", "region": "영남권", "latitude": 35.8941, "longitude": 128.6589},
    {"code": "CJJ", "name": "청주국제공항", "region": "충청권", "latitude": 36.7166, "longitude": 127.4991},
    {"code": "KWJ", "name": "광주공항", "region": "호남권", "latitude": 35.1264, "longitude": 126.8089},
    {"code": "RSU", "name": "여수공항", "region": "호남권", "latitude": 34.8423, "longitude": 127.6169},
    {"code": "USN", "name": "울산공항", "region": "영남권", "latitude": 35.5935, "longitude": 129.3518},
    {"code": "KPO", "name": "포항경주공항", "region": "영남권", "latitude": 35.9879, "longitude": 129.4204},
    {"code": "WJU", "name": "원주공항", "region": "강원권", "latitude": 37.4381, "longitude": 127.9601},
    {"code": "YNY", "name": "양양국제공항", "region": "강원권", "latitude": 38.0613, "longitude": 128.6692},
    {"code": "HIN", "name": "사천공항", "region": "영남권", "latitude": 35.0886, "longitude": 128.0703},
    {"code": "KUV", "name": "군산공항", "region": "호남권", "latitude": 35.9038, "longitude": 126.6158},
    {"code": "MWX", "name": "무안국제공항", "region": "호남권", "latitude": 34.9914, "longitude": 126.3828},
]


@router.get("", response_model=AirportListResponse)
async def get_airports(
    region: Optional[str] = None,
):
    """공항 목록 조회"""
    airports = AIRPORTS

    if region:
        airports = [a for a in airports if a["region"] == region]

    return {
        "total": len(airports),
        "airports": airports
    }


@router.get("/{airport_code}", response_model=AirportDetail)
async def get_airport(airport_code: str):
    """특정 공항 조회"""
    airport = next((a for a in AIRPORTS if a["code"] == airport_code.upper()), None)

    if not airport:
        raise HTTPException(status_code=404, detail="공항을 찾을 수 없습니다.")

    return airport


@router.get("/regions/list", response_model=RegionListResponse)
async def get_regions():
    """지역 목록 조회"""
    regions = list(set(a["region"] for a in AIRPORTS))
    return {"regions": sorted(regions)}
