# 운영 매뉴얼

공항 위험지수 모니터링 시스템의 일상 운영, 모니터링, 장애대응 가이드.

---

## 서비스 구성

6개 Docker 컨테이너로 구성됩니다.

```
                      ┌─────────────┐
                      │   Frontend  │ :3000(dev) / :80(prod)
                      │   (Nginx)   │
                      └──────┬──────┘
                             │ /api/* → backend:8000
                             │ /ws/*  → backend:8000
                      ┌──────▼──────┐
                      │   Backend   │ :8000
                      │  (FastAPI)  │
                      └──┬──────┬───┘
                 ┌───────▼┐  ┌─▼───────┐
                 │  DB    │  │  Redis   │
                 │ (PG15) │  │  (v7)   │
                 │ :5432  │  │ :6379   │
                 └────────┘  └─┬───────┘
                         ┌─────▼──────┐
                         │   Celery   │
                         │Worker+Beat │
                         └────────────┘
```

| 컨테이너 | 이미지 | 역할 | 의존 |
|----------|--------|------|------|
| airport-risk-db | postgres:15-alpine | 데이터 저장 | - |
| airport-risk-redis | redis:7-alpine | 캐시, 메시지 브로커, Celery 큐 | - |
| airport-risk-backend | python:3.11-slim | REST API, WebSocket | db, redis |
| airport-risk-celery-worker | python:3.11-slim | 데이터 수집 태스크 실행 | db, redis |
| airport-risk-celery-beat | python:3.11-slim | 태스크 스케줄링 | redis, celery-worker |
| airport-risk-frontend | node:20-alpine / nginx:alpine | 웹 UI | backend |

---

## 일상 운영 명령어

### 시작 / 중지 / 재시작

```bash
# 전체 서비스 시작
docker compose up -d

# 전체 서비스 중지
docker compose down

# 특정 서비스만 재시작
docker compose restart backend
docker compose restart celery-worker celery-beat

# 전체 재시작
docker compose restart
```

### 로그 확인

```bash
# 전체 로그 (최근 100줄)
docker compose logs --tail=100

# 특정 서비스 실시간 로그
docker compose logs -f backend
docker compose logs -f celery-worker

# 에러만 필터링 (structlog JSON 모드)
docker compose logs backend 2>&1 | grep '"level":"error"'
```

### 상태 확인

```bash
# 컨테이너 상태
docker compose ps

# 리소스 사용량
docker stats --no-stream

# 디스크 사용량
docker system df
```

### 스케일링

```bash
# Celery 워커 수 조정 (CPU 바운드 작업 대응)
docker compose up -d --scale celery-worker=3
```

---

## 모니터링

### 헬스체크

```bash
# API 서버 상태
curl http://localhost:8000/health
# 응답: {"status":"healthy","version":"1.0.0"}
```

Docker 자체 헬스체크가 30초 간격으로 자동 실행됩니다 (`curl -f http://localhost:8000/health`).

### Prometheus 메트릭

```bash
# 메트릭 엔드포인트
curl http://localhost:8000/metrics
```

주요 메트릭:

| 메트릭 | 타입 | 설명 |
|--------|------|------|
| `http_request_duration_seconds` | Histogram | 요청별 응답 시간 (method, path, status 라벨) |
| `http_request_duration_seconds_count` | Counter | 총 요청 수 |
| `http_request_duration_seconds_sum` | Counter | 총 처리 시간 |

Prometheus 스크래핑 설정 예시 (`prometheus.yml`):
```yaml
scrape_configs:
  - job_name: 'airport-risk'
    scrape_interval: 15s
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /metrics
```

### structlog 로그 형식

프로덕션(`ENV=production`)에서는 JSON 형식으로 출력됩니다:
```json
{"event":"request","method":"GET","path":"/api/v1/risks/dashboard","status":200,"duration_ms":45.3,"client":"192.168.1.1","timestamp":"2026-02-10T09:00:00+09:00"}
```

> `/health`와 `/metrics` 경로는 접근 로그에서 자동 제외됩니다 (노이즈 방지).

---

## Celery 태스크 모니터링

