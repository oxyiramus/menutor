# MEN-107 B — доступ к аккаунтам и изоляция данных

MEN-110 · 25.11.2026 · **BLOCKED, частичные результаты для этапа E**

Объект: `d3322adaebb1a06561e2cd3177adde40c5a561df`. Базовый коммит `8908b1860a36d72b742608ee73faa44fcc62a008` добавляет только [реестр MEN-109](MEN-107-scope.md). Проверки запускались на копии из `git archive`. Исторические отчёты MEN-7 не использовались. Отдельных ADR по именам отслеживаемых файлов не найдено. Исходники, тесты и конфигурация снимка сохранены. Рабочие сервисы и данные не использовались.

## Матрица маршрутов MEN-109

Для каждого семейства защищённых операций анонимный результат **401** подтверждён T01. Колонки владельца и другого аккаунта содержат проверяемый инвариант. Ссылки на тесты описывают их утверждения, результаты исполнения указаны отдельно. Для POST создания владелец означает аккаунт вызывающего.

| Семейство | Анонимный | Владелец | Другой аккаунт и связанные данные | Доказательство |
|---|---|---|---|---|
| Ping, регистрация, вход | Ping публичен; регистрация и вход принимают собственные данные | Регистрация создаёт профиль и стартовые записи, вход выдаёт пару | Пара определяется проверенными учётными данными | T01, T02; `auth.py` в роутерах 52–88 и сценариях 56–115 |
| Refresh, logout | Требуется refresh из тела, Bearer роли не играет | Ротация одноразовая, logout отзывает переданный токен | Сессия определяется записью по хешу refresh | T02, T04; роутер 91–110, сценарии 129–152, 220–222 |
| GET/PATCH профиля, пароль | 401 | Профиль текущего аккаунта, смена по текущему паролю | Идентификатор берётся из Bearer, пароль через PATCH запрещён | T01, T02; роутер 113–160 |
| Продукты, цены, поиск, batch-delete | 401 | CRUD, личные страницы, подбор категории; batch удаляет свои ID | Чужие категории и записи исключаются; счётчик и поиск в области владельца | T02, T03; `manage_product.py`, `orm_product_repository.py` |
| Рецепты, расчёт, зависимости, вложенность, предпочтения, batch-delete | 401 | CRUD, предварительные расчёты и обход ингредиентов | Корневой и вложенные ID проверяются отдельно, обход ограничен аккаунтом | T03; `manage_recipe.py`, `validate_sub_recipe.py`, `flatten_recipe_products.py:29–35`, `calculate_recipe_cost.py:25–32`, `orm_recipe_repository.py` |
| Категории продуктов и рецептов | 401 | Личный список, использование, активация, перенос и удаление | Область владельца проверяется также для категории назначения | T03; `manage_category.py`, `base_category.py` |
| Семья и предпочтения | 401 | Личные списки и CRUD | Связи проверяют владельцев участников и продуктов; удаление не должно изменять чужие назначения | T03; `assign_preferences.py`, `manage_preference.py`, `orm_family_member_repository.py`, `orm_preference_repository.py` |
| Типы приёмов пищи | 401 | Личные записи, использование, ограничение для системной записи | Проверка владельца до признака системной записи; сводка использования в области аккаунта | T03; `manage_meal_type.py`, `orm_meal_type_repository.py` |
| Меню, слоты, перенос, очистка, копирование, сводка, PDF | 401 | Недельное меню и производные доступны владельцу | Слот требует своих рецепта, типа приёма и членов семьи; источник копии и производные проверяются по аккаунту | T03; `plan_menu.py`, `orm_menu_repository.py` |
| Генерация/экспорт покупок и сохранённые списки | 401 | Генерация, фильтрация, форматы, CRUD, копия и отметки | Меню, список, вложенный элемент и продукт ограничены владельцем и родительским списком | T03; `generate_shopping_list.py:17–21`, `generate_filtered_shopping_list.py`, `manage_saved_shopping_list.py`, `orm_saved_shopping_list_repository.py` |
| Импорт, экспорт и примеры | 401 | Импорт в область аккаунта; экспорт личных строк и примеров | Файл и переданные ID не задают владельца; связанные записи ограничены им; ошибочный импорт откатывается | T02–T04; `import_entities.py:20–50`, `export_entities.py:36–105`, `composition/_import_export.py` |

