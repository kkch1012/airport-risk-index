# 시스템 아키텍처

## 개요

본 문서는 공항 위험지수 모니터링 시스템의 상세 아키텍처를 설명합니다.

---

## 전체 시스템 구성도

```
                                    ┌─────────────────┐
                                    │   사용자 (Web)   │
                                    └────────┬────────┘
                                             │
                                             ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                              Nginx (Reverse Proxy)                          │
│                         - SSL 종료, 로드밸런싱, 정적파일                     │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
        ┌───────────────────┐             ┌───────────────────┐
        │    Frontend       │             │    Backend API    │
        │  (React App)      │             │    (FastAPI)      │
        │  :3000            │             │    :8000          │
        └───────────────────┘             └─────────┬─────────┘
                                                    │
                    ┌───────────────────────────────┼───────────────────────────────┐
                    │                               │                               │
                    ▼                               ▼                               ▼
        ┌───────────────────┐           ┌───────────────────┐           ┌───────────────────┐
        │   PostgreSQL      │           │      Redis        │           │   Celery Workers  │
        │   :5432           │           │      :6379        │           │                   │
        │                   │           │                   │           │ - 데이터 수집     │
        │ - 메인 데이터     │           │ - 캐시            │           │ - 분석 작업       │
        │ - 시계열 데이터   │           │ - 세션            │           │ - 알림 발송       │
        │ - 분석 결과       │           │ - 실시간 pub/sub  │           │                   │
        └───────────────────┘           └───────────────────┘           └───────────────────┘
```

---

## 컴포넌트 상세

### 1. Frontend (React Application)

```
frontend/
├── src/
│   ├── components/           # 재사용 컴포넌트
│   │   ├── common/          # 공통 UI
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── RiskGauge.tsx      # 위험도 게이지
│   │   │   ├── RiskBadge.tsx      # 위험등급 뱃지
│   │   │   └── LoadingSpinner.tsx
│   │   │
│   │   ├── dashboard/       # 대시보드 컴포넌트
│   │   │   ├── MainDashboard.tsx
│   │   │   ├── RiskOverviewCard.tsx
│   │   │   ├── AirportMap.tsx     # 지도 (Kakao/Naver Map)
│   │   │   ├── AirportRankingTable.tsx
│   │   │   └── AlertPanel.tsx
│   │   │
│   │   ├── airport/         # 공항 상세
│   │   │   ├── AirportHeader.tsx
│   │   │   ├── RiskBreakdownChart.tsx
│   │   │   ├── CategoryDetailCard.tsx
│   │   │   └── HistoryLineChart.tsx
│   │   │
│   │   └── analytics/       # 분석
│   │       ├── CorrelationHeatmap.tsx
│   │       ├── TrendChart.tsx
│   │       └── ComparisonRadar.tsx
│   │
│   ├── pages/               # 페이지 레벨
│   │   ├── DashboardPage.tsx
│   │   ├── AirportDetailPage.tsx
│   │   ├── AnalyticsPage.tsx
│   │   └── SettingsPage.tsx
│   │
│   ├── hooks/               # 커스텀 훅
│   │   ├── useRiskData.ts        # 위험 데이터 fetch
│   │   ├── useWebSocket.ts       # 실시간 연결
│   │   └── useAlerts.ts          # 알림 관리
│   │
│   ├── services/            # API 통신
│   │   ├── api.ts                # axios 인스턴스
│   │   ├── riskApi.ts            # 위험 API
│   │   └── airportApi.ts         # 공항 API
│   │
│   ├── stores/              # 상태 관리 (Zustand)
│   │   ├── useAirportStore.ts
│   │   └── useAlertStore.ts
│   │
│   └── types/               # TypeScript 타입
│       ├── airport.ts
│       ├── risk.ts
│       └── api.ts
```

### 2. Backend (FastAPI Application)