### Beat 스케줄 (5개 주기 태스크)

| 태스크 | 주기 | 만료 | 설명 |
|--------|------|------|------|
| collect_and_calculate_all_risks | 30분 | 25분 | 전체 공항 위험지수 수집+산출 |
| collect_weather_data | 1시간 | 55분 | 기상청 기상 데이터 수집 |
| collect_advisory_data | 6시간 | 5시간 | 여행경보/보건/운항정보 수집 |
| send_daily_report | 매일 09:00 KST | 1시간 | 일간 위험지수 리포트 이메일 |
| recalculate_weights | 매주 월 03:00 KST | 1시간 | 상관분석 기반 가중치 재산출 |

### 태스크 상태 확인

```bash
# 현재 실행 중인 태스크
docker compose exec celery-worker celery -A app.core.celery_app inspect active

# 등록된 태스크 목록
docker compose exec celery-worker celery -A app.core.celery_app inspect registered

# 예약된 태스크
docker compose exec celery-worker celery -A app.core.celery_app inspect scheduled

# 워커 상태
docker compose exec celery-worker celery -A app.core.celery_app inspect ping
```

---

## 데이터 수집기 상태

5종 수집기가 운영되며, 모두 API 실패 시 mock 데이터로 자동 전환됩니다.

| 수집기 | API 소스 | 환경변수 | 주기 | fallback |
|--------|---------|---------|------|----------|
| Weather | 기상청 KMA | `DATA_GO_KR_API_KEY` | 1시간 | mock 기상 데이터 |
| Travel Advisory | 외교부 MOFA | `DATA_GO_KR_API_KEY` | 6시간 | mock 여행경보 |
| Health Risk | 질병관리청 KDCA | `DATA_GO_KR_API_KEY` | 6시간 | mock 보건 데이터 |
| Flight Status | 한국공항공사 | `DATA_GO_KR_API_KEY` | 30분 | mock 운항 정보 |
| Aviation Safety | ARAIB | 웹 스크래핑 | 24시간 | mock 사고 데이터 |

수집 상태는 Celery 워커 로그에서 확인 가능합니다:
```bash
docker compose logs celery-worker --tail=50 | grep "collect"
```

---

## 사용자 관리

### 계정 생성

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "username": "newuser", "password": "Password123!"}'
```

### 로그인 (JWT 토큰 발급)

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "Password123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo $TOKEN
```

### 내 정보 조회

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### 관리자 권한 부여

```bash
docker compose exec db psql -U postgres -d airport_risk \
  -c "UPDATE users SET is_admin = true WHERE username = 'admin';"
```

### 사용자 목록 조회 (DB 직접)

```bash
docker compose exec db psql -U postgres -d airport_risk \
  -c "SELECT id, email, username, is_active, is_admin, created_at FROM users;"
```

---

## 백업 / 복원

### PostgreSQL 백업

```bash
# 전체 백업
docker compose exec db pg_dump -U postgres airport_risk > backup_$(date +%Y%m%d_%H%M%S).sql

# 압축 백업
docker compose exec db pg_dump -U postgres -Fc airport_risk > backup_$(date +%Y%m%d).dump
```

### PostgreSQL 복원

```bash
# SQL 파일에서 복원
docker compose exec -T db psql -U postgres airport_risk < backup_20260210.sql

# 덤프 파일에서 복원
docker compose exec -T db pg_restore -U postgres -d airport_risk --clean backup_20260210.dump
```

### Redis 백업

```bash
# 스냅샷 생성
docker compose exec redis redis-cli BGSAVE

# 스냅샷 파일 복사
docker cp airport-risk-redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d).rdb
```

### Redis 복원

```bash
# Redis 중지 → 파일 교체 → 재시작
docker compose stop redis
docker cp ./redis_backup_20260210.rdb airport-risk-redis:/data/dump.rdb
docker compose start redis
```

### 자동 백업 (crontab 예시)

```bash
# 매일 새벽 2시 DB 백업 (7일 보관)
0 2 * * * cd /path/to/airport-risk-index && docker compose exec -T db pg_dump -U postgres airport_risk | gzip > /backup/db_$(date +\%Y\%m\%d).sql.gz && find /backup -name "db_*.sql.gz" -mtime +7 -delete
```

