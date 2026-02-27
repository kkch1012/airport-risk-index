#!/bin/sh
set -e

# PostgreSQL 연결 대기 (최대 60초 타임아웃)
if [ "$USE_SQLITE" != "true" ]; then
    echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
    PGWAIT=0
    while ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -q 2>/dev/null; do
        PGWAIT=$((PGWAIT + 1))
        if [ "$PGWAIT" -ge 60 ]; then
            echo "ERROR: PostgreSQL did not become ready within 60 seconds"
            exit 1
        fi
        sleep 1
    done
    echo "PostgreSQL is ready."

    # Alembic 마이그레이션은 backend(uvicorn)에서만 실행 (Celery worker/beat 제외)
    case "$1" in
        uvicorn*)
            echo "Running Alembic migrations..."
            alembic upgrade head
            echo "Migrations complete."
            ;;
        *)
            echo "Skipping migrations (non-API process)."
            ;;
    esac
fi

# 원래 명령 실행
exec "$@"
