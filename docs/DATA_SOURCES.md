# 데이터 소스 가이드

## 개요

본 문서는 공항 위험지수 시스템에서 사용하는 모든 데이터 소스와 수집 방법을 설명합니다.

---

## 국내 데이터 소스

### 1. 기상청 (기상 데이터)

#### API 정보
| 항목 | 내용 |
|------|------|
| 제공처 | 기상청 기상자료개방포털 |
| URL | https://data.kma.go.kr |
| 인증 | API Key (무료 발급) |
| 형식 | JSON, XML |

#### 사용 API
```
1. 항공기상관측(METAR) 조회
   - 엔드포인트: /api/aviation/metar
   - 데이터: 시정, 풍향, 풍속, 기온, 기압, 현재날씨

2. 항공기상예보(TAF) 조회
   - 엔드포인트: /api/aviation/taf
   - 데이터: 6-24시간 예보

3. 공항별 기상특보
   - 엔드포인트: /api/aviation/warning
   - 데이터: 강풍, 태풍, 대설 등 특보
```

#### 수집 주기
- METAR: 매 시간 (정시)
- TAF: 6시간마다
- 특보: 실시간 (발표 시)

#### 샘플 데이터
```json
{
  "airport_code": "RKSI",
  "observed_at": "2024-01-15T09:00:00Z",
  "visibility": 9999,
  "wind_direction": 270,
  "wind_speed": 5,
  "temperature": -3,
  "dewpoint": -8,
  "pressure": 1025,
  "weather": "FEW020"
}
```

---

### 2. 공공데이터포털 (항공 통계)

#### API 정보
| 항목 | 내용 |
|------|------|
| 제공처 | 공공데이터포털 |
| URL | https://data.go.kr |
| 인증 | API Key (무료) |
| 형식 | JSON, XML |

#### 사용 API
```
1. 국내선 여객 운송실적
   - 데이터: 공항별 승객수, 운항횟수

2. 국제선 여객 운송실적
   - 데이터: 노선별 승객수, 출발/도착국

3. 항공기 지연/결항 현황
   - 데이터: 지연율, 결항율, 사유
```

#### 수집 주기
- 일별 통계: 매일 오전 6시
- 월별 통계: 매월 10일

---

### 3. 항공철도사고조사위원회 (ARAIB)

#### 정보
| 항목 | 내용 |
|------|------|
| 제공처 | 항공철도사고조사위원회 |
| URL | https://araib.molit.go.kr |
| 형식 | 웹 크롤링 (PDF 보고서) |

#### 수집 데이터
```
- 항공기 사고
- 항공기 준사고
- 항공안전장애
- 조류충돌 (Bird Strike)
- 활주로 침범 (Runway Incursion)
```

#### 수집 방법
```python
# 크롤링 예시
class ARAIBCollector(BaseCollector):
    BASE_URL = "https://araib.molit.go.kr"

    async def collect(self):
        # 1. 사고 목록 페이지 크롤링
        # 2. 각 사고 상세 페이지 파싱
        # 3. PDF 보고서 다운로드 및 텍스트 추출
        pass
```

#### 수집 주기
- 매일 1회 (새로운 보고서 확인)

---

### 4. 질병관리청 (보건 데이터)

#### API 정보
| 항목 | 내용 |
|------|------|
| 제공처 | 질병관리청 |
| URL | https://kdca.go.kr |
| 형식 | API + 크롤링 |

#### 수집 데이터
```
1. 감염병 발생 현황
   - 코로나19, 원숭이두창, 콜레라 등
   - 지역별 발생 건수

2. 검역 현황
   - 입국자 검역 건수
   - 감염병 의심자 현황

3. 감염병 위기경보
   - 관심 → 주의 → 경계 → 심각
```

#### 수집 주기
- 감염병 현황: 매일 1회
- 위기경보: 실시간 (변경 시)

---

### 5. 외교부 (여행경보)

#### API 정보
| 항목 | 내용 |
|------|------|
| 제공처 | 외교부 해외안전여행 |
| URL | https://www.0404.go.kr |
| 형식 | 웹 크롤링 / RSS |

#### 수집 데이터
```
여행경보 단계:
1단계: 여행유의 (남색)
2단계: 여행자제 (황색)
3단계: 출국권고 (적색)
4단계: 여행금지 (흑색)
```

#### 활용
- 출발/도착 국가의 위험도 평가
- 외부요인 위험지수 산출

