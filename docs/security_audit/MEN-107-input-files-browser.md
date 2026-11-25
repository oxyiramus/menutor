# MEN-111 — аудит входов, файлов и браузера

25.11.2026, этап C задачи MEN-107. Объект — d3322adaebb1a06561e2cd3177adde40c5a561df. База — 8908b1860a36d72b742608ee73faa44fcc62a008. Между ними добавлен только [план A](MEN-107-scope.md). Анализ и прогоны выполнены до сопоставления с MEN-7. По именам отслеживаемых путей отдельных ADR не обнаружено. Контекст — [архитектура](../architecture.md), [руководство разработчика](../CONTRIBUTIND.md), [аккаунты](../features/accounts.md). Владение данными проверяет B, reverse proxy и ограничения edge проверяет D.

## Покрытие A

| ID | Входы и доказательства | Ограничение |
|---|---|---|
| MEN-107-C-T01 | Регистрация, вход, refresh/logout, профиль, пароль и Bearer. backend/api/schemas/auth.py:15–77, routers/auth.py:31–110,124–154, api/auth.py:18–31, domain/services/password_policy.py. Регистрация валидирует форму email, вход допускает старые адреса. Политика пароля проверяет байты и символы в сценарии. Профиль отдельно отклоняет password. | T08/T09 покрывают ASGI и SQLite. PostgreSQL и реальная сеть не проверены. |
| MEN-107-C-T02 | CRUD продуктов и рецептов, категории, поиск, batch, cost/flatten/validate preview, dependents и matching. backend/api/schemas/{product,recipe}.py, api/converters.py, application/use_cases/{manage_product,manage_recipe,preview_recipe_cost,preview_flattened_products,crud_base}.py. В CRUD ингредиента есть XOR, preview использует отдельные схемы. UI ограничивает цену, коэффициент и порции, схемы принимают более широкие значения. Quantity проверяет единицу, Money — совпадение валют при сложении. | T08/T09 и C-003/C-004. Полный перебор полей и Unicode при сравнении PostgreSQL не выполнены. |
| MEN-107-C-T03 | Категории, семья, предпочтения и типы приёмов. backend/api/schemas/{category,family,preference,meal_type}.py и application/use_cases/manage_{category,meal_type,preference}.py. Формат цвета проверяется, имя типа приёма ограничено 50 символами, время шаблоном; сценарий обрезает пробелы. Списки ссылок семьи и предпочтений без общего лимита длины схемы. UI ограничивает семейный множитель 0,1–5, схема принимает float. | Статический анализ и существующее покрытие бизнес-сценариев. Полная динамическая матрица граничных значений не выполнена. |
| MEN-107-C-T04 | Меню, слоты, move/remove/clear/copy, summary, покупки, фильтры, save/copy/toggle, ping. backend/api/schemas/{menu,shopping_list}.py, api/routers/{menus,shopping_list,system}.py, domain/entities/menu.py:15–37. Схема записи слота проверяет XOR, домен проверяет день. Move/remove имеют отдельные схемы. Позиции покупок содержат пользовательский текст и числа без общей границы длины массива. Ping без пользовательского тела. | T08 проверяет расчёты. Ширина графа и пределы отдельных полей не измерены. |
| MEN-107-C-T05 | Импорт products/recipes JSON и CSV, menus JSON, вложенные слоты, ингредиенты и шаги. backend/composition/_import_export.py:40–61 регистрирует пять адаптеров. api/routers/import_export.py:59–87 читает multipart до лимита + 1, формат берётся из реестра. Имя и MIME не определяют парсер или файловый путь. infrastructure/import_/parsing.py:16–51 проверяет UTF-8, форму и число верхних записей. JSON разбирается до проверки числа записей, CSV strict читает limit + 1; вложенный JSON CSV разбирается отдельно. application/use_cases/import_entities.py:32–50 управляет транзакцией, repositories/base.py:65–69 при импорте делает flush. | T08 проверяет откат для всех пяти адаптеров после корректной строки. Предупреждения совместимы с успешным импортом. T09 проверяет границу записей и MIME на ASGI. |
| MEN-107-C-T06 | Экспорт products/recipes JSON/CSV, recipes compact JSON, menus JSON, shopping text/CSV/JSON/PDF, меню PDF отдельно. backend/composition/_import_export.py:26–38; backend/api/routers/{import_export,menus,shopping_list}.py. PDF и compact JSON не имеют отдельного импортера. Реестр ограничивает расширение. Меню формирует ASCII и percent-encoded UTF-8 имя, покупки возвращают attachment. SPA создаёт и отзывает Blob URL. | T08 читает PDF через pypdf и проверяет обмен с SQLite. Compact JSON, text и заголовки всех вариантов просмотрены по коду; отдельная динамика каждого формата не выполнена. |
| MEN-107-C-T07 | DOM, URL, CSS, storage, CORS и скачивания. Поиск по frontend/src, трассировка api/{client,auth,accountSession}.ts, router/index.ts, форм и отображения. Пользовательский текст выводится интерполяцией или через поля форм, явных v-html, innerHTML или пользовательских href/src не найдено. URL рецепта сохраняется строкой, возвращается в поле type=url и экспортируется. Категорийный цвет используется в свойствах цвета. Справочная ссылка статическая, ошибки импорта и уведомления выводятся текстом. | T09 проверяет CORS на ASGI. T10 проверяет Vue с моками API и методов скачивания. Исполнение XSS, загрузки и навигация в настоящем браузере не проверены. |

