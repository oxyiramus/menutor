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

Для SQLite и PostgreSQL задайте собственный непустой `JWT_SECRET_KEY` в окружении или в `.config/.env`. Если ключ отсутствует, пуст или совпадает с одной из прежних заглушек, backend остановится до запуска API. В примере ниже команда `openssl` создаёт ключ для нового локального стенда. Для повторного запуска используйте сохранённый ключ стенда.

```sh
python3.14 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
mkdir -p data
export DATABASE_URL=sqlite:///data/menutor.db
export JWT_SECRET_KEY="$(openssl rand -hex 32)"
uvicorn backend.api.main:app --reload
```

Для локального PostgreSQL задайте URL с адресом базы, доступным с хоста. Backend и Alembic читают `.config/.env` и используют SQLite по умолчанию, если `DATABASE_URL` отсутствует.

В другом терминале запустите интерфейс.

```sh
cd frontend
npm ci
npm run dev
```

Vite доступен на <http://localhost:5173> и по умолчанию проксирует `/api` на порт 8000. Для другого адреса задайте `API_URL` в окружении процесса Vite.

## Доступ браузера к API с другого origin

Если веб-клиент обращается к API с другого origin, перечислите доверенные origins через запятую в `CORS_ALLOWED_ORIGINS`, например `https://app.example,https://admin.example:8443`. Указывайте схему, хост и порт при необходимости, без пути и завершающего слеша. Backend читает настройку при запуске из `.config/.env`. Значение переменной процесса имеет приоритет, в том числе если оно пустое.

Если список пуст или настройка отсутствует, внешние origins не получают разрешений CORS. Значения с `*` и значение `null` останавливают запуск backend. API не отправляет `Access-Control-Allow-Credentials`. Для интерфейса со штатным прокси Vite или Nginx оставьте список пустым, поскольку запросы браузера к `/api` идут с того же origin. Для защищённых маршрутов сервер по-прежнему проверяет Bearer-токен. CORS управляет доступом браузера к ответам и не заменяет серверную авторизацию.

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

Для регрессии CORS и Bearer-авторизации запустите из корня репозитория с пустым списком разрешённых origins:

```sh
CORS_ALLOWED_ORIGINS='' python -m pytest -q tests/unit/api/test_cors.py tests/integration/test_audit_http.py::test_real_http_register_write_read_calculate_and_error
```

Ожидается `20 passed`. CORS-тесты подставляют свои настройки. Интеграционный тест создаёт временную SQLite-базу, задаёт тестовый JWT-ключ и регистрирует аккаунт. Подготавливать данные вручную не требуется.

Для проверки запуска с JWT-ключом выполните `python -m pytest -q tests/integration/test_jwt_startup.py`. Ожидается `9 passed, 1 skipped`. Для полного прогона задайте `TEST_PERSONAL_CATEGORIES_POSTGRES_URL` с URL отдельной тестовой базы PostgreSQL и правом создавать схемы. Тест сам создаст и удалит временную схему. Ожидается `10 passed`.

Для проверки границ сессии задайте `TEST_PERSONAL_CATEGORIES_POSTGRES_URL` с URL отдельной тестовой БД PostgreSQL. Роли подключения нужно право создавать схемы. Каждый тест создаёт и удаляет временную схему и сам регистрирует два аккаунта. Ожидаемый результат команды — `2 passed, 4 deselected`.

```sh
pytest -q tests/integration/test_request_sessions.py -k postgresql
```

Первый тест удерживает запрос в обработчике и проверяет, что аутентификация и обработчик используют одну сессию, а параллельный запрос получает другую. Второй удерживает импорт сразу после записи первого продукта, дожидается успешного входа другого аккаунта и возобновляет импорт. Некорректная вторая строка приводит к HTTP 422. Независимое соединение с БД подтверждает, что продукт отсутствует как после входа, так и после отката импорта. Число токенов обновления увеличивается только у вошедшего аккаунта.

Проверки завершения сессий, принадлежности объектов и атомарности импорта на SQLite создают данные самостоятельно:

```sh
pytest -q tests/integration/test_request_sessions.py \
  tests/integration/test_api_data_isolation.py \
  tests/integration/test_related_object_isolation.py \
  tests/integration/test_derived_data_isolation.py \
  tests/integration/test_audit_regressions.py \
  tests/integration/test_audit_files.py -k 'not postgresql'
```

```sh
cd frontend
npm ci
npm test
npm run build
```

Из корня можно отдельно запустить набор [поведенческих тестов фронтенда](../tests/frontend/README.md) командой `node tests/frontend/run.mjs` после установки зависимостей. Эти тесты проверяют компоненты и работу с API на уровне клиента. Команда `npm run lint` применяет автоматические исправления.