---

## 장애대응

### DB 연결 실패

**증상**: Backend 로그에 `connection refused` 또는 `timeout`

```bash
# 1. DB 컨테이너 상태 확인
docker compose ps db
docker compose logs db --tail=20

# 2. DB 연결 테스트
docker compose exec db pg_isready -U postgres

# 3. DB 재시작
docker compose restart db

# 4. Backend 재시작 (DB 복구 후)
docker compose restart backend celery-worker
```

### Celery 워커 중단

**증상**: 데이터 수집이 멈춤, 대시보드 데이터 갱신 안 됨

```bash
# 1. 워커 상태 확인
docker compose ps celery-worker celery-beat

# 2. 워커 로그 확인
docker compose logs celery-worker --tail=50

# 3. 워커 재시작
docker compose restart celery-worker celery-beat

# 4. 태스크 큐 확인 (Redis)
docker compose exec redis redis-cli LLEN celery
```

### API 키 만료 / 할당량 초과

**증상**: 수집기 로그에 401/403 에러, 대시보드에 mock 데이터 표시

```bash
# 1. 수집기 로그에서 에러 확인
docker compose logs celery-worker 2>&1 | grep -i "error\|401\|403"

# 2. API 키 갱신 (.env 수정 후)
vi .env  # API 키 업데이트

# 3. 변경 반영
docker compose up -d celery-worker celery-beat
```

> mock fallback이 동작하므로 서비스 자체는 중단되지 않습니다. 다만 실제 데이터 대신 샘플 데이터가 표시됩니다.

### 디스크 부족

**증상**: DB 쓰기 실패, Docker 빌드 실패

```bash
# 1. 디스크 사용량 확인
df -h
docker system df

# 2. Docker 정리 (미사용 이미지/볼륨/캐시)
docker system prune -f
docker image prune -a -f

# 3. 오래된 로그 정리
docker compose logs --no-log-prefix backend 2>/dev/null | wc -l
truncate -s 0 $(docker inspect --format='{{.LogPath}}' airport-risk-backend)
```

### Backend 응답 느림

**증상**: API 응답 시간 > 5초

```bash
# 1. Prometheus 메트릭에서 느린 엔드포인트 확인
curl -s http://localhost:8000/metrics | grep "http_request_duration"

# 2. 리소스 사용량 확인
docker stats --no-stream

# 3. DB 연결 풀 확인
docker compose exec db psql -U postgres -d airport_risk \
  -c "SELECT count(*) FROM pg_stat_activity;"

# 4. 워커 수 증가 (docker-compose.yml 수정)
# command: uvicorn ... --workers 4 → --workers 8
docker compose up -d backend
```

---

## 보안 체크리스트

### 정기 점검 (월 1회)

- [ ] JWT_SECRET_KEY 가 기본값이 아닌지 확인
- [ ] DB_PASSWORD 가 강력한 비밀번호인지 확인
- [ ] SECRET_KEY 가 기본값이 아닌지 확인
- [ ] `.env` 파일 권한이 `600` (소유자만 읽기/쓰기)인지 확인
  ```bash
  chmod 600 .env
  ls -la .env
  ```
- [ ] 프로덕션에서 DEBUG=false 확인
- [ ] PostgreSQL/Redis 포트가 외부에 노출되지 않는지 확인

### 시크릿 교체

```bash
# 1. 새 시크릿 생성
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. .env 파일 업데이트
vi .env  # JWT_SECRET_KEY, SECRET_KEY 교체

# 3. 서비스 재시작
docker compose up -d backend celery-worker
```

> JWT_SECRET_KEY 교체 시 기존 발급된 토큰은 모두 무효화됩니다. 사용자 재로그인이 필요합니다.

### 의존성 업데이트

```bash
# Backend 취약점 확인
docker compose exec backend pip audit

# Frontend 취약점 확인
docker compose exec frontend npm audit

# 업데이트 적용
docker compose build --no-cache
docker compose up -d
```