```
backend/
├── app/
│   ├── main.py                    # 앱 진입점
│   ├── config.py                  # 환경설정 (pydantic-settings)
│   │
│   ├── api/
│   │   ├── deps.py               # 의존성 (DB 세션, 인증 등)
│   │   └── v1/
│   │       ├── router.py         # 라우터 통합
│   │       ├── airports.py       # 공항 CRUD
│   │       ├── risks.py          # 위험지수 조회
│   │       ├── analytics.py      # 분석 API
│   │       ├── alerts.py         # 알림 관리
│   │       └── websocket.py      # 실시간 연결
│   │
│   ├── models/                   # SQLAlchemy ORM
│   │   ├── base.py
│   │   ├── airport.py
│   │   ├── risk.py
│   │   ├── incident.py
│   │   └── alert.py
│   │
│   ├── schemas/                  # Pydantic 스키마
│   │   ├── airport.py
│   │   ├── risk.py
│   │   └── analytics.py
│   │
│   ├── services/                 # 비즈니스 로직
│   │   ├── risk_calculator.py    # 위험지수 계산
│   │   ├── alert_service.py      # 알림 처리
│   │   └── email_service.py      # 이메일 발송
│   │
│   ├── collectors/               # 데이터 수집기
│   │   ├── base.py              # 추상 수집기
│   │   ├── weather.py           # 기상청
│   │   ├── aviation.py          # 항공 데이터
│   │   ├── health.py            # 질병관리청
│   │   ├── security.py          # 보안 정보
│   │   └── international.py     # 해외 데이터
│   │
│   ├── ml/                       # ML 모듈
│   │   ├── correlation.py       # 상관분석
│   │   ├── weight_calculator.py # 가중치 산출
│   │   └── predictor.py         # 예측 모델
│   │
│   └── core/
│       ├── database.py          # DB 연결
│       ├── security.py          # JWT, 암호화
│       └── celery_app.py        # Celery 설정
│
├── tasks/                        # Celery 태스크
│   ├── collection.py            # 데이터 수집
│   ├── analysis.py              # 분석 작업
│   └── notification.py          # 알림 발송
│
└── alembic/                      # DB 마이그레이션
    └── versions/
```

---

## 데이터 흐름

### 1. 실시간 데이터 수집 흐름

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ External    │     │ Celery      │     │ PostgreSQL  │     │ Redis       │
│ Data Source │────▶│ Worker      │────▶│ (저장)      │────▶│ (캐시)      │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
                    ┌─────────────┐     ┌─────────────┐            │
                    │ Frontend    │◀────│ WebSocket   │◀───────────┘
                    │ (실시간)    │     │ Server      │
                    └─────────────┘     └─────────────┘
```

### 2. 위험지수 계산 흐름

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Raw Data    │     │ Normalizer  │     │ Weight      │     │ Risk Score  │
│ (수집 데이터)│────▶│ (정규화)    │────▶│ Calculator  │────▶│ (위험지수)  │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
                    ┌─────────────┐     ┌─────────────┐            │
                    │ Email       │◀────│ Alert       │◀───────────┘
                    │ (긴급알림)  │     │ Service     │   (임계치 초과 시)
                    └─────────────┘     └─────────────┘
```

---

## 데이터베이스 설계

### ERD (Entity Relationship Diagram)

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    airports     │       │ risk_categories │       │  risk_factors   │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ code            │       │ code            │       │ category_id(FK) │
│ name            │       │ name            │       │ code            │
│ region          │       │ base_weight     │       │ name            │
│ latitude        │       └────────┬────────┘       │ weight          │
│ longitude       │                │                └────────┬────────┘
│ runway_count    │                │                         │
│ annual_capacity │                │                         │
└────────┬────────┘                │                         │
         │                         │                         │
         │         ┌───────────────┴───────────────┐         │
         │         │                               │         │
         ▼         ▼                               ▼         ▼
┌─────────────────────────┐              ┌─────────────────────────┐
│    daily_risk_scores    │              │       raw_data          │
├─────────────────────────┤              ├─────────────────────────┤
│ id (PK)                 │              │ id (PK)                 │
│ airport_id (FK)         │              │ factor_id (FK)          │
│ date                    │              │ airport_id (FK)         │
│ aviation_score          │              │ collected_at            │
│ security_score          │              │ value                   │
│ health_score            │              │ raw_json                │
│ operational_score       │              └─────────────────────────┘
│ weather_score           │
│ external_score          │              ┌─────────────────────────┐
│ total_score             │              │       incidents         │
│ risk_level              │              ├─────────────────────────┤
│ score_breakdown (JSONB) │              │ id (PK)                 │
└─────────────────────────┘              │ airport_id (FK)         │
                                         │ category_id (FK)        │
┌─────────────────────────┐              │ incident_date           │
│    country_risks        │              │ incident_type           │
├─────────────────────────┤              │ severity                │
│ id (PK)                 │              │ fatalities              │
│ country_code            │              │ injuries                │
│ date                    │              └─────────────────────────┘
│ travel_advisory_level   │
│ terrorism_index         │              ┌─────────────────────────┐
│ health_risk_level       │              │    weight_history       │
│ active_diseases (JSONB) │              ├─────────────────────────┤
└─────────────────────────┘              │ id (PK)                 │
                                         │ factor_id (FK)          │
                                         │ calculated_at           │
                                         │ correlation_coefficient │
                                         │ weight                  │
                                         └─────────────────────────┘
```

### 파티셔닝 전략

대용량 시계열 데이터 처리를 위해 파티셔닝 적용:

```sql
-- raw_data 테이블 월별 파티셔닝
CREATE TABLE raw_data (
    id BIGSERIAL,
    factor_id INT,
    airport_id INT,
    collected_at TIMESTAMP NOT NULL,
    value DECIMAL(15, 4),
    raw_json JSONB,
    PRIMARY KEY (id, collected_at)
) PARTITION BY RANGE (collected_at);

