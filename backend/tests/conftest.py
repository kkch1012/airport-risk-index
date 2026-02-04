"""
pytest 설정 및 공통 fixture
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """FastAPI 테스트 클라이언트"""
    return TestClient(app)


@pytest.fixture
def airport_codes():
    """테스트용 공항 코드 목록"""
    return ["ICN", "GMP", "PUS", "CJU", "TAE"]
