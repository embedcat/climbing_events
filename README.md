# Climbing Events

Сервис для ввода и подсчёта результатов скалолазных соревнований.

## Разработка (Локальный запуск)

Для запуска в режиме разработки (с автоматической перезагрузкой кода):

1. Убедитесь, что у вас установлен Docker и Docker Compose.
2. Запустите контейнеры (переменные окружения для разработки уже прописаны в `docker-compose.yml`):
   ```bash
   docker-compose up --build
   ```
3. Приложение будет доступно по адресу: [http://localhost:8000](http://localhost:8000)

Вместе с приложением поднимается сервис `frontend`: dev-сервер Vite для Vue-экранов (каталог `frontend/`,
порт 5173). Он сам ставит npm-зависимости при первом запуске, а правки в `frontend/src` подхватывает без
перезагрузки страницы. Node на хосте не нужен. Тесты и проверка типов:

```bash
docker-compose exec frontend npm test
docker-compose exec frontend npm run typecheck
```

В проде Vue-экраны собираются стадией `frontend` в `Dockerfile.prod` (вместе с тестами и проверкой типов),
сервис `frontend` и dev-сервер там не нужны.

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
1. Скопируйте конфиг сайта из `nginx.host.conf`, активируйте и проверьте его:
   ```bash
   sudo cp nginx.host.conf /etc/nginx/sites-available/rockevents.ru
   sudo ln -s /etc/nginx/sites-available/rockevents.ru /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```
2. Получите SSL-сертификат:
   ```bash
   sudo certbot --nginx
   ```

### 4. Запуск приложения
Запустите Docker контейнеры:
```bash
docker compose -f docker-compose.prod.yml up -d
```

Создайте суперпользователя:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

---

## Обновление сайта после изменений

```bash
./do_upgrade.sh
```

Скрипт забирает изменения из Git, скачивает новый образ (он собирается на GitHub), перезапускает контейнеры
и удаляет старые образы. Миграции и `collectstatic` выполняются автоматически при старте контейнера (`entrypoint.py`).

## Резервное копирование и восстановление (Бэкапы)

### 1. Создание бэкапа
Скрипт `do_backup.sh` сохраняет в папку `backups/` дамп базы (`backup_<время>.backup`) и архив загруженных файлов
(`media_<время>.tar.gz`), а бэкапы старше `KEEP_DAYS` дней удаляет. Ночной запуск настраивается в cron
(см. ниже), вручную:
```bash
./do_backup.sh
```

### 2. Восстановление из бэкапа
База данных:
```bash
docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --no-owner --no-privileges' < backups/backup_<время>.backup
```
Загруженные файлы (существующие файлы с теми же именами перезапишутся, остальные останутся):
```bash
tar -xzf backups/media_<время>.tar.gz -C /var/www/climbing_events
```

## Периодические задачи (Cron)

Откройте планировщик командой `crontab -e` и добавьте строки:
```cron
# бэкап базы и загруженных файлов — каждую ночь в 03:00
0 3 * * * ~/climbing_events/do_backup.sh > /dev/null 2>&1
# перевод прошедших соревнований в статус "Завершено" (manage.py check_expired) — каждый день в 00:05
5 0 * * * ~/climbing_events/do_check_expired.sh > /dev/null 2>&1
# закрытие регистрации по дате/времени (manage.py check_close_registration) — каждый час
1 * * * * ~/climbing_events/do_check_close_registration.sh > /dev/null 2>&1
```

---

## Тестовый сайт (dev.rockevents.ru)

Новый фронтенд можно смотреть на настоящих данных рядом с боевым сайтом. Тестовый сайт — отдельный набор
контейнеров из ветки репозитория: свой проект Docker (`climbing_events_staging`), порт 8001, своя база и свои
каталоги; боевой `docker-compose.prod.yml` он не трогает. Базу один раз восстанавливают из бэкапа боевого сайта и
дальше она живёт сама: что делают на тестовом сайте, в боевую базу не попадает, а свежие данные боевого сайта сюда
не приходят. Образ собирается на самом сервере; тесты и проверку типов Vue в этой сборке не гоняют
(`RUN_CHECKS=0` в `docker-compose.staging.yml`), поэтому она идёт заметно быстрее боевой.

Что учитывать:
- письма (регистрация, PIN, сброс пароля) уходят настоящие, поэтому на тестовом сайте регистрируйте только свои адреса;
- оплата ведёт на настоящий кошелёк ЮMoney, а уведомление об оплате приходит на боевой сайт, поэтому платить на
  тестовом сайте нельзя;
- счётчик Метрики выключен (`METRIKA_ID=` в `.env.staging`), в поисковую выдачу сайт не попадает (`noindex`);
- крон-задачи (`check_expired`, `check_close_registration`) настраиваются только для боевого сайта.

### Первый запуск

Тестовый сайт живёт в отдельном клоне. Нельзя переключать ветку в боевом каталоге `~/climbing_events`: его
`do_upgrade.sh` делает `git pull` той ветки, что там выбрана.
```bash
git clone -b feat/frontend <адрес репозитория> ~/climbing_events_dev
cd ~/climbing_events_dev
cp .env.staging.example .env.staging   # заполните: SECRET_KEY, пароли базы и почты
bash do_staging_setup.sh               # каталоги, копия медиа, база из свежего бэкапа, сборка и запуск
```
Скрипт берёт самый свежий `~/climbing_events/backups/backup_*.backup` (или путь первым аргументом), копирует афиши
из `/var/www/climbing_events/media` в `/var/www/climbing_events_dev/media`, восстанавливает базу, собирает образ и
запускает `web`. Потом nginx и сертификат (DNS-запись `dev.rockevents.ru` должна указывать на сервер):
```bash
sudo cp nginx.staging.conf /etc/nginx/sites-available/dev.rockevents.ru
sudo ln -s /etc/nginx/sites-available/dev.rockevents.ru /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d dev.rockevents.ru
```

### Обновление

После новых коммитов в ветке:
```bash
cd ~/climbing_events_dev && bash do_staging_upgrade.sh
```
База и медиа при этом остаются как есть.

### Начать заново (свежая копия боевых данных)

```bash
cd ~/climbing_events_dev
docker compose -f docker-compose.staging.yml down -v    # -v удаляет и тестовую базу
sudo rm -rf /var/www/climbing_events_dev/media
bash do_staging_setup.sh
```

---

### Архитектурные заметки:
- Проект использует **Gunicorn** в качестве сервера приложений.
- **Nginx** на хосте работает как Reverse Proxy и раздает статику/медиа.
- Все настройки передаются через файлы `.env` и `.env.prod`.