### SQL, CSRF, сеть и файлы

- Поиск прослежен от backend/api/routers/{products,recipes}.py:32–42/55–70 до infrastructure/repositories/orm_product_repository.py:80–112 и orm_recipe_repository.py:170–205. Строка с процентами передаётся как значение в SQLAlchemy ilike. ID, область владельца, offset и limit передаются ORM-выражениями. Символы процента и подчёркивания сохраняют семантику шаблона. Поиск raw SQL выявил миграции, seed и константные внутренние идентификаторы таблиц в infrastructure/database/personal_categories.py:53–102. В просмотренных путях из тела, поиска или файла до текста SQL не обнаружено. Сетевой PostgreSQL не проверен.
- Axios формирует Authorization из localStorage, backend читает явный заголовок. Refresh и logout принимают токен из JSON, а register/login возвращают токены в JSON без установки cookie. Межсайтовый запрос с автоматически приложенными cookie не получает полномочия действующего пользователя. CORS разрешает явные origins и задаёт allow_credentials=False (backend/api/main.py:55–87). Это не защищает от исполнения скрипта на том же origin, где оба токена доступны JavaScript. Признаков stored/reflected/DOM XSS в просмотренных путях вывода не найдено. Проверки в браузере остаются открыты.
- Инвентаризация по backend/**/*.py, frontend/src, pyproject.toml, frontend/package.json и lock не выявила прикладных LLM API, загрузки URL рецепта и сетевого клиента в сценариях. Сервер использует настроенную БД, VERSION, конфигурацию, миграции, встроенные или системные PDF-шрифты. Стандартная документация FastAPI может обращаться к CDN из браузера. Прокси, внешние обращения сборки и CI относятся к D. Разрешение источников изображений через PDF-разметку представляет отдельный риск C-001.
- HTTP-экспорт пользуется export_bytes. backend/infrastructure/export/csv_exporter.py:47–55 содержит файловый метод, который маршруты не вызывают. Клиент выбирает расширение по имени, сервер читает объект UploadFile.file; SQLite-путь задаётся конфигурацией. По входному имени загрузки или скачивания пути к серверному traversal не обнаружено. PDF обрабатывается отдельно в C-001.
- AuthRoute удаляет input и ctx из ошибок схемы (backend/api/routers/auth.py:31–44). Остальные роутеры используют стандартную обработку FastAPI. Неожиданная ошибка импорта даёт фиксированный ответ и сообщение без exception info (routers/import_export.py:75–83). api/main.py:152–172 возвращает текст DomainError, RepositoryError и ImportValidationError. Ошибка единицы может повторить ввод, RepositoryError может включить имя таблицы и ID (infrastructure/repositories/base.py:58–74). T08 проверяет техническую ошибку импорта с подменой адаптера, T09 — публичный ответ на необработанную ошибку параметра. Журнал Uvicorn и поведение при реальной ошибке драйвера, включая наличие SQL, путей и персональных данных, не проверены.

