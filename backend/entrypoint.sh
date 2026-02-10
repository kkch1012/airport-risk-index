#!/bin/sh
set -e

# PostgreSQL 연결 대기
if [ "$USE_SQLITE" != "true" ]; then
    echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
    while ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -q 2>/dev/null; do
        sleep 1
    done
    echo "PostgreSQL is ready."

    # Alembic 마이그레이션 실행
    echo "Running Alembic migrations..."
    alembic upgrade head
    echo "Migrations complete."
fi

# 원래 명령 실행
exec "$@"
