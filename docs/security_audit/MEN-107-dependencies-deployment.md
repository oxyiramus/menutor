# MEN-112 · Зависимости и поставка Menutor

Независимый результат D для этапа E. Дата проверки 25.11.2026, Europe/Amsterdam. Код проверен на `d3322adaebb1a06561e2cd3177adde40c5a561df` (ниже `d3322ada`). Рабочая база `8908b1860a36d72b742608ee73faa44fcc62a008` отличается добавлением [границ MEN-109](MEN-107-scope.md). `git rev-list --left-right --count origin/dev...d3322ada` дал `0 27`. Принятых ADR в дереве не найдено. Выводы прежних аудитов не использовались. Рабочие серверы, данные, окружение и реальные `.env` в области проверки отсутствовали.

## MEN-107-D-T01 · Инвентаризация и advisories

| Источник | Что установлено | Граница доказательства |
| --- | --- | --- |
| Python runtime | `pyproject.toml:4–16`: Python ≥3.14, Alembic ≥1.18, bcrypt ≥4.0, FastAPI ≥0.115, psycopg2-binary ≥2.9, PyJWT ≥2.8, python-dotenv ≥1.2, SQLAlchemy ≥2.0, python-multipart ≥0.0.20, ReportLab ≥4.0, Uvicorn ≥0.34 | Диапазоны без lock. Чистое разрешение не дошло до расчёта дерева. |
| Python dev/test | `pyproject.toml:18–29`: black, httpx, isort, mypy, pylint, pytest, pytest-cov, pypdf и testcontainers с PostgreSQL extra. Устанавливаются отдельно в `.docker/dev/test-backend.dockerfile:7–11`. | В системной среде Python 3.14.4 замечены pip 25.3, setuptools 78.1.1, SQLAlchemy 2.0.45, psycopg2 2.9.11. Это частичный снимок инструментов хоста. |
| npm frontend | lock v3, 503 узла без корня, 401 с `dev: true`, 102 остальных, 95 optional (пересекаются с обоими наборами). Все 503 с integrity. Прямые runtime: axios 1.13.6, pinia 3.0.4, sortablejs 1.15.7, vue 3.5.30, vue-router 5.0.3. Из dev/build: Vite 7.3.1 и happy-dom 20.8.4. | Записи lock включают платформенные варианты. Prod build использует `npm ci` и переносит только `dist`. Dev использует `npm install`. Установленное дерево и содержимое итогового bundle не получены. |
| Образы | `python:3.14-slim` — backend runtime/dev/test и proxy-клиенты; `node:25.8-alpine` — dev и prod build, npm 11.12.0 в обоих Dockerfile; `nginx:alpine` — frontend runtime и proxy-стенд; `postgres:18.3` — обе конфигурации Compose. Prod образы приложения в GHCR имеют тег `$VERSION`, dev — теги `frontend-dev` и `backend-dev`. | Ни один FROM или Compose image не фиксирует digest. Registry и daemon недоступны. Платформа, digest, состав системных пакетов и production SBOM неизвестны. |

Инструменты: Git 2.53.0, Python 3.14.4, pip 25.3, Node 24.14.0, npm 11.9.0, Docker CLI 26.1.4, Compose 2.27.1. Команды для снимка выполнялись в одноразовом каталоге `git archive d3322ada | tar -x -C "$audit_dir"`. Инвентарь npm полностью воспроизводим из lock:

```sh
node -e 'const {packages}=require("./frontend/package-lock.json"); for(const [p,m] of Object.entries(packages)) if(p) console.log(p,m.version,!!m.dev,!!m.optional,m.integrity)'
```