## Находки для E

- **MEN-107-C-001 — Medium. PDF интерпретирует пользовательскую разметку.** backend/infrastructure/export/menu_pdf_exporter.py:70–112,203–222,263 и shopping_list_pdf_exporter.py:136–166 передают имена, категории и часть составных строк в ReportLab Paragraph. Пользователь с правами записи и экспорта может изменить разметку PDF. T09 подтвердил интерпретацию форматирования на синтетическом имени меню. В ReportLab 4.4.10 paraparser.py:2708–2724 и lib/utils.py:460–540,620–653 разметка поддерживает разрешение источников изображений через файловый и сетевой ввод. Это путь к ресурсам с правами серверного процесса. Доступ к внутренним узлам и произвольным локальным данным не установлен. Экранировать пользовательские фрагменты до составления Paragraph. При перепроверке требовать буквального вывода текста и отсутствия доступа к загрузчику на недоверенном содержимом для обоих PDF.
- **MEN-107-C-002 — Medium. Формульное значение сохраняется в CSV.** backend/infrastructure/export/product_csv_exporter.py:24–44, recipe_csv_exporter.py:26–64, csv_exporter.py:26–44 передают текстовые поля в csv.writer. При открытии экспорта с контролируемой другим источником строкой редактор может обработать её как формулу. T09 подтвердил сохранение простой арифметической строки в ячейке CSV продуктов. Исполнение в редакторе не проверено. Согласовать безопасное представление всех текстовых полей для таблиц с контрактом обратного импорта. Проверить все три экспортера, кавычки, разделители и пробельные префиксы в выбранных редакторах.
- **MEN-107-C-003 — Low. Проверки чисел различаются между UI, схемой и импортом.** backend/api/schemas/product.py:6–15, infrastructure/import_/parsing.py:45–51 и frontend/src/components/products/ProductForm.vue:80–89,146–158. T09 показал, что схема принимает отрицательную цену, бесконечный коэффициент и bool в ID, а парсер усекает дробную часть. Неизвестное поле схема отбрасывает. В аутентифицированных операциях это создаёт риск неверных цен, связей и несерилизуемых чисел. Последствия записи каждого значения не установлены. Согласовать диапазоны и политику приведения типов между CRUD, preview и импортом. Проверить контракт на границах и неизменность записей при отказе.
- **MEN-107-C-004 — Low. Неверный параметр экспорта даёт 500.** backend/api/routers/import_export.py:19–34 преобразует элементы ids через int без обработки ошибок. Аутентифицированный пользователь получает 500 при ошибке ввода, а сервер может журналировать необработанное исключение. T09 проверяет статус и отсутствие внутренних деталей ответа. Валидировать тип, размер и диапазон списка до use case. Перепроверить пустые элементы, неверный тип и переполнение, включая серверный журнал.
- **MEN-107-C-005 — Informational. Общий бюджет работы не установлен.** backend/application/use_cases/crud_base.py:120–134 читает каталог целиком при запросе без page, а постраничная выдача использует 25 строк и подсчёт. export_entities.py:77–103 загружает всю коллекцию даже при выборе ID. Артефакты материализуются в памяти. domain/services/recipe_dependency_validator.py:6–47 проверяет глубину до пяти и цикл, но не общий бюджет обхода ветвей. api/routers/recipes.py:61–78 добавляет расчёт стоимости элементов выдачи. Предпосылка — большой собственный каталог или граф. T08/T09 отражают небольшой локальный объём; влияние на доступность других аккаунтов не установлено. Определить бюджеты и проверить их на выделенном стенде вместе с D.

## Проверки и воспроизведение