Общий справочник единиц — `UnitRow` без владельца, внешний ключ на имя единицы у продукта и ингредиента (`models.py:61–66,109–110,166`). Отдельный маршрут записи единиц в OpenAPI отсутствует. Стартовые категории создаются для конкретного пользователя через связи ORM (`orm_user_repository.py:52–65`). Проверка ссылки в репозитории `ownership.py:8–11` сопоставляет владельца и использует единый отказ для отсутствующей и чужой записи. Эту проверку нельзя обобщать на все ошибки: полное дифференциальное сравнение тел ответов чужого и отсутствующего ID не завершено.

## Сессии и транзакции по коду

- `backend/api/auth.py:13–32` извлекает Bearer. `GetCurrentUser.execute` проверяет токен и загружает пользователя. `backend/api/deps.py:10–14` открывает SQLAlchemy Session на запрос, FastAPI кеширует зависимость в пределах запроса. Композиция передаёт сессию репозиториям и импортёрам.
- `password_policy.py:3–24` задаёт 12 символов для нового пароля и 72 байта UTF-8 для всех паролей. `bcrypt_password_hasher.py:6–11` генерирует соль и проверяет исходные UTF-8 байты. Ошибки валидации AuthRoute исключают входные поля из ответа (`routers/auth.py:31–44`).
- Access подписывается HS256, содержит строковый `sub`, `type=access` и `exp` с 30 минутами по умолчанию. Refresh непрозрачный случайный, в БД хранится SHA-256 и срок 30 дней (`jwt_token_service.py:16–38`, `auth.py:21,104–115`). Logout отзывает только предъявленный refresh. Уже выданный access действует до `exp`, включая после смены пароля. Это заявленный контракт. Остаточный риск — использование уже выданного access в пределах оставшегося срока.
- Ротация берёт блокировку аккаунта, условно отзывает исходный refresh и вставляет замену в одной транзакции (`orm_refresh_token_repository.py:55–83`). Смена пароля использует условное обновление хеша и отзыв refresh до commit (`orm_user_repository.py:98–124`). SQLite проверяет часть откатов, результат блокировок PostgreSQL отсутствует.
- Импорт помечает свою транзакцию в Session, часть репозиториев через эту отметку применяет flush вместо промежуточного commit. При ошибке сценарий делает rollback (`import_entities.py:32–50`, `base.py:65–69`). Сценарий конкурирующего входа с импортом требует PostgreSQL.

## Наблюдения и непроверенные гипотезы

- **MEN-107-B-001 · Low · подтверждено чтением кода, эксплуатация не подтверждена.** `backend/infrastructure/auth/jwt_token_service.py:28–35`. Валидатор закрепляет алгоритм и сверяет тип, но не требует наличия `exp` и `sub` через параметры декодирования. Обращение к `sub` и преобразование в идентификатор не обрабатывают ошибки формы claims. Предпосылка — доверенно подписанный токен с некорректными claims. Штатный издатель формирует оба поля. Возможные последствия при нарушении договора издателя — отсутствие ограничения срока либо ошибка сервера. Рекомендуется явно требовать ключевые claims и проверять тип и допустимый диапазон идентификатора. Критерий исправления — отказ валидатора для неполного или некорректного набора claims. T02 подтверждает отказ для истёкшего токена, неверной подписи и неверного типа в существующем наборе.
- **MEN-107-B-002 · Medium · гипотеза по коду.** `backend/application/use_cases/auth.py:95–113`, `orm_user_repository.py:67–71,98–120`, `orm_refresh_token_repository.py:29–33`. Проверка пароля при входе, запись `last_login_at` и сохранение refresh не сериализованы с изменением пароля общей транзакцией. Требуется установить, сможет ли уже начавшийся вход со старым паролем сохранить пригодную сессию после успешной смены пароля. В случае подтверждения рекомендация — связать выдачу refresh с актуальным хешем или версией сессии транзакционно. Критерий проверки — результат входа и состояние сессий согласованы с порядком фиксации смены пароля. T04 блокирует проверку.
- **MEN-107-B-003 · Low · гипотеза по коду.** `frontend/src/api/accountSession.ts:78–109,114–123`. Объединение запросов refresh реализовано в памяти одной вкладки. Отказ refresh завершает текущую сессию, даже если другой контекст успел обновить пару для того же поколения. Возможен неожиданный выход при одновременном обновлении в двух вкладках. Критерий проверки — оба контекста корректно сходятся на действующей паре при конкурентном обновлении, а logout аннулирует оба. Межвкладочная очередь событий и наблюдаемая последовательность записи не проверены (T05).
- **MEN-107-B-004 · Informational · контракт и остаточный риск.** `backend/application/use_cases/auth.py:56–62,95–99`, `backend/api/main.py:104–108`. Повторная регистрация сообщает о занятом точном email по контракту. Текст ошибки входа одинаков для отсутствующего пользователя и неверного пароля, но при отсутствии пользователя bcrypt не выполняется. Временная различимость не измерялась. При пересмотре контракта регистрации отдельно оценить допустимую видимость существования аккаунта и выравнивание затрат проверки. Привязка риска к фактической доступности и лимитам production находится вне этапа B.

