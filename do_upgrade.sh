#!/bin/bash
set -euo pipefail
set -x

cd "$(dirname "$0")"

if [ ! -f .env.prod ]; then
    echo "ERROR: .env.prod not found, aborting" >&2
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: working tree is dirty, aborting to avoid a bad merge" >&2
    exit 1
fi

git pull --ff-only
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# give the container time to run entrypoint.py (db wait + migrate) and start gunicorn
sleep 5
if ! docker compose -f docker-compose.prod.yml ps --status running | grep -q web; then
    echo "ERROR: web service is not running after upgrade, check logs with:" >&2
    echo "  docker compose -f docker-compose.prod.yml logs web" >&2
    exit 1
fi

docker image prune -f