Все проверки выполнены 25.11.2026 на указанном SHA. Git 2.53.0, Python 3.14.4, SQLite 3.46.1, pytest 9.0.2, FastAPI 0.135.1, Starlette 0.52.1, AnyIO 4.12.1, HTTPX 0.28.1, Pydantic 2.12.5, SQLAlchemy 2.0.48, ReportLab 4.4.10, pypdf 7.1.0. Node 24.14.0, npm 11.9.0, Vite 7.3.1, Vitest 4.1.0, happy-dom 20.8.4, Vue 3.5.30, Vue Test Utils 2.4.6.

Из корня репозитория выделить приватный временный каталог на доступной для записи ФС и распаковать в него только снимок. Ниже AUDIT_PYTHON — абсолютный путь к интерпретатору с пакетами указанных версий. В этом прогоне использовалось доступное локальное окружение смежного checkout только как источник библиотек. Все импорты backend идут из архивной копии. Исходники, тесты и конфигурация проекта не менялись. Синтетические ключи и временные БД создаются фикстурами или сценарием.

```sh
audit_dir=$(mktemp -d "$PWD/.men111.XXXXXX")
git archive d3322adaebb1a06561e2cd3177adde40c5a561df | tar -x -C "$audit_dir"
cd "$audit_dir"
```

### MEN-107-C-T08 — штатные Python-проверки

```sh
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 CORS_ALLOWED_ORIGINS= \
  timeout 40s "$AUDIT_PYTHON" -m pytest -q -p no:cacheprovider \
  tests/integration/test_audit_files.py tests/integration/test_audit_calculations.py \
  tests/unit/infrastructure/test_audit_pdf.py tests/unit/domain/test_audit_value_objects.py
```

Ожидалось успешное прохождение обмена, отката, проверок рекурсии, расчётов и структуры PDF. Факт — 43 passed за 4,07 с, выход 0. Фикстуры используют SQLite в памяти с внешними ключами, синтетические записи и реальные адаптеры и ReportLab. Разбор PDF через pypdf покрывает структуру и представление, потребитель CSV и сетевые эффекты PDF этим не проверяются.

Первый совместный запуск с test_import_limits.py, test_import_errors.py и test_audit_http.py завершился по таймауту 90 с (124). Отдельный test_import_limits.py с диагностикой faulthandler дошёл до первого setup и застрял на входе Starlette TestClient в asyncio portal. Отдельный test_import_errors.py без обхода завершился по таймауту 25 с (124). Повторный запуск с временным pytest-плагином, который ставит короткий периодический callback в event loop, выполнил 15 тестов до таймаута 50 с (124). Плагин меняет ожидание loop, приложение, тесты и драйверы остаются теми же. Это ASGI в процессе, даже для теста с real_http в названии.

### MEN-107-C-T09 — независимый сценарий

Ожидалось, что повреждённая кодировка и 1001 верхняя запись отклоняются, CORS различает два origins, cookie без заголовка не авторизует запрос и ошибка схемы auth не повторяет маркер. Эти проверки прошли. Для сравнения с защитными инвариантами сценарий фиксирует фактическое сохранение формулы, интерпретацию PDF-разметки, коэрцию чисел и ошибку 500. Проверка ASGI без периодического callback прошла оба preflight, затем вышла по защитному таймауту на переходе в worker thread (1). С callback и свежей синтетической учётной записью итоговый прогон завершился с кодом 0.

| Операция | Факт |
|---|---|
| JSON и CSV разбор 1000 записей | 39 000 и 10 005 байт, 0,35 и 0,66 мс. Для 1001 записей и неверного UTF-8 нужные типы исключений. |
| Multipart JSON, 32 товара, расширение bin и application/octet-stream | 200, 88,34 мс. Содержимое определяется форматом маршрута, MIME не блокирует импорт. |
| Выдача товаров, page=1 / page=0 | 200, 25 элементов из 32, 67,99 мс / 422, 34,76 мс. |
| CSV товаров / неверный тип ids | 200, 1145 байт, 45,50 мс / 500 с обычным текстом Internal Server Error, 44,85 мс. |
| Разрешённый и запрещённый preflight, cookie, валидация auth | 200/400; без allow-credentials; 401; 422 без значения маркера. |