| Команда из снимка, где не указано иное | Ожидание и фактический результат |
| --- | --- |
| `python3 -m venv .audit-venv` | Изолированный pip. Код 1, ensurepip недоступен. Созданный интерпретатор использован как цель внешнего pip. |
| `PIP_CONFIG_FILE=/dev/null timeout 20s python3 -m pip --python .audit-venv/bin/python install --dry-run --report pip-report.json --disable-pip-version-check --no-cache-dir --retries 0 --timeout 5 --index-url https://pypi.org/simple "$extra"`, с `extra=.` и `extra='.[dev]'` | Полностью разрешённый runtime и runtime+dev без установки. Оба 1, EPERM соединения с прокси при загрузке setuptools для изолированной сборки. |
| `npm ci --offline --ignore-scripts --no-audit --cache ../npm-cache` из frontend | Дерево из lock в выделенном кэше. Код 1, ENOTCACHED, первый сообщённый пакет yocto-queue 0.1.0. |
| `timeout 25s npm audit --json --fetch-retries=0 --fetch-timeout=8000 --cache ../npm-cache` из frontend | Результаты bulk advisory по lock. Код 1, EPERM соединения. Результатов сканирования нет. |
| `docker version --format '{{.Server.Version}}'` | Версия daemon. Код 1, EPERM сокета. |
| `curl -q -sS -o /dev/null --max-time 8 -w '%{http_code}\\n' URL` к `https://registry-1.docker.io/v2/`, `https://ghcr.io/v2/`, `https://api.osv.dev/` | HTTP-ответ, для registry допустим 401. Для всех код 7, HTTP 000, EPERM сокета. |
| `command -v pip-audit osv-scanner trivy grype gitleaks detect-secrets nginx` (проверка каждого инструмента) | Все отсутствуют в PATH. |

Сетевой поиск через браузерный инструмент позволил выборочно проверить данные первичных advisories на 25.11.2026. Полного покрытия npm, Python или образов нет. Для повторения получить чистые `pip install --report` и `pip freeze --all` отдельно для runtime/dev, `npm ci` и `npm ls --all --json`, затем `pip-audit --local` в каждом окружении и `npm audit --json` с разбором зависимостей build/test/runtime. На отдельном daemon получить platform manifest и `RepoDigests` каждого образа, собрать образы из снимка, зафиксировать SBOM и дату базы Trivy/Grype, сопоставить запущенные сервисы с этими digest. Сопоставление Python-диапазонов с CVE без разрешённых версий не подтверждает уязвимую установку.

### MEN-107-D-001 · Vite dev-сервер с затронутой версией

**High, подтверждено по lock, доступ к стенду условный.** `frontend/package-lock.json:6393–6396`, `.docker/dev/frontend.dockerfile:5–10`, `docker-compose.dev.yml:3–17`, `frontend/vite.config.ts:19–26`. Vite 7.3.1 входит в оба диапазона ниже. Dev слушает все интерфейсы внутри контейнера, Compose публикует loopback и монтирует frontend. Обращение к dev-серверу предполагает доступ с хоста, из смежной сети контейнеров либо через отдельную публикацию. Для WebSocket advisory дополнительно нужен доступ к WebSocket, который в конфигурации Vite явно не отключён. Последствия по advisories — чтение доступных процессу файлов и исполнение кода в dev-контейнере соответственно. Production Dockerfile копирует статический bundle в Nginx, Vite dev-сервера в указанной production-цепочке нет. Доказательство T01. Обновить Vite до проверенного исправленного релиза и подтвердить версию по lock и фактической установке, а экспозицию — по сетевой политике изолированного dev-стенда.