## Реестр доказательств

Все запуски 25.11.2026 на указанном снимке. Python 3.14.4, pytest 9.0.2, FastAPI 0.135.1, Starlette 0.52.1, anyio 4.12.1, HTTPX 0.28.1, SQLAlchemy 2.0.48, Alembic 1.18.4, bcrypt 5.0.0, PyJWT 2.11.0, psycopg2-binary 2.9.11 и testcontainers 4.15.0. Использован доступный интерпретатор из уже установленного окружения, рабочий каталог и SQLite-файлы выделены в архивной копии. Для повторения — создать копию по MEN-109, выделить доступный `TMPDIR` и выполнить команды от корня копии. Все пароли и токены в запусках тестовые.

### MEN-107-B-T01 · независимая проверка HTTP

Ожидалось: 401 без Bearer на каждой защищённой операции из OpenAPI; два синтетических аккаунта могут войти с паролем ровно 72 байта UTF-8; лишний байт даёт 422 без отражения пароля; PATCH с `password: null` не меняет имя. Фактически: 79 операций отклонены с 401, проверки обоих аккаунтов прошли, код 0. Проверка 401 использует минимальные запросы без JSON и не доказывает поведение с чужими ID при действительном Bearer или ошибки разбора тела.

Первый вариант с `TestClient` остановлен по таймауту, код 124. Стек показал ожидание portal в `TestClient.__enter__`. Рабочий сценарий использует ASGI в одном event loop с ограниченным ожиданием, без HTTP-сокета. Сохранить текст как временный сценарий в копии и выполнить `timeout 20 python -u -c "$(cat audit-http.py)"`.

```python
import asyncio
import os
import secrets
os.environ["JWT_SECRET_KEY"] = secrets.token_hex(32)
os.environ["DATABASE_URL"] = "sqlite:///" + os.getcwd() + "/independent.sqlite"
os.environ["CORS_ALLOWED_ORIGINS"] = ""
import re
import httpx
from backend.api.main import app

async def heartbeat():
    while True:
        await asyncio.sleep(0.02)

async def check():
    tick = asyncio.create_task(heartbeat())
    try:
        async with app.router.lifespan_context(app), httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://audit.test"
        ) as client:
            for index in range(2):
                credentials = dict(email=f"audit-{index}@example.test", password="я" * 36)
                result = await client.post("/api/auth/register", json=credentials)
                assert result.status_code == 201
                uid = result.json()["id"]
                data = (await client.post("/api/auth/login", json=credentials)).json()
                bearer = {"Authorization": f"Bearer {data['access_token']}"}
                assert (await client.get("/api/auth/me", headers=bearer)).json()["id"] == uid
                response = await client.patch("/api/auth/me", headers=bearer,
                                        json={"nickname": "Marker", "password": None})
                assert response.status_code == 422
                assert (await client.get("/api/auth/me", headers=bearer)).json()["nickname"] != "Marker"
                bad = dict(credentials, password=credentials["password"] + "x")
                denied = await client.post("/api/auth/login", json=bad)
                assert denied.status_code == 422 and bad["password"] not in denied.text
            public = {"/api/ping", "/api/auth/register", "/api/auth/login",
                      "/api/auth/refresh", "/api/auth/logout"}
            count = 0
            for path, operations in app.openapi()["paths"].items():
                if path in public:
                    continue
                target = re.sub(r"\{[^}]+\}", "1", path)
                for method in operations:
                    response = await client.request(method, target)
                    assert response.status_code == 401, (method, path, response.status_code)
                    count += 1
            print(f"Anonymous operations rejected: {count}. Two profile/password checks passed.")
    finally:
        tick.cancel()

asyncio.run(asyncio.wait_for(check(), 15))
```