Один последовательный прогон занял 1,90 с, maxRSS процесса 125304 КиБ. Время включает локальный ASGI, SQLite, создание учётной записи и диагностический callback. Это единичные локальные оценки без переноса на production. Верхние вложенные объёмы, параллелизм, тяжёлый PDF, реальный PostgreSQL и proxy-лимиты в оценку не входят.

Сохранить код как diagnostic-c.py. Повторять в новой копии с пустой audit-c.sqlite.

```sh
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 timeout -k 2s 16s \
  /usr/bin/time -f 'elapsed=%e s maxRSS=%M KiB' "$AUDIT_PYTHON" -u diagnostic-c.py
```

```python
import asyncio, csv, io, json, os, secrets
from decimal import Decimal
from importlib.metadata import version
from time import perf_counter
os.environ.update(DATABASE_URL="sqlite:///audit-c.sqlite", JWT_SECRET_KEY=secrets.token_hex(32),
                  CORS_ALLOWED_ORIGINS="https://allowed.example.test", IMPORT_MAX_RECORDS="1000")
import httpx
from pypdf import PdfReader
from backend.api.main import app
from backend.api.schemas.product import ProductCreate
from backend.domain.entities.menu import WeeklyMenu
from backend.domain.entities.product import Product
from backend.domain.exceptions import ImportLimitExceededError, ImportValidationError
from backend.domain.value_objects.money import Money
from backend.infrastructure.export.menu_pdf_exporter import MenuPdfExporter
from backend.infrastructure.export.product_csv_exporter import ProductCsvExporter
from backend.infrastructure.import_.parsing import csv_rows, json_rows, parse_int

for name in ("fastapi", "starlette", "anyio", "httpx", "pydantic", "sqlalchemy", "reportlab", "pypdf", "pytest"):
    print(name, version(name))
for parser, body in (
    (json_rows, lambda n: json.dumps([{"name": "Ёж 🥕"}] * n).encode()),
    (csv_rows, lambda n: ("name\n" + "Ёж 🥕\n" * n).encode()),
):
    data = body(1000)
    start = perf_counter()
    assert len(parser(data)) == 1000
    print(parser.__name__, len(data), round((perf_counter() - start) * 1000, 2), "ms")
    for bad_data, expected in ((body(1001), ImportLimitExceededError), (b"\xff", ImportValidationError)):
        try:
            parser(bad_data)
        except expected:
            pass
        else:
            raise AssertionError(expected)
assert parse_int(1.9, "id", "test") == 1 and parse_int(True, "id", "test") == 1
model = ProductCreate(name=" ", category_id=True, recipe_unit="g", purchase_unit="kg",
                      price_amount="-1", conversion_factor="Infinity", extra_marker=True)
assert model.category_id == 1 and model.conversion_factor == float("inf")
assert model.price_amount == -1 and "extra_marker" not in model.model_dump()
print("coercion and ignored extra field confirmed at schema/parser layer")
data = ProductCsvExporter().export_bytes([Product(1, "=1+1", "g", "kg", Money(Decimal(1)), 1000, 1)])
assert list(csv.DictReader(io.StringIO(data.decode())))[0]["name"] == "=1+1"
pdf = PdfReader(io.BytesIO(MenuPdfExporter().export_bytes(WeeklyMenu(1, "<b>Marker</b>", []), {}, {})))
assert "Marker" in pdf.pages[0].extract_text() and "<b>" not in pdf.pages[0].extract_text()
print("CSV formula text preserved, PDF formatting markup interpreted")

async def smoke():
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                     base_url="http://audit.example.test") as client:
            for origin, expected in (("https://allowed.example.test", 200), ("https://other.example.test", 400)):
                response = await client.options("/api/products", headers={
                    "Origin": origin, "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "authorization"})
                assert response.status_code == expected
                assert ("access-control-allow-origin" in response.headers) == (expected == 200)
                assert "access-control-allow-credentials" not in response.headers
            assert (await client.get("/api/products", headers={"Cookie": "access_token=synthetic"})).status_code == 401
            response = await client.post("/api/auth/register", json={"password": "synthetic-marker"})
            assert response.status_code == 422 and "synthetic-marker" not in response.text
            print("ASGI preflight 200/400, cookie 401, validation 422 sanitized")


            password = secrets.token_urlsafe(24)
            credentials = {"email": f"{secrets.token_hex(4)}@example.test", "password": password}
            assert (await client.post("/api/auth/register", json=credentials)).status_code == 201
            tokens = await client.post("/api/auth/login", json=credentials)
            assert tokens.status_code == 200
            client.headers["Authorization"] = "Bearer " + tokens.json()["access_token"]
            categories = (await client.get("/api/product-categories")).json()
            upload = json.dumps([{"name": f"Test {i}", "category_id": categories[0]["id"],
                                  "recipe_unit": "g", "purchase_unit": "kg", "price_amount": 1}
                                 for i in range(32)]).encode()
            for method, endpoint, status, kwargs in (
                ("POST", "products/import/json", 200, {"files": {"file": ("test.bin", upload, "application/octet-stream")}}),
                ("GET", "products?page=1", 200, {}),
                ("GET", "products?page=0", 422, {}),
                ("GET", "products/export/csv", 200, {}),
                ("GET", "products/export/csv?ids=invalid", 500, {}),
            ):
                start = perf_counter()
                result = await client.request(method, "/api/" + endpoint, **kwargs)
                assert result.status_code == status, (endpoint, result.status_code)
                if endpoint == "products?page=1":
                    assert len(result.json()["items"]) == 25 and result.json()["total"] == 32
                if status == 500:
                    assert result.text == "Internal Server Error"
                print(method, endpoint, status, len(result.content), round((perf_counter() - start) * 1000, 2), "ms")

async def heartbeat():
    while True:
        await asyncio.sleep(0.01)

async def run():
    ticker = asyncio.create_task(heartbeat())
    try:
        await asyncio.wait_for(smoke(), 12)
    finally:
        ticker.cancel()

asyncio.run(run())
```