---

### 6. 관세청 (밀수 통계)

#### 정보
| 항목 | 내용 |
|------|------|
| 제공처 | 관세청 |
| URL | https://customs.go.kr |
| 형식 | 공개 통계 / 크롤링 |

#### 수집 데이터
```
- 마약류 밀수 적발 현황
- 밀수품 적발 통계
- 공항별 적발 건수
```

#### 수집 주기
- 월별 통계: 매월 (공개 시)

---

## 해외 데이터 소스

### 1. WHO (세계보건기구)

#### API 정보
| 항목 | 내용 |
|------|------|
| URL | https://www.who.int |
| 형식 | API / 크롤링 |

#### 수집 데이터
```
- 국가별 감염병 현황
- 국제 공중보건 비상사태 (PHEIC)
- 여행 권고사항
```

---

### 2. Aviation Safety Network (ASN)

#### 정보
| 항목 | 내용 |
|------|------|
| URL | https://aviation-safety.net |
| 형식 | 웹 크롤링 |

#### 수집 데이터
```
- 전세계 항공 사고 DB
- 사고 유형, 원인, 피해 규모
- 항공사별 사고 이력
```

---

### 3. Global Terrorism Index (GTI)

#### 정보
| 항목 | 내용 |
|------|------|
| 제공처 | Institute for Economics & Peace |
| URL | https://www.visionofhumanity.org |
| 형식 | 연간 보고서 / API |

#### 수집 데이터
```
- 국가별 테러 위험 지수 (0-10)
- 테러 발생 건수
- 테러 유형 분석
```

---

## 데이터 수집기 구현

### 기본 수집기 클래스

```python
# backend/app/collectors/base.py

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
from app.core.database import get_db
from app.models.risk import RawData

class BaseCollector(ABC):
    """데이터 수집기 기본 클래스"""

    name: str = "base"
    source_url: str = ""
    collection_interval: int = 3600  # 초 단위

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.last_collected: Optional[datetime] = None

    @abstractmethod
    async def collect(self) -> List[Dict[str, Any]]:
        """데이터 수집 (구현 필수)"""
        pass

    @abstractmethod
    def transform(self, raw_data: Dict) -> Dict[str, Any]:
        """데이터 변환 (구현 필수)"""
        pass

    async def save(self, data: List[Dict[str, Any]]):
        """수집 데이터 저장"""
        async with get_db() as db:
            for item in data:
                raw = RawData(
                    factor_id=item["factor_id"],
                    airport_id=item.get("airport_id"),
                    collected_at=datetime.utcnow(),
                    value=item["value"],
                    raw_json=item.get("raw_json"),
                    source_url=self.source_url
                )
                db.add(raw)
            await db.commit()

    async def run(self):
        """수집 실행"""
        try:
            raw_data = await self.collect()
            transformed = [self.transform(d) for d in raw_data]
            await self.save(transformed)
            self.last_collected = datetime.utcnow()
            return {"status": "success", "count": len(transformed)}
        except Exception as e:
            return {"status": "error", "message": str(e)}
```

### 기상 수집기 예시

```python
# backend/app/collectors/weather.py

from typing import Any, Dict, List
from app.collectors.base import BaseCollector
from app.config import settings

class WeatherCollector(BaseCollector):
    """기상청 항공기상 수집기"""

    name = "weather"
    source_url = "https://data.kma.go.kr"
    collection_interval = 3600  # 1시간

    # 공항 ICAO 코드 매핑
    AIRPORT_CODES = {
        "ICN": "RKSI",  # 인천
        "GMP": "RKSS",  # 김포
        "PUS": "RKPK",  # 김해
        "CJU": "RKPC",  # 제주
        # ... 추가
    }

    async def collect(self) -> List[Dict[str, Any]]:
        """METAR 데이터 수집"""
        results = []

        for airport_code, icao_code in self.AIRPORT_CODES.items():
            url = f"{settings.KMA_API_URL}/api/aviation/metar"
            params = {
                "serviceKey": settings.KMA_API_KEY,
                "icao": icao_code,
                "dataType": "JSON"
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            data["airport_code"] = airport_code
            results.append(data)

        return results

    def transform(self, raw_data: Dict) -> Dict[str, Any]:
        """METAR 데이터 변환"""
        metar = raw_data.get("response", {}).get("body", {}).get("items", [{}])[0]

        return {
            "airport_code": raw_data["airport_code"],
            "factors": {
                "visibility": self._parse_visibility(metar.get("visibility")),
                "wind_speed": metar.get("windSpeed", 0),
                "wind_gust": metar.get("windGust", 0),
                "temperature": metar.get("temperature"),
                "weather_code": metar.get("weather", ""),
            },
            "raw_json": metar
        }

    def _parse_visibility(self, vis: str) -> int:
        """시정 파싱 (미터 단위)"""
        if vis == "9999" or vis == "CAVOK":
            return 10000
        try:
            return int(vis)
        except:
            return 0
```