- 06.04.2026, affected 7.0.0–7.3.1, fix 7.3.2. [GHSA-p9ff-h696-f583](https://github.com/vitejs/vite/security/advisories/GHSA-p9ff-h696-f583)
- 10.11.2026, affected 7.0.0–7.3.7, fix 7.3.8. [GHSA-p4f5-76q4-ffq7](https://github.com/vitejs/vite/security/advisories/GHSA-p4f5-76q4-ffq7)

### MEN-107-D-002 · Axios в браузерном runtime

**Medium, версия подтверждена по lock, достижимость условная.** `frontend/package-lock.json:3172–3175`, `frontend/src/api/client.ts:39`, `frontend/src/api/auth.ts:11`. Для GHSA-pf86-5x62-jrwf Axios 1.13.6 попадает в диапазон ≤1.15.0, исправление 1.15.1. Уязвимость требует отдельного источника prototype pollution в том же JS-контексте. Возможна подмена обработки ответа, наличие первичного источника в Menutor не установлено. GHSA-fvcv-3m26-pcqx (CVE-2026-40175) затрагивает 1.13.6, исправление в ветке 1.x — 1.15.0. Облачная цепочка этого advisory требует Node HTTP adapter и отдельного источника загрязнения прототипа. Клиентские экземпляры используют относительные API URL, production API на Python и серверного исполнения этих вызовов в штатной цепочке не выявлено. Доказательство T01. Обновить по свежему аудиту полного дерева и проверить login/refresh и типовые API-вызовы после сборки.

- 24.04.2026. [GHSA-pf86-5x62-jrwf](https://github.com/axios/axios/security/advisories/GHSA-pf86-5x62-jrwf)
- 09.04.2026. [GHSA-fvcv-3m26-pcqx](https://github.com/axios/axios/security/advisories/GHSA-fvcv-3m26-pcqx)

### MEN-107-D-003 · Happy DOM в тестах

**Low для штатной цепочки, версия подтверждена по lock.** `frontend/package-lock.json:4377–4380`, `frontend/vite.config.ts:32–36`, `tests/frontend/vitest.config.mjs:11`. Зафиксирована 20.8.4. При обработке недоверенного HTML или ESM в тестовом процессе возможны исходящие запросы и исполнение кода с правами тестового раннера. Текущие точки подключения — тесты. Обработка внешнего пользовательского HTML/ESM через Happy DOM в production не выявлена. Доказательство T01. Обновить до релиза с обоими исправлениями, подтвердить версии всех тестовых окружений и запустить штатные тесты с ограниченным egress.

- 12.10.2026, affected ≤20.14.6, fix 21.0.0. [GHSA-c8p4-j97h-3vg8](https://github.com/capricorn86/happy-dom/security/advisories/GHSA-c8p4-j97h-3vg8)
- 20.10.2026, affected 17.0.0–21.0.3, fix 21.0.4, неполное исправление CVE-2026-33943. [GHSA-834v-8h66-3h79](https://github.com/capricorn86/happy-dom/security/advisories/GHSA-834v-8h66-3h79)

## MEN-107-D-T02 · Секреты и история

`git rev-parse --is-shallow-repository` → false, `git rev-list --count d3322ada` → 423, `git rev-list --all --count` → 440. Проверены все коммиты, достижимые от локальных `refs/heads/*`, `refs/remotes/origin/*`, `refs/tags/*` и HEAD на момент проверки, включая снимок аудита. Для повторения запишите `git for-each-ref --format='%(refname) %(objectname)'`. Не исследованы reflog, недостижимые/удалённые объекты и удалённые refs, отсутствующие локально. Предыдущие отчёты из `docs/security_audit/` и `docs/review/` исключены на этапе отбора путей. `git log --all --format= --name-only` с этими исключениями и фильтром по `.env`, `.pem`, `.key`, secrets/credentials и proxy-key/proxy-trust нашёл только `.config/.env.example`.

`python3 "$audit_dir/scan.py"` из корня (скрипт ниже) → 0. Ожидались только счётчики и пути. Просканированы 2543 уникальных Git-блоба, 0 совпадений по формату, 116 блобов по эвристике имён. Кандидаты включают env-шаблоны, тесты, документацию и присваивания в коде. Шаблон на целевом SHA содержит заполненные примеры БД и пустые JWT/GitHub поля. В истории есть прежние известные JWT-заглушки, значения скрыты. `git log -G` по двум литералам из текущего denylist на целевом SHA даёт `a38cb61` и `6d8b21f`. Действующий секрет не подтверждён. Проверка ограничена выбранными формами и ручной оценкой контекста, не покрывает произвольно закодированные секреты и полный перечень провайдеров.

`git check-ignore --no-index .env .config/.env .config/proxy-trust.conf tests/proxy/.certs.abc/key.pem` → 0, все четыре исключаются Git. Синтетические пути, реальные файлы не открывались. `.gitignore:10–15` исключает env и proxy key, `.dockerignore:1–3` исключает proxy trust и тестовые сертификаты. Git и Docker применяют разные правила.

### MEN-107-D-004 · Передача env всем сервисам и широкий build context

**Medium, подтверждено по шаблонам.** `docker-compose.yml:3–20,26–37,49–63`, `docker-compose.dev.yml:3–27,41–55`, `.dockerignore:1–3`, `.docker/prod/frontend.dockerfile:9–10`. Во всех сервисах один env-файл, включая Nginx и PostgreSQL. Если туда внесены JWT-ключ, пароль БД или токен автоматизации, значения доступны ненужным контейнерам и пользователям с правом читать их Docker-конфигурацию. Корневой build context допускает рабочий env и исходные метаданные checkout при их наличии. Prod COPY не включает корневой env в финальные слои; широкий COPY frontend может включить локальные вложенные файлы в build stage. Передача чувствительного контекста зависит от состава checkout и builder. Доказательства T02/T03. Разделить конфигурацию по службам и сузить контекст. Повторная проверка с синтетическими маркерами должна подтвердить отсутствие маркеров у посторонних сервисов и в контексте, слоях и артефактах сборки.

### MEN-107-D-005 · Переменные сборки и происхождение образов

**Medium, подтверждено по коду.** `.docker/prod/backend.dockerfile:1–16`, `.docker/prod/frontend.dockerfile:1–15`, `docker-compose.yml:3–9,26–32,49–50`, `.config/git-hooks/pre-push:3–10`, `.github/workflows/deploy.yml:3–23`. Изменяемые теги базы и приложения, свободное разрешение pip/apt, исполнение npm lifecycle и локальная сборка/публикация через hook позволяют получить разные артефакты для одного SHA. Self-hosted deploy выполняет скрипт из каталога хоста, содержимое скрипта вне отслеживаемого дерева. В workflow не указаны проверка происхождения или подписи и concurrency. При подмене тега или контроле builder/runner вредоносный артефакт может быть запущен с доступом к служебным данным. Доказательства T01/T03. Фиксировать проверенные digest и зависимости, выпускать артефакт из проверенного SHA, проверять provenance перед деплоем. Повторно сверить ожидаемый commit и digest для каждой службы и протестировать отклонение неизвестного артефакта в отдельной среде.

Контроль T02 для D-004 на снимке, без чтения env:

```sh
git show d3322ada:.dockerignore | python3 -c 'import sys; rules=set(sys.stdin.read().splitlines()); assert rules.intersection({".config/.env",".config","**/.env",".env"}), "tracked Docker ignore rules omit env entries"'
```

Ожидалось явное исключение env в списке правил. Получены `AssertionError` и код 1. Проверка подтверждает отсутствие перечисленных правил по статическому списку. Отправка контекста builder не проверялась.

## MEN-107-D-T03 · Контейнеры, запуск, CI и конфигурация

- Production backend переключается на непривилегированного пользователя; процесс слушает интерфейсы контейнера. Dev backend также понижает права. Dev frontend и Nginx Dockerfile не задают свой USER, фактическая учётная запись и сброс прав зависят от базового образа. В обоих Compose отсутствуют явные read-only root filesystem, `cap_drop`, `security_opt` и лимиты ресурсов. Также отсутствуют privileged и монтирование Docker socket. Не проверено по runtime. См. все Dockerfile и оба Compose.
- Prod: общий bridge, frontend опубликован на loopback 8080, Postgres на loopback 5432, backend без host mapping. Dev: loopback 5174, 8000, 5432, writable bind исходников и DB-каталога; prod использует именованный DB-том. Доступ соседей по bridge и локальных процессов зависит от daemon/host firewall. Compose `container_name`, подсети и порты требуют изоляции даже при другом имени проекта.
- JWT: `backend/composition/_infrastructure.py:85–115` требует непустой ключ и отбрасывает старые заглушки, но не измеряет длину или случайность. HS256 с фиксированным алгоритмом, срок по умолчанию 30 минут и opaque refresh с хешированием показаны в `backend/infrastructure/auth/jwt_token_service.py:12–38`. Для PostgreSQL env-шаблон даёт пример URL, SQLite fallback задан в ApplicationDatabase и Alembic. Реальные секреты и параметры TLS к БД неизвестны.
- SQLAlchemy создаёт engine без явного echo (`backend/infrastructure/database/connection.py:14–38`). В auth-валидации тело/ввод исключаются из ответа (`backend/api/routers/auth.py:31–44`); обработчик импорта пишет обезличенную строку (`backend/api/routers/import_export.py:79–83`). Общий обработчик RepositoryError сериализует строку исключения (`backend/api/main.py:157–161`), конфигурацию логирования Nginx и Uvicorn в реальном развёртывании установить нельзя. В отслеживаемом workflow нет выгрузки артефактов или явного вывода env. Host-скрипт, журналы runner и registry вне scope. Hooks читают env как shell-код и выполняют локальные операции (`.config/git-hooks/pre-commit:3–14`, `post-commit:5–20`, `pre-push:3–10`), поэтому важно происхождение файла и каталог запуска.
- Workflow останавливает стек перед pull, затем вызывает миграцию и запускает сервисы. Сбой pull/миграции может оставить простой. Startup повторно запускает миграции и seed, с блокировкой процесса в `backend/infrastructure/database/connection.py:41–47`, блокировкой схемы PostgreSQL и SQLite транзакцией в `backend/infrastructure/database/migrations/env.py:57–100`. Идемпотентность, конкуренция при нескольких backend workers и rollback динамически не проверялись.
- `VERSION=audit docker compose config --quiet` и `docker compose -f docker-compose.dev.yml config --quiet` → оба 0. В снимке созданы пустые синтетические `.config/.env` и `.config/proxy-trust.conf`; ожидалась только проверка разбора. Вывод конфигурации с реальными env исключён. Контейнеры не запускались.

### MEN-107-D-006 · Шаблон хостового входа обслуживает HTTP

**Medium, подтверждено для шаблона, фактический TLS неизвестен.** `.docker/prod/host-nginx.conf.example:1–19` включает 80 и 443 в одном server и отправляет оба потока к приложению без HTTPS redirect. Ни в этом файле, ни во внутреннем `.docker/prod/nginx.conf:33–60` нет явных HSTS, CSP, anti-framing и `X-Content-Type-Options`. Если развернуть шаблон буквально и клиент обратится по HTTP, credentials или bearer могут передаваться открытым текстом при доступе наблюдателя к каналу. Другие security headers зависят от общего Nginx-конфига и внешнего edge. Доказательства T03/T04. Разделить HTTP redirect и TLS, определить security headers с учётом SPA и действующих доменов. На отдельном стенде проверить переадресацию, TLS и итоговые заголовки для успешных ответов, ошибок и статических ресурсов.

## MEN-107-D-T04 · Proxy, ограничения API и CORS

- Хостовый Nginx перезаписывает IP и схему, очищает Forwarded/XFF и подставляет ключ из отдельного include. Внутренний Nginx допускает forwarded-метаданные по сочетанию адреса шлюза и ключа, выводит схему из белого списка, иначе берёт исходного TCP-пира и свою схему. При отправке в Uvicorn пересоздаёт XFF, очищает Forwarded и удаляет ключ. Prod Uvicorn получает одно доверенное значение `172.29.103.3`; в Dockerfile доверенный список изначально пуст. Источники: `.docker/prod/host-nginx.conf.example:9–18`, `.docker/prod/nginx.conf:1–17,36–37,48–54`, `docker-compose.yml:11–15,33–37,69–79`, `.docker/prod/backend.dockerfile:25–27`.
- Для login и register заданы отдельные shared zones по доверенному клиентскому IP, 5 запросов в минуту каждая, `burst=10 nodelay`, отказ 429. Зоны общие для workers одного Nginx, общего состояния между репликами в шаблоне нет. Сопоставление зависит от URI, квоты не привязаны к аккаунту. Статический тест проверяет директивы, не определяет фактическое поведение нормализации URI, смены workers, NAT, подмены метаданных или нескольких экземпляров. `.docker/prod/nginx.conf:19–46`, `backend/api/routers/auth.py:49–88`.
- На обоих Nginx 2 MiB на тело запроса. Бэкенд по умолчанию читает до 1 MiB + 1 байт из уже разобранного UploadFile, возвращает 413 сверх лимита; отдельно задано 1000 записей. Настройка большего лимита файла требует согласованного транспортного лимита с multipart overhead. Handler ограничивает чтение файла, а сетевое ограничение применяется раньше только при прохождении proxy. `.docker/prod/host-nginx.conf.example:9–10`, `.docker/prod/nginx.conf:42–46`, `backend/import_limits.py:7–19`, `backend/api/routers/import_export.py:60–83`.
- CORS требует явный список origins, отклоняет wildcard и null, по умолчанию список пуст, credentialed CORS выключен. Заголовки/методы разрешены для согласованных origins. Это ограничение браузера; same-origin UI использует относительные URL. Внешний CORS и поведение preflight не проверены. `backend/api/main.py:56–87`, `frontend/src/api/client.ts:39`.
- Nginx проксирует `/api/` и обслуживает SPA для прочих путей. При прямой доступности backend его маршруты и стандартная API-документация FastAPI доступны на иной сетевой границе. Маршруты backend не реализуют эти ingress-квоты самостоятельно.

### MEN-107-D-007 · Квоты и лимит тела привязаны к Nginx

**Medium при доступе к backend со смежного узла, условная достижимость.** `docker-compose.yml:26–47,49–79`, `.docker/prod/backend.dockerfile:25–27`, `.docker/prod/nginx.conf:42–55`, `backend/api/routers/auth.py:49–88`, `backend/api/routers/import_export.py:60–76`. Ingress-контроли существуют в Nginx. Соседняя служба или иной клиент с сетевой достижимостью backend может обратиться к тому же приложению без ingress-квот и ограничения полного multipart-тела. Это ослабляет защиту от подбора, массовой регистрации и нагрузки на parser/диск при наличии такого сетевого пути. Шаблон не публикует Uvicorn на хост, внешняя достижимость не установлена. Доказательства T03/T04. Ограничить доступ к backend доверенным ingress, проверить политику доступности для каждого соседнего сегмента, провести ограниченную проверку отказа выше согласованных границ.

### Результаты проверок proxy

| Команда | Ожидание и наблюдение |
| --- | --- |
| `python3 tests/proxy/check_rate_config.py` | Два теста директив, код 0, `Ran 2 tests`, `OK`. |
| `sh -n tests/proxy/run.sh` | Синтаксис shell, код 0. |
| `python3 tests/proxy/check_uvicorn.py` | Два in-process теста Uvicorn и Compose на временной конфигурации. Код 1, отсутствует uvicorn до запуска сценария. |
| `python3 -m pytest -q tests/proxy/test_import_config.py` | Два статических случая проверки 2 MiB, код 1, отсутствует pytest. Директивы сверены вручную в обоих шаблонах. |
| `sh tests/proxy/run.sh` | Не запущен, доступ к Docker daemon отклонён. |

Перед решением о запуске изучены `run.sh:3–42`, `compose.yml:1–56`, `rate-nginx.conf` и сценарии. Стенд использует уникальный project, специально сгенерированные однодневный сертификат и ключ, подменный ASGI без БД, read-only mounts, cleanup своего проекта. Однако host-network edge/host-client, фиксированные порты 18080/18081/18443 и подсеть `172.29.103.0/24` требуют выделенного Linux-хоста или VM. Для повторения проверить свободные порты и сеть именно там, использовать снимок, отдельный daemon и ограничить прогон по времени. Проверить целостность доверенных метаданных и независимость квот, смену двух workers, восстановление квоты и отсутствие запроса к backend при 429. Подменный ASGI не проверяет реальный multipart import. Его повторить отдельно с синтетическим аккаунтом/БД, ограниченным числом нормальных запросов вокруг границ 1 MiB файла и 2 MiB тела и таймаутами. Для многорепличной конфигурации результат учитывать отдельно.

## Вопросы отдельной проверки production

1. Какие commit, platform и digest запущены для всех трёх сервисов, какой SBOM и на какую дату просканированы пакеты OS, Python и frontend bundle?
2. Кто управляет self-hosted runner, host-скриптом и правом записи тега в GHCR? Как доказывается происхождение образа, как выполняются rollback, backup/restore и миграции при нескольких процессах?
3. Где хранятся JWT, пароль БД и proxy key, каким службам они доступны, как устроена ротация и кто видит контейнерные метаданные, логи, build cache и registry?
4. Какие порты доступны снаружи, с хоста и из каждого bridge-сегмента? Какие реальные адреса видят edge и frontend? Есть ли CDN, дополнительные прокси/реплики или правила доверия к заголовкам?
5. Перенаправляется ли HTTP до обработки запроса приложением? Какие TLS, HSTS и другие security headers действуют после всех переходов, какие фактические origins разрешены и где доступна API-документация?
6. Где применяются фактические лимиты тела и квоты, согласованы ли они с пределами импорта, сколько workers и реплик и какие правила действуют для прямого backend?
7. Включено ли маскирование данных в журналах, какие сроки хранения у логов, дампов и CI-артефактов? Достаточны ли права запуска, лимиты ресурсов и изоляция сетей при компрометации одной службы?

## Воспроизводимость эвристики T02

```python
import collections
import re
import subprocess

def git(*args):
    return subprocess.check_output(["git", *args])

patterns = {
    "format": rb"(?:-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|gh[pousr]_[a-zA-Z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|(?:AKIA|ASIA)[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{12,}|AIza[A-Za-z0-9_-]{35}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})",
    "literal": rb"""(?im)^[ \t]*(?:export )?["']?(?:JWT_SECRET_KEY|POSTGRES_PASSWORD|DATABASE_URL|GITHUB_TOKEN|API_KEY|SECRET_KEY|PASSWORD|ACCESS_TOKEN|PROXY_KEY)["']?\s*[:=]\s*["']?[^\s"'$\x60#]+""",
}
paths = collections.defaultdict(set)
for rev in git("rev-list", "--all", "d3322ada").decode().splitlines():
    for row in git("ls-tree", "-rz", rev).split(b"\0"):
        if not row:
            continue
        metadata, path = row.split(b"\t", 1)
        _, kind, oid = metadata.split()
        if kind == b"blob" and not path.startswith((b"docs/security_audit/", b"docs/review/")):
            paths[oid].add(path)
totals = collections.Counter()
candidates = collections.defaultdict(set)
with subprocess.Popen(["git", "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE) as pipe:
    for oid, names in paths.items():
        pipe.stdin.write(oid + b"\n")
        pipe.stdin.flush()
        size = int(pipe.stdout.readline().split()[-1])
        data = pipe.stdout.read(size)
        assert pipe.stdout.read(1) == b"\n"
        for label, rx in patterns.items():
            if re.search(rx, data):
                totals[label] += 1
                candidates[label].update(names)
    pipe.stdin.close()
    assert pipe.wait() == 0
print(len(paths), dict(totals))
for label, names in sorted(candidates.items()):
    print(label, sorted(n.decode(errors="replace") for n in names))
```
