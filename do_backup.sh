#!/bin/bash

# Сколько дней хранить бэкапы
KEEP_DAYS=6

# Переходим в папку проекта (важно для cron)
cd ~/climbing_events

mkdir -p backups

TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_NAME="backup_$TIMESTAMP.backup"
docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "backups/$BACKUP_NAME"

# Загруженные файлы (постеры); папка смонтирована в web в docker-compose.prod.yml
tar -czf "backups/media_$TIMESTAMP.tar.gz" -C /var/www/climbing_events media

find backups/ -type f -name "*.backup" -mtime +$KEEP_DAYS -delete
find backups/ -type f -name "media_*.tar.gz" -mtime +$KEEP_DAYS -delete