### MEN-107-B-T02 · существующие регрессии, SQLite

`timeout 35 python -m pytest -q -p no:cacheprovider tests/integration/test_audit_regressions.py` → **15 passed in 10.70s**, код 0. Fixtures используют синтетические аккаунты и SQLite. Подтверждены утверждения о регистрации, входе, смене пароля, предупреждении повторной ротации, logout, rollback при отказе записи refresh, rollback при ошибке commit смены пароля, изоляции поиска/пакетного удаления и восстановлении Session после отката импорта. Контроль access после смены пароля соответствует контракту. SQLite не устанавливает порядок блокировок и видимость изменений PostgreSQL.

### MEN-107-B-T03 · наборы владельца, связей, производных, request Session

`python -m pytest --collect-only -q tests/integration/test_{api_data_isolation,related_object_isolation,derived_data_isolation,request_sessions,audit_postgresql}.py` → 356 собрано, код 0. Обычный запуск HTTP-наборов и SQLite-сессий не прошёл в ограниченное время из-за ожидания portal. Повтор с опросом selector каждые 20 мс сохраняет штатные fixtures и assertions. Воспроизведение в копии, передавая соответствующий путь к тесту как аргумент:

```sh
timeout 75 python -c '
import selectors, sys
import pytest
original = selectors.DefaultSelector.select
def poll(self, delay=None):
    return original(self, 0.02 if delay is None else min(delay, 0.02))
selectors.DefaultSelector.select = poll
sys.exit(pytest.main(sys.argv[1:]))
' -q -p no:cacheprovider tests/integration/test_{api_data_isolation,related_object_isolation,derived_data_isolation}.py
```

Полный повтор с обёрткой: код 124, 13 успешных отметок pytest до таймаута, итоговая сводка отсутствует. Обычные первые запуски вручную остановлены после зависания, код 130. Завершённые выборочные запуски с той же обёрткой:

| Файл и аргументы после `-p no:cacheprovider` | Фактический результат |
|---|---|
| `test_request_sessions.py -k sqlite` | 1 прошёл, код 0. Параллельные запросы получили разные Session, аутентификация и обработчик каждого использовали одну Session. |
| `test_related_object_isolation.py -k 'legacy_assignments or assigning_preferences'` | 3 прошли, код 0. Назначение и удаление предпочтений сохранили границу владельца. |
| `test_derived_data_isolation.py -k 'menu_summary_and_meal_type_usage or filtered_generation_ignores_foreign or recipe_reads_are_scoped'` | 3 прошли, код 0. Сводка, использование типов приёмов, чтение рецептов и фильтрация покупок соблюли утверждения тестов о владельце. |
| `test_api_data_isolation.py::test_direct_edit_and_delete_contract[shopping-lists-1]` и `test_api_data_isolation.py::test_batch_only_removes_owned_ids[recipes-0]` | 2 прошли, код 0. Прямые операции со списками и смешанное пакетное удаление рецептов. |
| `test_derived_data_isolation.py::test_entity_exports_filter_rows[mixed-recipes-json]` и `test_derived_data_isolation.py::test_menu_and_shopping_files_require_owner[export/pdf-pdf]` | 2 прошли, код 0. Отбор владельца при JSON-экспорте и доступ к экспорту меню в PDF. |
| `test_derived_data_isolation.py -k 'menu_import_rolls_back and recipe'` | 1 прошёл, код 0. Откат импорта меню при ссылке на чужой рецепт. |
| `test_personal_categories.py -k 'personal_category_catalog or foreign_category_references'` | 6 прошли, код 0. Личные каталоги категорий и отказ для чужих ссылок. |

