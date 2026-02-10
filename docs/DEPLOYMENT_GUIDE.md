# 배포 가이드

공항 위험지수 모니터링 시스템의 프로덕션 배포 절차.

---

## 시스템 요구사항

| 항목 | 최소 사양 | 권장 사양 |
|------|----------|----------|
| OS | Ubuntu 22.04 / CentOS 8+ | Ubuntu 22.04 LTS |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB | 50 GB SSD |
| Docker | 24.0+ | 최신 안정 버전 |
| Docker Compose | v2.20+ | 최신 안정 버전 |

## 사전 준비

### 1. API 키 발급

| API | 발급처 | 용도 |
|-----|--------|------|
| 공공데이터포털 | https://data.go.kr | 기상청, 외교부, 질병관리청, 한국공항공사 데이터 |
| 기상청 (KMA) | https://data.kma.go.kr | 기상 관측 데이터 (선택, 공공데이터포털 키로 대체 가능) |

> API 키 없이도 시스템은 동작합니다. 모든 수집기에 mock fallback이 내장되어 있어 실제 API 연결 실패 시 샘플 데이터로 대체됩니다.

### 2. 도메인 / SSL (선택)

프로덕션 환경에서 HTTPS 사용 시 Nginx 리버스 프록시 앞단에 SSL 인증서를 설정하세요. Let's Encrypt 등의 무료 인증서를 권장합니다.

---

## 배포 단계

### Step 1: 소스코드 클론

```bash
git clone <repository-url> airport-risk-index
cd airport-risk-index
```

### Step 2: 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 아래 항목을 설정합니다.

#### 필수 설정 (프로덕션)

```bash
# 환경 모드
ENV=production
DEBUG=false

# 시크릿 키 생성 (반드시 변경)
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# 데이터베이스
DB_PASSWORD=<강력한-비밀번호>

# CORS (프론트엔드 도메인)
CORS_ORIGINS=https://your-domain.com
```

#### 선택 설정

```bash
# 공공데이터 API (미설정 시 mock 데이터 사용)
DATA_GO_KR_API_KEY=<발급받은-키>
KMA_API_KEY=<발급받은-키>

# 이메일 알림 (미설정 시 알림 비활성화)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=<앱-비밀번호>
ALERT_RECIPIENTS=admin@example.com
```

> 시크릿 키 생성 한 줄 명령:
> ```bash
> python3 -c "import secrets; print(secrets.token_urlsafe(32))"
> ```

### Step 3: 프로덕션 Docker Compose 설정

`docker-compose.yml`에서 프로덕션용 변경이 필요합니다.

#### backend 서비스: `--reload` 제거

```yaml
# 개발 모드 (기본값)
command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# 프로덕션 (--reload 제거, 워커 수 추가)
command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### frontend 서비스: production 타겟 사용

```yaml
# 개발 모드 (기본값)
build:
  target: development

# 프로덕션 (Nginx 정적 서빙)
build:
  target: production
```

#### Nginx 리버스 프록시 활성화 (선택)

`docker-compose.yml`에서 주석 처리된 nginx 서비스를 활성화합니다:

```yaml
nginx:
  image: nginx:alpine
  container_name: airport-risk-nginx
  restart: unless-stopped
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    - ./frontend/dist:/usr/share/nginx/html:ro
  ports:
    - "80:80"
    - "443:443"
  depends_on:
    - backend
    - frontend
```

### Step 4: 빌드 및 실행

```bash
# 이미지 빌드
docker compose build

# 백그라운드 실행
docker compose up -d

# 로그 확인 (초기 기동 시)
docker compose logs -f
```

entrypoint.sh가 자동으로 다음을 수행합니다:
1. PostgreSQL 연결 대기 (pg_isready)
2. Alembic 마이그레이션 실행 (`alembic upgrade head`)
3. uvicorn 서버 시작

### Step 5: 초기 관리자 계정 생성

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "username": "admin",
    "password": "StrongPassword123!"
  }'
```

성공 시 응답:
```json
{
  "id": 1,
  "email": "admin@example.com",
  "username": "admin",
  "is_active": true,
  "is_admin": false
}
```

> 관리자 권한(is_admin) 부여는 DB에서 직접 수행:
> ```bash
> docker compose exec db psql -U postgres -d airport_risk \
>   -c "UPDATE users SET is_admin = true WHERE username = 'admin';"
> ```

---

## 배포 검증 체크리스트

배포 후 아래 항목을 순서대로 확인합니다.

```bash
# 1. 컨테이너 상태 확인 (6개 모두 Up)
docker compose ps

# 2. 헬스체크
curl http://localhost:8000/health

# 3. Prometheus 메트릭
curl http://localhost:8000/metrics

# 4. API 응답
curl http://localhost:8000/api/v1/risks/dashboard

# 5. 로그인 테스트
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "StrongPassword123!"}'

# 6. 프론트엔드 접속
curl -I http://localhost:3000

# 7. Celery 워커 상태
docker compose exec celery-worker celery -A app.core.celery_app inspect active

# 8. 데이터 수집 확인 (30분 후)
curl http://localhost:8000/api/v1/risks/dashboard | python3 -m json.tool
```

---

## 업데이트 절차

### 일반 업데이트

```bash
cd airport-risk-index

# 1. 소스 업데이트
git pull origin main

# 2. 이미지 재빌드 + 재시작
docker compose build
docker compose up -d

# 3. Alembic 마이그레이션 자동 실행 (entrypoint.sh)
# 4. 로그 확인
docker compose logs -f backend --tail=50
```

### 롤백

```bash
# 1. 이전 커밋으로 되돌리기
git log --oneline -5          # 롤백 대상 커밋 확인
git checkout <commit-hash>

# 2. 재빌드 + 재시작
docker compose build
docker compose up -d

# 3. DB 마이그레이션 롤백 (필요 시)
docker compose exec backend alembic downgrade -1
```

---

## 서비스 포트 요약

| 서비스 | 컨테이너 이름 | 포트 | 비고 |
|--------|-------------|------|------|
| PostgreSQL | airport-risk-db | 5432 | 프로덕션에서 외부 노출 제거 권장 |
| Redis | airport-risk-redis | 6379 | 프로덕션에서 외부 노출 제거 권장 |
| Backend API | airport-risk-backend | 8000 | FastAPI + uvicorn |
| Frontend | airport-risk-frontend | 3000 (dev) / 80 (prod) | Vite (dev) / Nginx (prod) |
| Celery Worker | airport-risk-celery-worker | - | 백그라운드 태스크 |
| Celery Beat | airport-risk-celery-beat | - | 스케줄러 |
