# Climbing Events

Сервис для ввода и подсчёта результатов скалолазных соревнований.

## Разработка (Локальный запуск)

Для запуска в режиме разработки (с автоматической перезагрузкой кода):

1. Убедитесь, что у вас установлен Docker и Docker Compose.
2. Создайте файл `.env` на основе `.env.example`.
3. Запустите контейнеры:
   ```bash
   docker-compose up --build
   ```
4. Приложение будет доступно по адресу: [http://localhost:8000](http://localhost:8000)

---

## Развертывание на сервере (Production)

### 1. Подготовка сервера (Debian/Ubuntu)
Установите необходимые пакеты:
```bash
sudo apt update
sudo apt install docker.io docker-compose nginx certbot python3-certbot-nginx
```

### 2. Настройка проекта
1. Склонируйте репозиторий.
2. Подготовьте файл с переменными окружения:
   ```bash
   cp .env.prod.example .env.prod
   # Обязательно отредактируйте .env.prod: установите DEBUG=False, домены в ALLOWED_HOSTS и CSRF_TRUSTED_ORIGINS
   ```
3. Создайте папки для статики и медиа и дайте права Nginx:
   ```bash
   sudo mkdir -p /var/www/climbing_events/static /var/www/climbing_events/media
   sudo chown -R www-data:www-data /var/www/climbing_events/
   ```

### 3. Настройка Nginx и SSL
1. Создайте конфиг сайта `/etc/nginx/sites-available/rockevents.ru` на основе файла `nginx.host.conf`.
2. Активируйте конфиг и проверьте его:
   ```bash
   cp nginx.host.conf /etc/nginx/sites-available/rockevents.ru
   sudo ln -s /etc/nginx/sites-available/rockevents.ru /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```
3. Получите SSL-сертификат:
   ```bash
   sudo certbot --nginx
   ```

### 4. Запуск приложения
Запустите Docker контейнеры:
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Создайте суперпользователя:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

---

## Обновление сайта после изменений

1. **Заберите изменения** из Git (чтобы обновить конфигурационные файлы):
   ```bash
   git pull
   ```
2. **Скачайте новый образ** из реестра (так как образ собирается на GitHub):
   ```bash
   docker compose -f docker-compose.prod.yml pull
   ```
3. **Перезапустите** контейнеры (Docker Compose автоматически пересоздаст контейнер с новым образом):
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```
4. (Опционально) Удалите старые неиспользуемые образы, чтобы освободить место:
   ```bash
   docker image prune -f
   ```
3. (Опционально) Если вы добавили новые миграции, они применятся автоматически при запуске благодаря `entrypoint.py`. Но вы можете проверить их вручную:
   ```bash
   docker compose -f docker-compose.prod.yml exec web python manage.py showmigrations
   ```
4. Если изменились статические файлы, они также соберутся автоматически, но можно запустить сборку вручную:
   ```bash
   docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --no-input
   ```

## Резервное копирование и восстановление (Бэкапы)

### 1. Создание бэкапа вручную
Чтобы сделать бэкап базы данных продакшена, выполните команду в папке проекта:
```bash
docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backup_$(date +%Y-%m-%d_%H-%M-%S).backup
```

### 2. Восстановление из бэкапа вручную
Чтобы восстановить базу данных из файла бэкапа кастомного формата (`.backup`):
```bash
docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --no-owner --no-privileges' < dump.backup
```

### 3. Автоматические бэкапы по расписанию (Cron)
Для настройки автоматического создания бэкапов на сервере:

1. Создайте в корне проекта файл `do_backup.sh`:
    ```bash
    #!/bin/bash
    # Переходим в папку проекта (важно для cron)
    cd ~/climbing_events

    # Создаем папку для бэкапов, если её нет
    mkdir -p backups

    # Формируем бэкап
    BACKUP_NAME="backup_$(date +%Y-%m-%d_%H-%M-%S).backup"
    docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "backups/$BACKUP_NAME"

    # Удаляем бэкапы старше 14 дней
    find backups/ -type f -name "*.backup" -mtime +14 -delete
    ```
2. Сделайте скрипт исполняемым:
   ```bash
   chmod +x do_backup.sh
   ```
3. Откройте планировщик cron командой `crontab -e` и добавьте строку для запуска скрипта каждую ночь в 03:00:
   ```cron
   0 3 * * * ~/climbing_events/do_backup.sh > /dev/null 2>&1
   ```

## Периодические задачи (Cron)

### 1. Проверка завершённых соревнований
Для автоматической проверки соревнований и перевода их в статус "Завершено" создана консольная команда Django:
```bash
docker compose -f docker-compose.prod.yml exec -T web python manage.py check_expired
```

Чтобы запускать эту проверку автоматически (например, каждый день в 00:05):
1. Откройте планировщик cron на сервере:
   ```bash
   crontab -e
   ```
2. Добавьте в конец файла следующую строку:
   ```cron
   5 0 * * * cd ~/climbing_events && docker compose -f docker-compose.prod.yml exec -T web python manage.py check_expired > /dev/null 2>&1
   ```

### 2. Автоматическое закрытие регистрации
Для автоматической проверки даты/времени закрытия регистрации создана консольная команда:
```bash
docker compose -f docker-compose.prod.yml exec -T web python manage.py check_close_registration
```

Чтобы запускать эту проверку автоматически (например, каждый час):
1. Откройте планировщик cron на сервере (`crontab -e`).
2. Добавьте строку:
   ```cron
   1 * * * * cd ~/climbing_events && docker compose -f docker-compose.prod.yml exec -T web python manage.py check_close_registration > /dev/null 2>&1
   ```

---

### Архитектурные заметки:
- Проект использует **Gunicorn** в качестве сервера приложений.
- **Nginx** на хосте работает как Reverse Proxy и раздает статику/медиа.
- Все настройки передаются через файлы `.env` и `.env.prod`.