Пути в таблице относительны к `tests/integration/`. Параметризованные ID передавать в кавычках. Ожидалось прохождение штатных утверждений при синтетических аккаунтах из fixtures. Успех отдельных выборок не распространяется на все варианты форматов и направлений.

### MEN-107-B-T04 · PostgreSQL и конкурентность

PostgreSQL 18.6. `initdb -D pg --auth=trust --no-locale` успешно создал отдельный кластер, код 0. `pg_ctl -D pg -o "-k $audit_dir/socket -p 15432 -c listen_addresses= -c statement_timeout=15000" -l pg.log -w start` → код 1, `could not bind Unix address … Operation not permitted`; сервер завершился. Выделенная база не запускалась. Существующий `test_password_change_refresh_overlap` использует два соединения, Events, паузу перед commit и подтверждение ожидания блокировки. Для закрытия критерия повторить оба порядка на выделенном PostgreSQL, дополнить проверкой конкурентных ротаций, logout и смены пароля, входа и смены пароля и запустить PostgreSQL-ветку `test_request_sessions.py` с отдельным `TEST_PERSONAL_CATEGORIES_POSTGRES_URL`. Ожидаемые инварианты — один успешный обмен refresh, отзыв всех прежних refresh при смене пароля, изоляция незавершённого импорта от параллельного запроса.

### MEN-107-B-T05 · frontend

Node 24.14.0, npm 11.9.0, Vitest 4.1.0, happy-dom 20.8.4, Vite 7.3.1, Axios 1.13.6, Pinia 3.0.4, Vue 3.5.30. `npm ci --offline` из локального кеша завершился кодом 1 из-за `spawnSync esbuild EPERM`. Повтор с `--ignore-scripts` установил версии из lock, код 0. `npm --prefix frontend test -- --maxWorkers=1 src/stores/__tests__/account-session.test.ts` и `node tests/frontend/run.mjs --maxWorkers=1` → код 1, `getaddrinfo EAI_AGAIN localhost` до запуска тестов. Реальный браузер со штатным API и Vite не подтверждён в среде с запрещённым связыванием сокетов.

Отдельная проба `python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); s.close()'` завершилась кодом 1 с `PermissionError: [Errno 1] Operation not permitted` при создании сокета. По коду `stores/auth.ts:30–47,58–91` сбрасывает профиль, stores, контекстное меню и буфер, а `App.vue:11–15` выводит с защищённого экрана. `api/client.ts:43–73` сопоставляет поколение сессии и AbortSignal до отправки и после ответа, повторяет запрос после 401 только один раз. `api/accountSession.ts:18–49,98–124` отслеживает маркер сессии и storage-события, поздний результат refresh после закрытия идёт на отзыв. Настройки отображения общие для профиля браузера, ключ недавних цветов включает ID пользователя (`stores/recipeSettings.ts:12–23`, `stores/shoppingListSettings.ts:15–27`, `composables/useRecentColors.ts:15–26`).

Happy-dom нужен для реактивности, логики очистки, размонтирования и синтетических ответов. Ручной двухвкладочный прогон нужен для реального порядка storage-событий, навигации, отмены транспорта и конкурирующих запросов. Использовать два синтетических аккаунта, задерживать один защищённый ответ и refresh, оставить черновик и буфер, выйти и открыть другой аккаунт. Проверить очистку обеих вкладок, отсутствие восстановления предыдущей сессии, отсутствие прежних данных, объединение параллельных 401 во вкладке и наблюдаемое поведение при 401 в двух вкладках.

## Передача E и границы завершения

Анонимная колонка закрыта независимым запуском, две другие покрыты выборочно. Полная HTTP-матрица с действительным Bearer, сравнение ошибок чужих и отсутствующих ID, подтверждение конкурентных инвариантов PostgreSQL, happy-dom и браузер остаются открытыми. Статический анализ и SQLite не предоставляют этих доказательств. RED для исправления, GREEN и REFACTOR не выполнялись. Задание диагностическое, тесты и реализацию менять запрещено. T01–T05 фиксируют результаты и ограничения без сопоставления с MEN-7.