---

## 데이터 품질 관리

### 검증 규칙

```python
# backend/app/collectors/validators.py

from pydantic import BaseModel, validator
from typing import Optional

class WeatherDataValidator(BaseModel):
    visibility: int
    wind_speed: float
    temperature: Optional[float]

    @validator("visibility")
    def validate_visibility(cls, v):
        if v < 0 or v > 50000:
            raise ValueError(f"Invalid visibility: {v}")
        return v

    @validator("wind_speed")
    def validate_wind_speed(cls, v):
        if v < 0 or v > 100:
            raise ValueError(f"Invalid wind speed: {v}")
        return v

class IncidentDataValidator(BaseModel):
    severity: int
    fatalities: int
    injuries: int

    @validator("severity")
    def validate_severity(cls, v):
        if v < 1 or v > 5:
            raise ValueError(f"Invalid severity: {v}")
        return v
```

### 결측치 처리

```python
def handle_missing_data(data: Dict, defaults: Dict) -> Dict:
    """결측치 기본값 처리"""
    for key, default_value in defaults.items():
        if key not in data or data[key] is None:
            data[key] = default_value
    return data

# 기상 데이터 기본값
WEATHER_DEFAULTS = {
    "visibility": 10000,
    "wind_speed": 0,
    "wind_gust": 0,
    "precipitation": 0,
}
```

---

## 수집 스케줄

| 수집기 | 주기 | 시간 | 비고 |
|--------|------|------|------|
| WeatherCollector | 매 시간 | :00 | 정시 |
| PassengerCollector | 매일 | 06:00 | |
| IncidentCollector | 매일 | 07:00 | |
| HealthCollector | 매일 | 08:00 | |
| TravelAdvisoryCollector | 6시간 | 00,06,12,18 | |
| NewsCollector | 30분 | :00, :30 | |
| InternationalCollector | 매일 | 09:00 | |

---

## API 키 관리

### 환경변수 설정

```bash
# .env
KMA_API_KEY=your_kma_api_key_here
DATA_GO_KR_API_KEY=your_data_go_kr_key_here
```

### API 키 발급 링크

| 서비스 | 발급 URL |
|--------|----------|
| 기상청 | https://data.kma.go.kr (회원가입 후 API 활용신청) |
| 공공데이터포털 | https://data.go.kr (회원가입 후 API 활용신청) |

---

## 크롤링 주의사항

### robots.txt 준수

```python
import urllib.robotparser

def check_robots_txt(url: str, user_agent: str = "*") -> bool:
    """robots.txt 확인"""
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"{url}/robots.txt")
    rp.read()
    return rp.can_fetch(user_agent, url)
```

### Rate Limiting

```python
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window  # 초
        self.requests = defaultdict(list)

    async def acquire(self, key: str):
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.time_window)

        # 오래된 요청 제거
        self.requests[key] = [t for t in self.requests[key] if t > cutoff]

        if len(self.requests[key]) >= self.max_requests:
            # 대기 필요
            sleep_time = (self.requests[key][0] - cutoff).total_seconds()
            await asyncio.sleep(sleep_time)

        self.requests[key].append(now)
```

---

## 데이터 저장 용량 예측

| 데이터 유형 | 일일 건수 | 건당 크기 | 월간 용량 |
|-------------|----------|----------|----------|
| 기상 (METAR) | 360건 (15공항 × 24시간) | 1KB | ~11MB |
| 승객 통계 | 15건 | 0.5KB | ~0.2MB |
| 사고 이력 | ~5건 | 5KB | ~0.8MB |
| 뉴스/이슈 | ~100건 | 2KB | ~6MB |
| **총합** | | | **~20MB/월** |

연간 예상: ~240MB (원시 데이터)
10년 보존 시: ~2.4GB
