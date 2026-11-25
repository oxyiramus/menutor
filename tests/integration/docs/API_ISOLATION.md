# TASK 1: матрица HTTP-проверок

Все строки проверяются без JWT и с недействительным JWT тестом `test_every_scoped_route_requires_valid_jwt`.
Проверки владения выполняются в обоих направлениях; списки — в последовательности A → B → A.

| Метод | Маршрут | Проверка с JWT |
|---|---|---|
| GET | `/api/auth/me` | test_profile_and_password_only_change_current_user |
| PATCH | `/api/auth/me` | test_profile_and_password_only_change_current_user |
| POST | `/api/auth/me/password` | test_profile_and_password_only_change_current_user |
| GET | `/api/recipes` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| POST | `/api/recipes` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| GET | `/api/recipes/categories` | Только JWT; владение категориями — TASK 4 |
| POST | `/api/recipes/cost-preview` | JWT: test_every_scoped_route_requires_valid_jwt; проверка вычислений/экспорта — TASK 3 (вне TASK 1) |
| POST | `/api/recipes/validate-sub-recipe` | JWT: test_every_scoped_route_requires_valid_jwt; проверка вычислений/экспорта — TASK 3 (вне TASK 1) |
| GET | `/api/recipes/{recipe_id}` | test_direct_edit_and_delete_contract |
| PUT | `/api/recipes/{recipe_id}` | test_direct_edit_and_delete_contract |
| DELETE | `/api/recipes/{recipe_id}` | test_direct_edit_and_delete_contract; test_recipe_deletion_preserves_dependency_contract |
| GET | `/api/recipes/{recipe_id}/flattened-products` | JWT: test_every_scoped_route_requires_valid_jwt; проверка вычислений/экспорта — TASK 3 (вне TASK 1) |
| POST | `/api/recipes/{recipe_id}/flattened-products-preview` | JWT: test_every_scoped_route_requires_valid_jwt; проверка вычислений/экспорта — TASK 3 (вне TASK 1) |
| GET | `/api/recipes/{recipe_id}/dependents` | test_additional_direct_operations |
| POST | `/api/recipes/batch-delete` | test_batch_only_removes_owned_ids; test_batch_id_combinations_and_retry |
| GET | `/api/recipes/{recipe_id}/matching-preferences` | test_additional_direct_operations |
| GET | `/api/products` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| POST | `/api/products` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| GET | `/api/products/categories` | Только JWT; владение категориями — TASK 4 |
| PUT | `/api/products/{product_id}` | test_direct_edit_and_delete_contract |
| DELETE | `/api/products/{product_id}` | test_direct_edit_and_delete_contract |
| PATCH | `/api/products/{product_id}/price` | test_additional_direct_operations |
| POST | `/api/products/batch-delete` | test_batch_only_removes_owned_ids; test_batch_id_combinations_and_retry |
| GET | `/api/menus` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| POST | `/api/menus` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| GET | `/api/menus/{menu_id}` | test_direct_edit_and_delete_contract |
| DELETE | `/api/menus/{menu_id}` | test_direct_edit_and_delete_contract |
| GET | `/api/menus/{menu_id}/summary` | JWT: test_every_scoped_route_requires_valid_jwt; проверка вычислений/экспорта — TASK 3 (вне TASK 1) |
| POST | `/api/menus/{menu_id}/slots` | test_menu_slot_writes_require_menu_owner |
| DELETE | `/api/menus/{menu_id}/slots` | test_menu_slot_writes_require_menu_owner |
| POST | `/api/menus/{menu_id}/slots/move` | test_menu_slot_writes_require_menu_owner |
| POST | `/api/menus/{menu_id}/clear` | test_additional_direct_operations |
| POST | `/api/menus/{menu_id}/copy` | test_additional_direct_operations |
| POST | `/api/menus/{menu_id}/export/pdf` | JWT: test_every_scoped_route_requires_valid_jwt; проверка вычислений/экспорта — TASK 3 (вне TASK 1) |
| GET | `/api/family-members` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| POST | `/api/family-members` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| PUT | `/api/family-members/{member_id}` | test_direct_edit_and_delete_contract |
| DELETE | `/api/family-members/{member_id}` | test_direct_edit_and_delete_contract |
| POST | `/api/menus/{menu_id}/shopping-list` | JWT: test_every_scoped_route_requires_valid_jwt; проверка вычислений/экспорта — TASK 3 (вне TASK 1) |
| POST | `/api/menus/{menu_id}/shopping-list/filtered` | JWT: test_every_scoped_route_requires_valid_jwt; проверка вычислений/экспорта — TASK 3 (вне TASK 1) |
| POST | `/api/menus/{menu_id}/shopping-list/export/text` | JWT: test_every_scoped_route_requires_valid_jwt; проверка вычислений/экспорта — TASK 3 (вне TASK 1) |
| POST | `/api/menus/{menu_id}/shopping-list/export/csv` | JWT: test_every_scoped_route_requires_valid_jwt; проверка вычислений/экспорта — TASK 3 (вне TASK 1) |
| POST | `/api/menus/{menu_id}/shopping-list/export/json` | JWT: test_every_scoped_route_requires_valid_jwt; проверка вычислений/экспорта — TASK 3 (вне TASK 1) |
| POST | `/api/menus/{menu_id}/shopping-list/export/pdf` | JWT: test_every_scoped_route_requires_valid_jwt; проверка вычислений/экспорта — TASK 3 (вне TASK 1) |
| GET | `/api/shopping-lists` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| POST | `/api/shopping-lists` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| GET | `/api/shopping-lists/{list_id}` | test_direct_edit_and_delete_contract |
| PUT | `/api/shopping-lists/{list_id}` | test_direct_edit_and_delete_contract |
| PATCH | `/api/shopping-lists/{list_id}` | test_additional_direct_operations |
| DELETE | `/api/shopping-lists/{list_id}` | test_direct_edit_and_delete_contract |
| POST | `/api/shopping-lists/{list_id}/copy` | test_additional_direct_operations |
| POST | `/api/shopping-lists/{list_id}/items/{item_id}/toggle-purchased` | test_additional_direct_operations |
| GET | `/api/preferences` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| POST | `/api/preferences` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| GET | `/api/preferences/{preference_id}` | test_direct_edit_and_delete_contract |
| PUT | `/api/preferences/{preference_id}` | test_direct_edit_and_delete_contract |
| DELETE | `/api/preferences/{preference_id}` | test_direct_edit_and_delete_contract |
| GET | `/api/meal-types` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| POST | `/api/meal-types` | POST: test_forged_owner_is_ignored_on_create_and_update; GET: test_lists_keep_a_b_a_context; products/recipes: test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| PUT | `/api/meal-types/{meal_type_id}` | test_direct_edit_and_delete_contract |
| DELETE | `/api/meal-types/{meal_type_id}` | test_direct_edit_and_delete_contract; test_system_meal_deletion_checks_owner_before_system_flag |
| GET | `/api/meal-types/{meal_type_id}/usage` | test_additional_direct_operations |

