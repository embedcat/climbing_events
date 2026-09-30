# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Climbing Events (rockevents.ru) — a Django web app for running climbing competitions:
event setup, participant registration, entering climbing results (accents/routes),
live scoring/results, Excel protocols, and paid registration (YooMoney / SBP QR).
UI and error messages are in Russian; locale is `ru-ru` / `Europe/Moscow`.

**Read `docs/PRODUCT.md` before any feature or UX decision** — it records the owner's product concept:
roles, devices (participants ~99% on phones), which scenarios are core vs rare, what is deliberately
out of scope, and the roadmap.

## Commands

### Local development (Docker, primary workflow)

Dev env vars (DEBUG, SECRET_KEY, DATABASE_URL, etc.) are hardcoded into
`docker-compose.yml`, so no `.env` file is needed to run this.

```bash
docker-compose up --build          # app at http://localhost:8000, Postgres on 5432
docker-compose exec web python manage.py <command>
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py createsuperuser
```

### Tests

```bash
docker-compose exec web python manage.py test
docker-compose exec web python manage.py test events.tests.ModelsTestCase.test_event_creation_and_defaults  # single test
```

(Same commands work without Docker via the `.venv` + `uv`-managed environment if one is active.)

### Lint

```bash
flake8 events config   # config in .flake8: max-line-length=120, excludes migrations
isort .
```

### Production

`docker-compose.prod.yml` pulls the prebuilt image `ghcr.io/embedcat/climbing_events:latest`
(built from `Dockerfile.prod` by `.github/workflows/build-and-push.yml` on every push to `master`).
Config comes from `.env.prod` (see `.env.prod.example`). Nginx on the host (`nginx.host.conf`)
reverse-proxies to gunicorn and serves `/static` and `/media` directly.

Both dev and prod images run `entrypoint.py` first: it waits for the DB (parsed from
`DATABASE_URL`), runs `migrate`, runs `collectstatic` only when `DEBUG` is not true, then
`exec`s the container's `CMD`.

Periodic state transitions are cron-driven, not in-process: `manage.py check_expired` and
`manage.py check_close_registration` (see README for the crontab entries) flip `Event.is_expired`
/ registration-closed state.

## Product direction

`docs/PRODUCT.md` is the product source of truth: roles, priorities, agreed UX decisions, roadmap and what
we deliberately don't build. Read it before changing functionality or UI; if a change contradicts it,
discuss first and update the doc afterwards. Clickable mockups of the agreed screens live in
`docs/mockups/` (open directly in a browser). New frontend screens are Vue 3 components mounted into
Django templates and fed only by `/api/`; every new feature gets a `services.py` function and an API
endpoint.

## Architecture

Single Django app `events` inside project `config` — there is no per-domain app split;
all domain logic lives in one app, organized by *layer* instead:

- **`services.py`** (~860 lines) is the actual business-logic layer: event creation,
  participant registration/validation, scoring and results calculation, group/set
  resolution, Excel protocol import/export (via `xl_tools.py`), QR/mock data, platform
  stats. `views.py`, `api_views.py`, and `pay_views.py` are thin and delegate here —
  when changing business rules, this is the file to change, not the views.
- **Dual presentation surface**, both calling into the same `services.py`:
  - `views.py` (~1075 lines) — classic server-rendered Django views + Bootstrap
    templates (`events/templates/`), the main web app.
  - `api_views.py` + `serializers.py` — a separate DRF REST API mounted at `/api/`
    (JWT auth via `djangorestframework-simplejwt`, `DefaultRouter` in `events/urls.py`)
    for external/mobile clients and a possible future SPA frontend — the API is actively developed,
    so new features should get an API endpoint, not only a server-rendered view.
  - Because both surfaces share `services.py`, keep business rules consistent between
    them rather than duplicating logic in a view.
- `pay_views.py` — payment integration; `Event.pay_type` selects **YooMoney** wallet
  or **SBP QR** (generated with `segno`); `NotifyView` handles the payment webhook;
  `Wallet` model holds payout destinations.
- `about_views.py` — static/about pages.
- `exceptions.py` — domain exceptions (`DuplicateParticipantError`,
  `ParticipantTooYoungError`, `ParticipantNotFoundError`) raised from `services.py` and
  caught in views/api views to produce Russian user-facing error messages.

### Domain model (`events/models.py`)

`CustomUser` (custom `AUTH_USER_MODEL`, `django-allauth` email login, `premium_price`
for paid "premium" event features) → `Wallet` → `Event` (owns all scoring/registration
config) → `Route` (a climbing route with grade/points) and `Participant` (a competitor
in an event, carries entered results in `accents`/`french_accents`/`scores` JSON fields)
→ `PromoCode` / `PayDetail` (paid registration flow).

- **Scoring**: `Event.score_type` selects one of 5 strategies (simple sum,
  proportional-to-attempts, grade table, accents count, French system); the actual
  point computation for each lives in `services.py` and reads `Route.score_json` and
  `Participant.accents`/`scores`/`counted_routes`.
- **Groups & sets**: competitions can be split into groups (e.g. age/skill categories)
  and sets (e.g. time slots/heats), stored as `group_index`/`set_index` integers on
  `Participant` and resolved to display names via `services.get_group_list`/
  `get_set_list` against `Event.group_list`/`set_list` (comma-separated strings).

### Cross-cutting

- Settings (`config/settings.py`) are env-driven via `django-environ`; dev values live
  directly in `docker-compose.yml`, prod values in `.env.prod`.
- `whitenoise` serves compressed/manifest static files in production; in `DEBUG` mode
  Django's own static serving + `django-debug-toolbar` (behind `USE_DJDT`) are used
  instead.
- `django-maintenance-mode` can take the whole site down except `/dja/` (admin) via
  `MAINTENANCE_MODE_GET_TEMPLATE_CONTEXT = 'events.services.get_maintenance_context'`.
