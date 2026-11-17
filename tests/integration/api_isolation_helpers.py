"""HTTP assertions shared by isolation fixtures and tests."""


def request_ok(client, method, path, headers, body=None, status=200):
    response = client.request(method, f"/api/{path}", headers=headers, json=body)
    assert response.status_code == status, response.text
    return response.json() if response.content else None


TABLES = {
    "products": "products",
    "recipes": "recipes",
    "menus": "menus",
    "family-members": "family_members",
    "preferences": "preferences",
    "meal-types": "meal_types",
    "shopping-lists": "shopping_lists",
}


def user_data_snapshot(user_id):
    """Read one user's persisted entities and their child/link rows independently."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from backend.api.main import app
    from backend.infrastructure.database.models import Base

    tables = Base.metadata.tables
    with Session(app.state.container._engine) as session:
        result = {}
        for name in TABLES.values():
            table = tables[name]
            result[name] = sorted(
                (
                    tuple(row)
                    for row in session.execute(
                        select(table).where(table.c.user_id == user_id)
                    )
                ),
                key=repr,
            )
        for child, parent, fk in (
            ("recipe_ingredients", "recipes", "recipe_id"),
            ("cooking_steps", "recipes", "recipe_id"),
            ("menu_slots", "menus", "menu_id"),
            ("shopping_list_items", "shopping_lists", "shopping_list_id"),
            ("preference_categories", "preferences", "preference_id"),
            ("preference_products", "preferences", "preference_id"),
            ("preference_recipe_categories", "preferences", "preference_id"),
            ("family_member_preferences", "family_members", "family_member_id"),
        ):
            table, owner_table = tables[child], tables[parent]
            ids = select(owner_table.c.id).where(owner_table.c.user_id == user_id)
            result[child] = sorted(
                (
                    tuple(row)
                    for row in session.execute(
                        select(table).where(table.c[fk].in_(ids))
                    )
                ),
                key=repr,
            )
        return result


def persisted_owner(kind, entity_id):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from backend.api.main import app
    from backend.infrastructure.database.models import Base

    table = Base.metadata.tables[TABLES[kind]]
    with Session(app.state.container._engine) as session:
        return session.execute(
            select(table.c.user_id).where(table.c.id == entity_id)
        ).scalar_one()
