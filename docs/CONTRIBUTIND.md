# Разработка и развёртывание Menutor

Команды выполняются из корня репозитория, кроме блоков с явным переходом в `frontend`. Схема приложения описана в [архитектуре](architecture.md).

## Контейнеры

Нужны Docker и Docker Compose. При первой настройке скопируйте `.config/.env.example` в `.config/.env`. Задайте `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` и согласованный с ними URL вида `postgresql+psycopg2://пользователь:пароль@postgres:5432/база` в `DATABASE_URL`. Укажите собственный `JWT_SECRET_KEY`, например сгенерированный командой `openssl rand -hex 32`. При необходимости задайте `ACCESS_TOKEN_MINUTES`, по умолчанию 30.

### Разработка

Для Vite внутри контейнера установите `API_URL=http://backend:8000` в `.config/.env`.

```sh
docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml logs -f backend
```

Интерфейс доступен на <http://localhost:5174>, API на <http://localhost:8000/docs>. Исходники монтируются в контейнеры и используются для горячей перезагрузки. PostgreSQL хранит данные в `.docker/volumes/db`.

### Продакшен

```sh
export VERSION="$(cat VERSION)"
docker compose -f docker-compose.yml build
docker compose -f docker-compose.yml up -d
docker compose -f docker-compose.yml ps
```

`VERSION` используется Compose в тегах образов. Интерфейс доступен на хосте по адресу <http://localhost:8080>, а проверка backend — по <http://localhost:8000/api/ping>. Nginx обслуживает сборку Vue и проксирует `/api/` в backend. PostgreSQL хранится в именованном томе `postgres_data`. Запускайте один из двух наборов контейнеров за раз, поскольку они используют одинаковые имена и порты backend и БД.

В репозитории есть [workflow развёртывания](../.github/workflows/deploy.yml) для self-hosted runner при push в `main`. Он обновляет версию скриптом на сервере, скачивает образы, запускает миграции и поднимает контейнеры.

## Локальный запуск

Нужны Python 3.14+ и Node.js 20.19.x либо 22.12+. Контейнерная сборка фронтенда использует Node.js 25.8.

```sh
python3.14 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
mkdir -p data
export DATABASE_URL=sqlite:///data/menutor.db
uvicorn backend.api.main:app --reload
```

Для локального PostgreSQL задайте URL с адресом базы, доступным с хоста, и `JWT_SECRET_KEY`. Backend и Alembic читают `.config/.env` и используют SQLite по умолчанию, если `DATABASE_URL` отсутствует.

В другом терминале запустите интерфейс.

```sh
cd frontend
npm ci
npm run dev
```

Vite доступен на <http://localhost:5173> и по умолчанию проксирует `/api` на порт 8000. Для другого адреса задайте `API_URL` в окружении процесса Vite.

## Миграции

Backend при запуске применяет Alembic до актуальной ревизии и затем заполняет справочник единиц измерения. Ошибка миграции останавливает запуск. Для диагностики и ручного применения используйте команды ниже с тем же адресом БД, что и у приложения.

```sh
alembic current
alembic heads
alembic history
alembic upgrade head
```

В Compose для ручной диагностики используйте `docker compose -f docker-compose.dev.yml run --rm backend alembic current`. Для продакшена укажите `docker-compose.yml` и экспортируйте `VERSION` как при запуске.

Перед обновлением рабочей базы сделайте резервную копию. Если таблицы существуют, а Alembic не показывает ревизию, сверяйте фактическую схему с историей перед запуском миграций. Для изменения схемы подготовьте ревизию, проверьте сгенерированные операции и порядок обновления на отдельной базе.

## Тесты и проверки

```sh
pytest tests/unit -q
pytest tests/integration -q
pytest tests/ -q
```

Тесты PostgreSQL в `tests/integration/test_audit_postgresql.py` используют Testcontainers и требуют доступный Docker. Многие остальные тесты работают с SQLite.

```sh
cd frontend
npm ci
npm test
npm run build
```

Из корня можно отдельно запустить набор [поведенческих тестов фронтенда](../tests/frontend/README.md) командой `node tests/frontend/run.mjs` после установки зависимостей. Эти тесты проверяют компоненты и работу с API на уровне клиента. Команда `npm run lint` применяет автоматические исправления.
