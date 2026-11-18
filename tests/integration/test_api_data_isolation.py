"""TASK 1: direct HTTP ownership contracts, using the production application."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.main import app
from backend.infrastructure.database.models import Base
from tests.integration.api_isolation_helpers import request_ok, user_data_snapshot

KINDS = (
    "products",
    "recipes",
    "menus",
    "family-members",
    "preferences",
    "meal-types",
    "shopping-lists",
)


def database_snapshot():
    # A fresh session avoids accepting stale identity-map objects as evidence.
    with Session(app.state.container._engine) as session:
        return {
            table.name: sorted(
                (tuple(row) for row in session.execute(select(table))), key=repr
            )
            for table in Base.metadata.sorted_tables
            if table.name not in {"users", "refresh_tokens"}
        }


@pytest.mark.parametrize("direction", [0, 1])
@pytest.mark.parametrize("kind", KINDS)
def test_direct_edit_and_delete_contract(isolation_users, direction, kind):
    client, users = isolation_users
    owner, other = users[direction], users[1 - direction]
    entity = owner["objects"][kind]
    path = f"{kind}/{entity['id']}"
    if kind == "recipes":
        owner["bodies"][kind]["ingredients"] = [
            {
                "product_id": owner["objects"]["products"]["id"],
                "quantity_amount": 100,
                "quantity_unit": "g",
            }
        ]
        request_ok(client, "PUT", path, owner["headers"], owner["bodies"][kind])
    elif kind == "menus":
        request_ok(
            client,
            "POST",
            path + "/slots",
            owner["headers"],
            {
                "day": 0,
                "meal_type_id": owner["objects"]["meal-types"]["id"],
                "recipe_id": owner["objects"]["recipes"]["id"],
                "member_ids": [owner["objects"]["family-members"]["id"]],
            },
        )
    if kind in {"recipes", "menus", "preferences", "shopping-lists"}:
        assert request_ok(client, "GET", path, owner["headers"])["id"] == entity["id"]
        request_ok(client, "GET", path, other["headers"], status=404)
    if kind != "menus":
        body = dict(owner["bodies"][kind], name="Edited", user_id=other["id"])
        before = database_snapshot()
        request_ok(client, "PUT", path, other["headers"], body, 404)
        assert database_snapshot() == before
        request_ok(client, "PUT", path, owner["headers"], body)
        # Forged user_id must not transfer ownership.
        rows = request_ok(client, "GET", kind, owner["headers"])
        rows = rows["items"] if isinstance(rows, dict) else rows
        assert entity["id"] in {row["id"] for row in rows}
    before = database_snapshot()
    other_before = user_data_snapshot(other["id"])
    expected = 404 if kind == "meal-types" else 204
    request_ok(client, "DELETE", path, other["headers"], status=expected)
    assert database_snapshot() == before
    request_ok(client, "DELETE", f"{kind}/99999999", other["headers"], status=expected)
    request_ok(client, "DELETE", path, owner["headers"], status=204)
    assert user_data_snapshot(other["id"]) == other_before
    request_ok(client, "DELETE", path, owner["headers"], status=expected)
    assert user_data_snapshot(other["id"]) == other_before
    rows = request_ok(client, "GET", kind, owner["headers"])
    rows = rows["items"] if isinstance(rows, dict) else rows
    assert entity["id"] not in {row["id"] for row in rows}


@pytest.mark.parametrize("kind", KINDS)
def test_lists_keep_a_b_a_context(isolation_users, kind):
    client, users = isolation_users
    results = []
    for current, foreign in (
        (users[0], users[1]),
        (users[1], users[0]),
        (users[0], users[1]),
    ):
        result = request_ok(client, "GET", kind, current["headers"])
        rows = result["items"] if isinstance(result, dict) else result
        ids = {row["id"] for row in rows}
        if isinstance(result, dict):
            assert result["total"] == len(rows)
        assert current["objects"][kind]["id"] in ids
        assert foreign["objects"][kind]["id"] not in ids
        results.append(result)
    assert results[0] == results[2]
    a_rows = results[0]["items"] if isinstance(results[0], dict) else results[0]
    b_rows = results[1]["items"] if isinstance(results[1], dict) else results[1]
    assert {row["id"] for row in a_rows}.isdisjoint(row["id"] for row in b_rows)


@pytest.mark.parametrize("direction", [0, 1])
@pytest.mark.parametrize("kind", ["products", "recipes"])
def test_batch_only_removes_owned_ids(isolation_users, direction, kind):
    client, users = isolation_users
    owner, other = users[direction], users[1 - direction]
    own_id, foreign_id = owner["objects"][kind]["id"], other["objects"][kind]["id"]
    before = request_ok(client, "GET", kind, other["headers"])
    request_ok(
        client,
        "POST",
        f"{kind}/batch-delete",
        owner["headers"],
        [foreign_id, 99999999, foreign_id],
        204,
    )
    snapshot = database_snapshot()
    request_ok(
        client,
        "POST",
        f"{kind}/batch-delete",
        owner["headers"],
        [own_id, foreign_id, 99999999, own_id],
        204,
    )
    assert request_ok(client, "GET", kind, other["headers"]) == before
    assert own_id not in {
        row["id"] for row in request_ok(client, "GET", kind, owner["headers"])["items"]
    }
    # Every table unrelated to the removed entity must remain unchanged.
    after = database_snapshot()
    excluded = (
        {"products"}
        if kind == "products"
        else {"recipes", "recipe_ingredients", "cooking_steps"}
    )
    assert {k: v for k, v in snapshot.items() if k not in excluded} == {
        k: v for k, v in after.items() if k not in excluded
    }


@pytest.mark.parametrize("direction", [0, 1])
@pytest.mark.parametrize("kind", ["products", "recipes"])
def test_search_filter_pages_and_total(isolation_users, direction, kind):
    from backend.application.paginated_result import PAGE_SIZE

    client, users = isolation_users
    own, foreign = users[direction], users[1 - direction]
    expected = []
    for i in range(PAGE_SIZE + 1):
        body = dict(own["bodies"][kind], name=f"Needle {i:04}")
        expected.append(
            request_ok(client, "POST", kind, own["headers"], body, 201)["id"]
        )
    request_ok(
        client,
        "POST",
        kind,
        foreign["headers"],
        dict(foreign["bodies"][kind], name="Needle foreign"),
        201,
    )
    found = []
    for page, count in ((1, PAGE_SIZE), (2, 1), (3, 0)):
        result = request_ok(
            client,
            "GET",
            f"{kind}?page={page}&search=NEEDLE&category_id={own['bodies'][kind]['category_id']}",
            own["headers"],
        )
        assert result["total"] == PAGE_SIZE + 1
        assert len(result["items"]) == count
        found.extend(row["id"] for row in result["items"])
    assert found == expected


# Method/path matrix also guards every scoped operation against missing/bad JWTs.
SCOPED_PATHS = {
    path: operations
    for path, operations in app.openapi()["paths"].items()
    if any(path.startswith(f"/api/{kind}") for kind in KINDS)
    or path.startswith("/api/auth/me")
}
AUTH_MATRIX = [
    (method, path) for path, operations in SCOPED_PATHS.items() for method in operations
]


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
@pytest.mark.parametrize("method,path", AUTH_MATRIX)
def test_every_scoped_route_requires_valid_jwt(isolation_client, method, path, headers):
    import re

    path = re.sub(r"\{[^}]+\}", "1", path)
    response = isolation_client.request(method, path, headers=headers, json={})
    assert response.status_code == 401, response.text


@pytest.mark.parametrize("direction", [0, 1])
def test_profile_and_password_only_change_current_user(isolation_users, direction):
    client, users = isolation_users
    own, other = users[direction], users[1 - direction]
    user_table = Base.metadata.tables["users"]
    with Session(app.state.container._engine) as session:
        other_before = tuple(
            session.execute(
                select(user_table).where(user_table.c.id == other["id"])
            ).one()
        )
    profile_fields = ("id", "email", "nickname")
    for user in (own, other, own):
        profile = request_ok(client, "GET", "auth/me", user["headers"])
        assert {field: profile[field] for field in profile_fields} == {
            field: user[field] for field in profile_fields
        }
    result = request_ok(
        client,
        "PATCH",
        "auth/me",
        own["headers"],
        {"nickname": "Changed", "user_id": other["id"]},
    )
    assert result["id"] == own["id"] and result["nickname"] == "Changed"
    request_ok(
        client,
        "POST",
        "auth/me/password",
        own["headers"],
        {
            "current_password": "Password123!",
            "new_password": "NewPassword456!",
            "user_id": other["id"],
        },
        204,
    )
    for user, nickname in ((own, "Changed"), (other, other["nickname"])):
        profile = request_ok(client, "GET", "auth/me", user["headers"])
        assert {field: profile[field] for field in profile_fields} == {
            "id": user["id"],
            "email": user["email"],
            "nickname": nickname,
        }
    with Session(app.state.container._engine) as session:
        assert (
            tuple(
                session.execute(
                    select(user_table).where(user_table.c.id == other["id"])
                ).one()
            )
            == other_before
        )
    for user, password, expected in (
        (own, "Password123!", 401),
        (own, "NewPassword456!", 200),
        (other, "Password123!", 200),
        (other, "NewPassword456!", 401),
    ):
        request_ok(
            client,
            "POST",
            "auth/login",
            {},
            {"email": user["email"], "password": password},
            expected,
        )


EXTRA_OPERATIONS = [
    ("products", "PATCH", "/price", {"amount": "99", "currency": "RUB"}, 200),
    ("recipes", "GET", "/dependents", None, 200),
    ("recipes", "GET", "/matching-preferences", None, 200),
    ("meal-types", "GET", "/usage", None, 200),
    ("menus", "POST", "/clear", None, 200),
    ("menus", "POST", "/copy", None, 201),
    ("shopping-lists", "PATCH", "", {"name": "Renamed"}, 200),
    ("shopping-lists", "POST", "/copy", None, 201),
    ("shopping-lists", "POST", "/items/{item_id}/toggle-purchased", None, 200),
]


@pytest.mark.parametrize("direction", [0, 1])
@pytest.mark.parametrize("kind,method,suffix,body,success", EXTRA_OPERATIONS)
def test_additional_direct_operations(
    isolation_users, direction, kind, method, suffix, body, success
):
    client, users = isolation_users
    own, foreign = users[direction], users[1 - direction]
    entity = own["objects"][kind]
    if kind == "menus" or suffix == "/usage":
        request_ok(
            client,
            "POST",
            f"menus/{own['objects']['menus']['id']}/slots",
            own["headers"],
            {
                "day": 0,
                "meal_type_id": own["objects"]["meal-types"]["id"],
                "recipe_id": own["objects"]["recipes"]["id"],
                "member_ids": [own["objects"]["family-members"]["id"]],
            },
        )
    if suffix == "/dependents":
        parent = request_ok(
            client,
            "POST",
            "recipes",
            own["headers"],
            dict(
                own["bodies"]["recipes"],
                name="Parent",
                ingredients=[
                    {
                        "sub_recipe_id": entity["id"],
                        "quantity_amount": 1,
                        "quantity_unit": "serv",
                    }
                ],
            ),
            201,
        )
    if "{item_id}" in suffix:
        suffix = suffix.format(item_id=entity["items"][0]["id"])
    path = f"{kind}/{entity['id']}{suffix}"
    before = database_snapshot()
    # Dependents intentionally hides inaccessible recipes as an empty list.
    if kind == "recipes":
        expected = [] if suffix == "/dependents" else {"preferences": []}
        assert request_ok(client, method, path, foreign["headers"], body) == expected
    else:
        request_ok(client, method, path, foreign["headers"], body, 404)
    assert database_snapshot() == before
    before_other = user_data_snapshot(foreign["id"])
    result = request_ok(client, method, path, own["headers"], body, success)
    assert user_data_snapshot(foreign["id"]) == before_other
    if suffix == "/price":
        assert float(result["price_amount"]) == 99
    elif suffix == "/copy":
        assert result["id"] != entity["id"]
        if kind == "shopping-lists":
            assert (
                result["items"][0]["product_name"] == entity["items"][0]["product_name"]
            )
        else:
            assert result["slots"][0]["recipe_id"] == own["objects"]["recipes"]["id"]
    elif method == "PATCH":
        assert result["name"] == "Renamed"
    elif "toggle-purchased" in suffix:
        assert result["items"][0]["purchased"] is True
    elif suffix == "/clear":
        assert result["slots"] == []
    elif suffix == "/usage":
        assert result["count"] == 1
        assert result["menus"] == [
            {
                "id": own["objects"]["menus"]["id"],
                "name": own["objects"]["menus"]["name"],
            }
        ]
    elif suffix == "/dependents":
        assert result == [{"id": parent["id"], "name": "Parent"}]
    elif suffix == "/matching-preferences":
        assert {row["id"] for row in result["preferences"]} == {
            own["objects"]["preferences"]["id"]
        }


@pytest.mark.parametrize("direction", [0, 1])
@pytest.mark.parametrize("operation", ["add", "move", "remove"])
def test_menu_slot_writes_require_menu_owner(isolation_users, direction, operation):
    client, users = isolation_users
    own, other = users[direction], users[1 - direction]
    menu_id = own["objects"]["menus"]["id"]
    slot = {
        "day": 0,
        "meal_type_id": own["objects"]["meal-types"]["id"],
        "recipe_id": own["objects"]["recipes"]["id"],
        "member_ids": [own["objects"]["family-members"]["id"]],
    }
    path = f"menus/{menu_id}/slots"
    request_ok(client, "POST", path, own["headers"], slot)
    method, body = "POST", slot
    if operation == "move":
        path += "/move"
        body = dict(slot, to_day=1, to_meal_type_id=slot["meal_type_id"])
    elif operation == "remove":
        method = "DELETE"
    else:
        body = dict(slot, day=2)
    before = database_snapshot()
    request_ok(client, method, path, other["headers"], body, 404)
    assert database_snapshot() == before
    response = request_ok(client, method, path, own["headers"], body)
    assert len(response["slots"]) == (
        0 if operation == "remove" else 2 if operation == "add" else 1
    )


@pytest.mark.parametrize("direction", [0, 1])
@pytest.mark.parametrize("kind", KINDS)
def test_forged_owner_is_ignored_on_create_and_update(isolation_users, direction, kind):
    from tests.integration.api_isolation_helpers import (
        persisted_owner,
        user_data_snapshot,
    )

    client, users = isolation_users
    own, other = users[direction], users[1 - direction]
    entity_id = own["objects"][kind]["id"]
    # The fixture sent the other user's ID during each creation.
    assert persisted_owner(kind, entity_id) == own["id"]
    before = user_data_snapshot(other["id"])
    if kind != "menus":  # There is no menu update route.
        result = request_ok(
            client,
            "PUT",
            f"{kind}/{entity_id}",
            own["headers"],
            dict(own["bodies"][kind], name="Retained ownership", user_id=other["id"]),
        )
        assert result["name"] == "Retained ownership"
        assert persisted_owner(kind, entity_id) == own["id"]
    assert user_data_snapshot(other["id"]) == before
    other_rows = request_ok(client, "GET", kind, other["headers"])
    other_rows = other_rows["items"] if isinstance(other_rows, dict) else other_rows
    assert entity_id not in {row["id"] for row in other_rows}


@pytest.mark.parametrize("direction", [0, 1])
@pytest.mark.parametrize("kind", ["products", "recipes"])
@pytest.mark.parametrize(
    "scenario", ["own", "foreign", "missing", "duplicate", "mixed", "empty"]
)
def test_batch_id_combinations_and_retry(isolation_users, direction, kind, scenario):
    from tests.integration.api_isolation_helpers import user_data_snapshot

    client, users = isolation_users
    own, other = users[direction], users[1 - direction]
    own_id, other_id = own["objects"][kind]["id"], other["objects"][kind]["id"]
    ids = {
        "own": [own_id],
        "foreign": [other_id],
        "missing": [99999999],
        "duplicate": [own_id, own_id],
        "mixed": [other_id, own_id, 99999999, other_id, own_id],
        "empty": [],
    }[scenario]
    request_ok(
        client,
        "PUT",
        f"recipes/{other['objects']['recipes']['id']}",
        other["headers"],
        dict(
            other["bodies"]["recipes"],
            ingredients=[
                {
                    "product_id": other["objects"]["products"]["id"],
                    "quantity_amount": 50,
                    "quantity_unit": "g",
                }
            ],
            steps=[{"order": 0, "description": "Private preparation"}],
        ),
    )
    request_ok(
        client,
        "PUT",
        f"preferences/{other['objects']['preferences']['id']}",
        other["headers"],
        dict(
            other["bodies"]["preferences"],
            product_ids=[other["objects"]["products"]["id"]],
        ),
    )
    before_other = user_data_snapshot(other["id"])
    before_all = database_snapshot()
    request_ok(client, "POST", f"{kind}/batch-delete", own["headers"], ids, 204)
    assert user_data_snapshot(other["id"]) == before_other
    if own_id not in ids:
        assert database_snapshot() == before_all
    rows = request_ok(client, "GET", kind, own["headers"])["items"]
    assert (own_id in {row["id"] for row in rows}) == (own_id not in ids)
    after_first = database_snapshot()
    request_ok(client, "POST", f"{kind}/batch-delete", own["headers"], ids, 204)
    assert database_snapshot() == after_first


@pytest.mark.parametrize("direction", [0, 1])
@pytest.mark.parametrize("kind", ["products", "recipes"])
def test_search_and_category_exclude_foreign_only_matches(
    isolation_users, direction, kind
):
    client, users = isolation_users
    own, other = users[direction], users[1 - direction]
    category_route = "product-categories" if kind == "products" else "recipe-categories"
    categories = request_ok(client, "GET", category_route, own["headers"])
    first = own["bodies"][kind]["category_id"]
    second = next(row["id"] for row in categories if row["id"] != first)
    visible = request_ok(
        client,
        "POST",
        kind,
        own["headers"],
        dict(own["bodies"][kind], name="Visible marker"),
        201,
    )
    off_category = request_ok(
        client,
        "POST",
        kind,
        own["headers"],
        dict(own["bodies"][kind], name="Visible elsewhere", category_id=second),
        201,
    )
    foreign_category = request_ok(client, "GET", category_route, other["headers"])[1][
        "id"
    ]
    request_ok(
        client,
        "POST",
        kind,
        other["headers"],
        dict(
            other["bodies"][kind],
            name="Foreign unique marker",
            category_id=foreign_category,
        ),
        201,
    )
    queries = [
        ("page=1&search=foreign%20unique", set()),
        (f"page=1&search=visible&category_id={first}", {visible["id"]}),
        (f"page=1&search=visible&category_id={second}", {off_category["id"]}),
        (f"page=1&search=no-match&category_id={second}", set()),
        (f"category_id={second}", {off_category["id"]}),
        ("page=1&search=visible", {visible["id"], off_category["id"]}),
    ]
    for query, expected in queries:
        response = request_ok(client, "GET", f"{kind}?{query}", own["headers"])
        assert {row["id"] for row in response["items"]} == expected
        assert response["total"] == len(expected)


@pytest.mark.parametrize("direction", [0, 1])
def test_recipe_deletion_preserves_dependency_contract(isolation_users, direction):
    client, users = isolation_users
    own, other = users[direction], users[1 - direction]
    recipe_id = own["objects"]["recipes"]["id"]
    parent = request_ok(
        client,
        "POST",
        "recipes",
        own["headers"],
        dict(
            own["bodies"]["recipes"],
            name="Dependent parent",
            ingredients=[
                {
                    "sub_recipe_id": recipe_id,
                    "quantity_amount": 1,
                    "quantity_unit": "serv",
                }
            ],
        ),
        201,
    )
    before = database_snapshot()
    request_ok(
        client,
        "DELETE",
        f"recipes/{recipe_id}?check_dependents=true",
        other["headers"],
        status=204,
    )
    assert database_snapshot() == before
    response = request_ok(
        client,
        "DELETE",
        f"recipes/{recipe_id}?check_dependents=true",
        own["headers"],
        status=409,
    )
    assert response["dependents"] == [{"id": parent["id"], "name": parent["name"]}]
    assert database_snapshot() == before
    other_before = user_data_snapshot(other["id"])
    request_ok(client, "DELETE", f"recipes/{recipe_id}", own["headers"], status=204)
    assert (
        request_ok(client, "GET", f"recipes/{parent['id']}", own["headers"])[
            "ingredients"
        ]
        == []
    )
    assert user_data_snapshot(other["id"]) == other_before


@pytest.mark.parametrize("direction", [0, 1])
def test_system_meal_deletion_checks_owner_before_system_flag(
    isolation_users, direction
):
    client, users = isolation_users
    own, other = users[direction], users[1 - direction]
    meals = request_ok(client, "GET", "meal-types", own["headers"])
    meal_id = next(row["id"] for row in meals if row["is_system"])
    before = database_snapshot()
    request_ok(client, "DELETE", f"meal-types/{meal_id}", other["headers"], status=404)
    assert database_snapshot() == before
    request_ok(client, "DELETE", f"meal-types/{meal_id}", own["headers"], status=403)
    assert database_snapshot() == before
