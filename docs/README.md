# Menutor

![Версия](https://img.shields.io/badge/version-0.15.2-green.svg)
![Лицензия](https://img.shields.io/badge/license-GPL--3.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.14%2B-blue.svg)

Menutor — веб-приложение для планирования семейного меню, хранения рецептов и составления списков покупок.

## Цель проекта

Помочь семье заранее решить, что готовить, сколько продуктов понадобится и во сколько обойдутся покупки. Одно меню можно использовать для планирования порций, подготовки к готовке и закупки.

## Технологии

- **Интерфейс** — Vue 3, TypeScript, Pinia, Vue Router, Tailwind CSS 4.
- **Backend** — Python 3.14+, FastAPI, Pydantic, SQLAlchemy, Alembic.
- **Хранение и развёртывание** — PostgreSQL, SQLite, Docker Compose и Nginx.
- **Аутентификация и отчёты** — PyJWT, bcrypt, ReportLab.
- **Проверки** — pytest, Vitest, vue-tsc.

## Архитектура

Браузерный интерфейс обращается к FastAPI. Прикладной слой связывает доменные правила с хранением данных и экспортом. [Схема и границы слоёв](architecture.md).

## Документация

- [Разработка, развёртывание и тесты](CONTRIBUTIND.md)
- [История изменений](CHANGELOG.md)
- [Руководство пользователя](user_guide.md)
- [Дорожная карта](roadmap.md)
- [Контекст для AI-агентов](AGENTS.md)

## Возможности

- [Аккаунт и сессия](features/accounts.md)
- [Каталог продуктов](features/products.md)
- [Каталог рецептов](features/recipes.md)
- [Категории и цветовая маркировка](features/categories.md)
- [Вложенные рецепты](features/nested-recipes.md)
- [Штучные рецепты](features/piece-based-recipes.md)
- [Стоимость порции](features/recipe-cost.md)
- [Планировщик меню](features/menu-planning.md)
- [Типы приёмов пищи](features/meal-types.md)
- [Семья и индивидуальное планирование](features/individual-planning.md)
- [Пищевые предпочтения](features/dietary-preferences.md)
- [Сводка блюд и план приготовления](features/meal-summary.md)
- [Списки покупок](features/shopping-lists.md)
- [Импорт и экспорт](features/data-exchange.md)

## Лицензия и обратная связь

Проект распространяется по [GNU GPL v3.0](../LICENSE). Ошибки и предложения можно оставлять в [GitHub Issues](https://github.com/zhdanovaekaterina/menutor/issues).
