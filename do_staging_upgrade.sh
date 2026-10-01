#!/bin/bash
# Обновление тестового сайта после новых коммитов в ветке: забирает код, пересобирает образ на сервере, перезапускает web.
# База и медиа не трогаются. Запускать из тестового клона: bash do_staging_upgrade.sh
set -euo pipefail
set -x

cd "$(dirname "$0")"

COMPOSE="docker compose -f docker-compose.staging.yml"

if [ ! -f .env.staging ]; then
    echo "ERROR: .env.staging not found, aborting" >&2
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: working tree is dirty, aborting to avoid a bad merge" >&2
    exit 1
fi

git pull --ff-only
$COMPOSE build
$COMPOSE up -d web

# give the container time to run entrypoint.py (db wait + migrate + collectstatic) and start gunicorn
sleep 8
if ! $COMPOSE ps --status running | grep -q web; then
    echo "ERROR: web service is not running after upgrade, check logs with:" >&2
    echo "  $COMPOSE logs web" >&2
    exit 1
fi

docker image prune -f