## Проверка состояния

`database_snapshot` читает реальные таблицы, включая связи, через новую SQLAlchemy Session после каждой запрещённой записи. Из полного снимка исключены users и refresh_tokens. Профиль B дополнительно сравнивается через новую Session, включая хеш пароля, до повторных login. `user_data_snapshot` проверяет сохранность всех объектов B и их дочерних строк после разрешённых изменений A и смешанного batch; `persisted_owner` проверяет владельца после подстановки user_id.

## Границы

БД: отдельный SQLite-файл с production ORM-схемой и включёнными FK. PostgreSQL и сценарии личных категорий после TASK 4 этим набором не проверяются. Вложенные ссылки и вычисляемые результаты не дублируют TASK 2/3; соответствующие маршруты здесь покрыты JWT-проверками.


## Сопоставление требований TASK 1

| Требование | Проверки |
|---|---|
| 1. Два пользователя и настоящие токены | isolation_client, isolation_users; регистрация и login через API; имена A/B различимы |
| 2. Изолированная БД и настоящая схема | isolation_client: отдельный SQLite-файл, production lifespan/container, FK включены |
| 3. Матрица маршрутов | Таблица выше; вычисления и экспорт явно отнесены к TASK 3, категории — TASK 4 |
| 4. Владелец / другой пользователь в обе стороны | test_direct_edit_and_delete_contract, test_additional_direct_operations, test_menu_slot_writes_require_menu_owner; direction=0/1 |
| 5. Списки, поиск, фильтры, страницы и total | test_lists_keep_a_b_a_context, test_search_filter_pages_and_total, test_search_and_category_exclude_foreign_only_matches |
| 6. Подстановка user_id | test_forged_owner_is_ignored_on_create_and_update; все семь сущностей, новые Session, запрет передачи владельца при PUT; для меню PUT отсутствует |
| 7. Нет JWT / недействительный JWT | test_every_scoped_route_requires_valid_jwt; каждый метод и путь из OpenAPI в области матрицы |
| 8. Профиль и пароль | test_profile_and_password_only_change_current_user; API, свежая Session, старые/новые пароли обоих пользователей |
| 9. Контракты удаления | test_direct_edit_and_delete_contract; batch: own/foreign/missing/duplicate/mixed/empty и повтор запроса; recipe check_dependents 409; системные meal-types 403 |
| 10. Исправления через TDD | Production-код не меняется в тестовой фазе. RED фиксируется только при реальном нарушении требований |

Ограничение TASK 1: получение собственных категорий через API проверяется фикстурами; текущая глобальная модель категорий не трактуется как нарушение до TASK 4. Для списков без search/page/filter такие параметры не выдумываются: проверяются существующие контракты.