-- 월별 파티션 생성 예시
CREATE TABLE raw_data_2024_01 PARTITION OF raw_data
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

---

## 실시간 처리

### WebSocket 연결

```python
# 클라이언트 연결 관리
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, airport_code: str = "ALL"):
        await websocket.accept()
        if airport_code not in self.active_connections:
            self.active_connections[airport_code] = []
        self.active_connections[airport_code].append(websocket)

    async def broadcast_risk_update(self, airport_code: str, data: dict):
        # 특정 공항 구독자에게 전송
        if airport_code in self.active_connections:
            for connection in self.active_connections[airport_code]:
                await connection.send_json(data)

        # 전체 구독자에게도 전송
        if "ALL" in self.active_connections:
            for connection in self.active_connections["ALL"]:
                await connection.send_json(data)
```

### Redis Pub/Sub

```python
# 워커에서 위험지수 계산 후 발행
async def publish_risk_update(redis: Redis, airport_code: str, risk_data: dict):
    channel = f"risk_updates:{airport_code}"
    await redis.publish(channel, json.dumps(risk_data))

# API 서버에서 구독하여 WebSocket으로 전달
async def subscribe_risk_updates(redis: Redis, manager: ConnectionManager):
    pubsub = redis.pubsub()
    await pubsub.psubscribe("risk_updates:*")

    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            airport_code = message["channel"].split(":")[1]
            data = json.loads(message["data"])
            await manager.broadcast_risk_update(airport_code, data)
```

---

## 스케줄링

### Celery Beat 스케줄

```python
# celery_app.py
from celery.schedules import crontab

app.conf.beat_schedule = {
    # 기상 데이터: 매 시간
    'collect-weather-hourly': {
        'task': 'tasks.collection.collect_weather',
        'schedule': crontab(minute=0),
    },

    # 승객 통계: 매일 오전 6시
    'collect-passenger-daily': {
        'task': 'tasks.collection.collect_passenger_stats',
        'schedule': crontab(hour=6, minute=0),
    },

    # 위험지수 계산: 매 시간
    'calculate-risk-hourly': {
        'task': 'tasks.analysis.calculate_all_risks',
        'schedule': crontab(minute=5),
    },

    # 상관분석 재계산: 매주 월요일 새벽
    'recalculate-weights-weekly': {
        'task': 'tasks.analysis.recalculate_weights',
        'schedule': crontab(day_of_week=1, hour=3, minute=0),
    },
}
```

---

## 보안

### 인증 흐름 (현재: JWT, 추후: SSO)

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Client  │────▶│  Login  │────▶│  JWT    │
│         │     │  API    │     │  발급   │
└─────────┘     └─────────┘     └────┬────┘
                                     │
                                     ▼
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Client  │────▶│  API    │────▶│  JWT    │
│ + JWT   │     │  요청   │     │  검증   │
└─────────┘     └─────────┘     └─────────┘

[추후 SSO 연동 시]
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Client  │────▶│  SSO    │────▶│  Token  │
│         │     │  Server │     │  교환   │
└─────────┘     └─────────┘     └─────────┘
```

---

## 모니터링

### 로깅 구조

```python
# 구조화된 로깅
import structlog

logger = structlog.get_logger()

logger.info(
    "risk_calculated",
    airport_code="ICN",
    total_score=42.3,
    risk_level="MODERATE",
    duration_ms=150
)
```

### 헬스체크 엔드포인트

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "components": {
            "database": check_db_connection(),
            "redis": check_redis_connection(),
            "celery": check_celery_workers(),
        },
        "version": settings.VERSION,
        "timestamp": datetime.utcnow().isoformat()
    }
```

---

## 확장성 고려사항

### 수평 확장

```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  API Server 1 │    │  API Server 2 │    │  API Server 3 │
└───────────────┘    └───────────────┘    └───────────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             ▼
                    ┌─────────────────┐
                    │  Redis Cluster  │
                    └─────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  Celery       │    │  Celery       │    │  Celery       │
│  Worker 1     │    │  Worker 2     │    │  Worker 3     │
└───────────────┘    └───────────────┘    └───────────────┘
```

### 데이터 보존 정책

| 데이터 유형 | 보존 기간 | 저장소 |
|-------------|----------|--------|
| 원시 데이터 (raw_data) | 무기한 | PostgreSQL (파티셔닝) |
| 일별 위험지수 | 무기한 | PostgreSQL |
| 분석 결과 | 무기한 | PostgreSQL |
| 캐시 데이터 | 1시간 | Redis |
| 로그 | 90일 | File/ELK |