### MEN-107-C-T10 — компоненты Vue

Установка из локального кэша npm с lock-файлом — 418 пакетов, выход 0. Команда штатного runner сначала остановилась на getaddrinfo EAI_AGAIN localhost (1). С числовым локальным адресом и отключённым WS тесты дошли до старта окружения, но не могли создать временный каталог в /tmp (1, 16 наборов без тестов). С отдельным TMPDIR в копии прошли 111 тестов в 16 наборах за 7,30 с (0). Конфигурация запуска импортирует штатные настройки, меняет только временное хранилище и сетевые настройки Vite. Тесты файлов подменяют API, Blob URL и клик. Результат подтверждает логику интерфейса в happy-dom.

```sh
timeout 55s npm --prefix frontend ci --offline --ignore-scripts --no-audit --no-fund
timeout 45s node tests/frontend/run.mjs
```

После первой команды runner создаёт симлинк tests/frontend/node_modules. Временный diagnostic-vitest.mjs для повторного запуска:

```js
import config from './tests/frontend/vitest.config.mjs'
export default { ...config, cacheDir: './audit-vite-cache', server: { host: '127.0.0.1', hmr: false, ws: false } }
```

```sh
TMPDIR="$PWD" timeout -k 2s 45s node frontend/node_modules/vitest/vitest.mjs run \
  --config diagnostic-vitest.mjs --configLoader native
```

### MEN-107-C-T11 — внешний стенд

Ожидалось определить доступность сети, браузера и контейнеров. Факт — socket(AF_INET) для пробного loopback завершился с EPERM (1), firefox --version отклонён snap-confine (1), docker version --format '{{.Server.Version}}' не смог обратиться к сокету (1). Chromium в PATH отсутствует. Проверка PostgreSQL по сокету также открыта, план A зафиксировал EPERM при старте выделенного сервера. Ни сетевой HTTP, ни браузер, ни живой PostgreSQL результатов не дали. Повторить на изолированном стенде по [плану A](MEN-107-scope.md). Критерии ручной проверки — CORS и передача credentials с двух origins, буквальный вывод имён/комментариев/ошибок, заголовки и фактические имена всех скачиваний, открытие CSV в целевом редакторе, журнал реального Uvicorn при синтетической ошибке драйвера. Для ресурсоёмких тестов измерять небольшие последовательные ступени с таймаутом и потолком объёма. Проверить размеры multipart до передачи роутеру совместно с D. Для вложенных рецептов разделить предел глубины и число посещений в широком графе. Зафиксировать версии и ограничения стенда отдельно от результатов SQLite.

