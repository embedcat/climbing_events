#!/bin/bash

mkdir -p backups

BACKUP_NAME="backup_\$(date +%Y-%m-%d_%H-%M-%S).backup"
docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U "\$POSTGRES_USER" -d "\$POSTGRES_DB" -Fc' > "backups/\$BACKUP_NAME"

find backups/ -type f -name "*.backup" -mtime +14 -delete
