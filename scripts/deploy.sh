#!/usr/bin/env bash
set -euo pipefail

# ===========================================
# 공항 위험지수 시스템 - 프로덕션 배포 스크립트
# ===========================================

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"
ENV_EXAMPLE=".env.production.example"
HEALTH_URL="http://localhost/health"
MAX_WAIT=60

cd "$(dirname "$0")/.."

echo "============================================"
echo "  Airport Risk Index - Production Deploy"
echo "============================================"

# 1) .env.production 존재 확인
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo "[ERROR] $ENV_FILE 파일이 없습니다."
    echo ""
    echo "  cp $ENV_EXAMPLE $ENV_FILE"
    echo "  vim $ENV_FILE   # CHANGE_ME 값을 모두 변경하세요"
    echo ""
    exit 1
fi

# 2) 시크릿 기본값 체크
check_secret() {
    local key="$1"
    local val
    val=$(grep "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d ' ')
    if [ "$val" = "CHANGE_ME" ] || [ -z "$val" ]; then
        return 1
    fi
    return 0
}

SECRETS_OK=true
for key in SECRET_KEY JWT_SECRET_KEY DB_PASSWORD GF_ADMIN_PASSWORD; do
    if ! check_secret "$key"; then
        echo "[ERROR] $ENV_FILE 에서 ${key}가 설정되지 않았거나 기본값(CHANGE_ME)입니다."
        SECRETS_OK=false
    fi
done

if [ "$SECRETS_OK" = false ]; then
    echo ""
    echo "보안을 위해 배포를 중단합니다. $ENV_FILE 의 시크릿 값을 변경하세요."
    exit 1
fi

echo ""
echo "[1/4] 이미지 빌드..."
docker compose -f "$COMPOSE_FILE" build

echo ""
echo "[2/4] 서비스 기동..."
docker compose -f "$COMPOSE_FILE" up -d

echo ""
echo "[3/4] 헬스체크 대기 (최대 ${MAX_WAIT}초)..."
elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        echo "  Backend healthy! (${elapsed}초)"
        break
    fi
    sleep 2
    elapsed=$((elapsed + 2))
    printf "  %d초 경과...\r" "$elapsed"
done

if [ $elapsed -ge $MAX_WAIT ]; then
    echo ""
    echo "[WARN] ${MAX_WAIT}초 내에 헬스체크 응답 없음. 로그를 확인하세요:"
    echo "  docker compose -f $COMPOSE_FILE logs backend"
fi

echo ""
echo "[4/4] 서비스 상태:"
docker compose -f "$COMPOSE_FILE" ps

echo ""
echo "============================================"
echo "  배포 완료!"
echo ""
echo "  Frontend:   http://localhost"
echo "  Backend:    http://localhost/api/v1"
echo "  Prometheus: http://localhost:9090"
echo "  Grafana:    http://localhost:3001"
echo "============================================"