### Диагностический плагин для T08

Сохранить как diagnostic_loop.py в копии, если TestClient блокируется на доставке callback в event loop.

```python
import asyncio

class PollingPolicy(asyncio.DefaultEventLoopPolicy):
    def new_event_loop(self):
        loop = super().new_event_loop()

        def tick():
            loop.call_later(0.01, tick)

        loop.call_soon(tick)
        return loop

def pytest_configure():
    asyncio.set_event_loop_policy(PollingPolicy())
```

```sh
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 CORS_ALLOWED_ORIGINS= \
  TMPDIR="$PWD" PYTHONPATH="$PWD" timeout -k 2s 50s "$AUDIT_PYTHON" \
  -m pytest -q -p no:cacheprovider -p diagnostic_loop --basetemp="$PWD/pytest-with-polling" \
  tests/integration/test_import_limits.py tests/integration/test_import_errors.py \
  tests/integration/test_audit_http.py
```

### MEN-107-C-T12 — SQLAlchemy bind по двум диалектам

Проверка воспроизводит выражение поиска обоих репозиториев с синтетическим Unicode и метасимволами LIKE. Ожидалось отсутствие маркера в SQL-тексте и наличие исходной строки в параметре. Все четыре комбинации дали bound, выход 0. Это компиляция выражения в SQLAlchemy 2.0.48 без обращения к серверу.

```sh
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 timeout 5s "$AUDIT_PYTHON" - <<'PY'
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from backend.infrastructure.database.models import ProductRow, RecipeRow

marker = "Ёж d’Artagnan_%"
for model in (ProductRow, RecipeRow):
    stmt = select(model.id).where(model.name.ilike(f"%{marker}%"))
    for dialect in (sqlite.dialect(), postgresql.dialect()):
        compiled = stmt.compile(dialect=dialect)
        assert marker not in str(compiled)
        assert list(compiled.params.values()) == [f"%{marker}%"]
        print(model.__name__, dialect.name, "bound")
PY
```

### Уточняющие повторы T08

После таймаута совместного запуска отдельно выполнены test_audit_http.py с диагностическим плагином и фильтром `-k 'real_http_register or preserves_email_case or does_not_echo'` (3 passed, 37 deselected, 3,77 с, выход 0, лимит 30 с). В составе — регистрация с сохранением регистра email, прикладной маршрут записи и расчёта, исключение маркера из валидационной ошибки auth. Это TestClient. Проверка сетевого HTTP остаётся открытой. Файл test_audit_calculations.py отдельно с `--durations=4` и лимитом 15 с дал 11 passed за 1,23 с (0). Самые длинные опубликованные этапы — setup 0,09–0,12 с. Выделенного замера стоимости каждого вычисления нет.

Полные test_import_errors.py и test_import_limits.py повторены раздельно с тем же плагином, отдельными basetemp и лимитом 20 с на процесс. До таймаута (124) pytest вывел шесть и пять успешных тестов соответственно. Эти прогоны и совместный прогон не засчитаны как прошедшие наборы. Технические ошибки импорта с подменой адаптера остаются частично проверенными. Полные три набора следует повторить в среде, где TestClient выполняется штатно.

## Границы завершения

Отчёт фиксирует независимые результаты для E. Полная динамическая верификация блокируется ограничениями сети и браузера и повторяющимся таймаутом штатных ASGI-наборов. Статическая проверка и ограниченные сценарии выше сохраняют силу в указанных границах. TDD-цикл приложения не выполнялся по условиям диагностической задачи, которая разрешает только отчёт и временные диагностические сценарии. Для проверки защитных инвариантов T09 сохранил наблюдения по PDF, CSV, коэрции и обработке неверного параметра. Исправления и рефакторинг приложения выходят за рамки C.
