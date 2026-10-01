#!/bin/bash
# Одноразовая подготовка тестового сайта (dev.rockevents.ru): каталоги, копия медиа, база из бэкапа боевого сайта,
# сборка образа и запуск. Запускать из тестового клона репозитория (git clone -b feat/frontend … ~/climbing_events_dev):
#   bash do_staging_setup.sh [путь/к/backup_….backup]
# Без аргумента берётся самый свежий бэкап из ~/climbing_events/backups. Дальше тестовая база живёт своей жизнью:
# данные боевого сайта сюда больше не подтягиваются. Начать заново: см. README, раздел про тестовый сайт.
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE="docker compose -f docker-compose.staging.yml"
PROD_DIR="${PROD_DIR:-$HOME/climbing_events}"
PROD_MEDIA="${PROD_MEDIA:-/var/www/climbing_events/media}"
STAGING_DIR=/var/www/climbing_events_dev
BACKUP="${1:-}"

if [ ! -f .env.staging ]; then
    echo "ERROR: .env.staging not found: cp .env.staging.example .env.staging и заполните" >&2
    exit 1
fi

if [ -z "$BACKUP" ]; then
    BACKUP=$(find "$PROD_DIR/backups" -maxdepth 1 -type f -name 'backup_*.backup' -printf '%T@ %p\n' 2>/dev/null \
        | sort -nr | head -n1 | cut -d' ' -f2-)
fi
if [ -z "$BACKUP" ] || [ ! -f "$BACKUP" ]; then
    echo "ERROR: бэкап базы не найден (искал в $PROD_DIR/backups); передайте путь первым аргументом" >&2
    exit 1
fi

if docker volume inspect climbing_events_staging_postgres_data_staging >/dev/null 2>&1; then
    echo "ERROR: тестовая база уже существует, скрипт одноразовый (чтобы начать заново, смотрите README)" >&2
    exit 1
fi

set -x

# Каталоги тестового сайта и разовая копия загруженных афиш
sudo mkdir -p "$STAGING_DIR/static" "$STAGING_DIR/media"
sudo cp -a "$PROD_MEDIA/." "$STAGING_DIR/media/"
sudo chown -R www-data:www-data "$STAGING_DIR"

# База: отдельный контейнер, восстановление из дампа боевой (формат pg_dump -Fc из do_backup.sh)
$COMPOSE up -d db
for _ in $(seq 1 60); do
    if $COMPOSE exec -T db sh -c 'pg_isready -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; then
        break
    fi
    sleep 1
done

# pg_restore на свежей базе может вернуть предупреждения, поэтому исход проверяем по числу событий
set +e
$COMPOSE exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges' < "$BACKUP"
RESTORE_RC=$?
set -e
EVENTS=$($COMPOSE exec -T db sh -c 'psql -tA -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select count(*) from events_event"' | tr -d '[:space:]')
set +x
echo "Событий в тестовой базе: ${EVENTS:-?} (код pg_restore: $RESTORE_RC)"
if [ -z "${EVENTS:-}" ] || [ "$EVENTS" = "0" ]; then
    echo "ERROR: база не восстановилась, смотрите вывод pg_restore выше" >&2
    exit 1
fi

# Образ собирается здесь же: стадия frontend гоняет тесты и сборку Vue, поэтому первый раз это несколько минут
set -x
$COMPOSE build
$COMPOSE up -d web

# entrypoint.py ждёт базу, делает migrate и collectstatic, потом стартует gunicorn
sleep 8
if ! $COMPOSE ps --status running | grep -q web; then
    echo "ERROR: web не запустился, логи: $COMPOSE logs web" >&2
    exit 1
fi
set +x

echo "Готово. Дальше: nginx.staging.conf в /etc/nginx/sites-available/dev.rockevents.ru, certbot --nginx -d dev.rockevents.ru"
