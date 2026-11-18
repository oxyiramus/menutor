import csv
import io
import json

import pytest
from pypdf import PdfReader
from sqlalchemy import insert

from backend.infrastructure.database.models import RecipeIngredientRow
from tests.integration.api_isolation_helpers import (
    persisted_owner,
    request_ok,
    user_data_snapshot,
)

EXPORT_FORMATS = [
    ("products", "csv"),
    ("products", "json"),
    ("recipes", "csv"),
    ("recipes", "json"),
    ("recipes", "json_compact"),
    ("menus", "json"),
]
IMPORT_FORMATS = [(kind, fmt) for kind, fmt in EXPORT_FORMATS if fmt != "json_compact"]


def ingredient(field, entity_id):
    return {
        field: entity_id,
        "quantity_amount": 100 if field == "product_id" else 1,
        "quantity_unit": "g" if field == "product_id" else "serv",
    }


@pytest.fixture
def derived_users(isolation_users):
    client, users = isolation_users
    for index, user in enumerate(users, start=1):
        headers, objects, bodies = user["headers"], user["objects"], user["bodies"]
        product = objects["products"]
        recipe_id = objects["recipes"]["id"]
        request_ok(
            client,
            "PUT",
            f"products/{product['id']}",
            headers,
            dict(bodies["products"], price_amount=str(80 * index)),
        )
        request_ok(
            client,
            "PUT",
            f"recipes/{recipe_id}",
            headers,
            dict(
                bodies["recipes"], ingredients=[ingredient("product_id", product["id"])]
            ),
        )
        objects["parent"] = request_ok(
            client,
            "POST",
            "recipes",
            headers,
            dict(
                bodies["recipes"],
                name=f"{user['nickname']} Parent",
                ingredients=[ingredient("sub_recipe_id", recipe_id)],
            ),
            201,
        )
        request_ok(
            client,
            "POST",
            f"menus/{objects['menus']['id']}/slots",
            headers,
            {
                "day": 0,
                "meal_type_id": objects["meal-types"]["id"],
                "recipe_id": recipe_id,
            },
        )
        request_ok(
            client,
            "PUT",
            f"shopping-lists/{objects['shopping-lists']['id']}",
            headers,
            {
                "name": f"{user['nickname']} Shopping",
                "items": [
                    dict(
                        bodies["shopping-lists"]["items"][0],
                        product_name=f"{user['nickname']} Saved item",
                    )
                ],
            },
        )
    return client, users


def denied(client, method, path, actor, owner, body=None):
    response = client.request(
        method, f"/api/{path}", headers=actor["headers"], json=body
    )
    assert response.status_code == 404, response.text
    assert owner["nickname"] not in response.text
    assert "content-disposition" not in response.headers


def test_recipe_reads_are_scoped(derived_users):
    client, (alice, bob) = derived_users
    for actor, owner, expected_cost in ((alice, bob, 4), (bob, alice, 8)):
        headers, own, foreign = actor["headers"], actor["objects"], owner["objects"]
        path = f"recipes/{own['recipes']['id']}"
        foreign_path = f"recipes/{foreign['recipes']['id']}"
        assert (
            request_ok(client, "GET", path, headers)["cost_per_portion"]
            == expected_cost
        )
        denied(client, "GET", foreign_path, actor, owner)
        rows = request_ok(client, "GET", f"{path}/flattened-products", headers)
        assert [row["product_name"] for row in rows] == [own["products"]["name"]]
        denied(client, "GET", f"{foreign_path}/flattened-products", actor, owner)
        assert request_ok(client, "GET", f"{path}/dependents", headers) == [
            {"id": own["parent"]["id"], "name": own["parent"]["name"]}
        ]
        assert request_ok(client, "GET", f"{foreign_path}/dependents", headers) == []
        matches = request_ok(client, "GET", f"{path}/matching-preferences", headers)
        assert [pref["name"] for pref in matches["preferences"]] == [
            own["preferences"]["name"]
        ]
        assert request_ok(
            client, "GET", f"{foreign_path}/matching-preferences", headers
        ) == {"preferences": []}


@pytest.mark.parametrize(
    "field,kind", [("product_id", "products"), ("sub_recipe_id", "recipes")]
)
@pytest.mark.parametrize("preview", ["cost", "flattened"])
def test_previews_require_owned_ingredients(derived_users, field, kind, preview):
    client, (alice, bob) = derived_users
    own, foreign = alice["objects"], bob["objects"]
    path = (
        "recipes/cost-preview"
        if preview == "cost"
        else f"recipes/{own['parent']['id']}/flattened-products-preview"
    )
    body = {"servings": 1, "ingredients": [ingredient(field, own[kind]["id"])]}
    result = request_ok(client, "POST", path, alice["headers"], body)
    if preview == "cost":
        assert result["total_cost"] == (8 if field == "product_id" else 4)
        result = result["ingredient_costs"]
    assert [row["product_name"] for row in result] == [own["products"]["name"]]
    body["ingredients"].append(ingredient(field, foreign[kind]["id"]))
    denied(client, "POST", path, alice, bob, body)


def test_flattened_preview_path_requires_owner_and_supports_unsaved_recipe(
    derived_users,
):
    client, (alice, bob) = derived_users
    body = {
        "ingredients": [ingredient("product_id", alice["objects"]["products"]["id"])]
    }
    rows = request_ok(
        client, "POST", "recipes/0/flattened-products-preview", alice["headers"], body
    )
    assert rows[0]["product_name"] == alice["objects"]["products"]["name"]
    denied(
        client,
        "POST",
        f"recipes/{bob['objects']['recipes']['id']}/flattened-products-preview",
        alice,
        bob,
        body,
    )


@pytest.mark.parametrize("foreign_field", ["parent_recipe_id", "sub_recipe_id"])
def test_validate_subrecipe_checks_both_ids(derived_users, foreign_field):
    client, (alice, bob) = derived_users
    path = "recipes/validate-sub-recipe"
    body = {
        "parent_recipe_id": alice["objects"]["parent"]["id"],
        "sub_recipe_id": alice["objects"]["recipes"]["id"],
    }
    assert request_ok(client, "POST", path, alice["headers"], body) == {
        "valid": True,
        "error": None,
    }
    assert request_ok(
        client, "POST", path, alice["headers"], {"sub_recipe_id": body["sub_recipe_id"]}
    ) == {"valid": True, "error": None}
    missing = request_ok(
        client, "POST", path, alice["headers"], dict(body, sub_recipe_id=999999)
    )
    assert missing["valid"] is False
    assert (
        request_ok(
            client,
            "POST",
            path,
            alice["headers"],
            dict(body, **{foreign_field: bob["objects"]["recipes"]["id"]}),
        )
        == missing
    )


def test_menu_summary_and_meal_type_usage_are_scoped(derived_users):
    client, (alice, bob) = derived_users
    own, foreign = alice["objects"], bob["objects"]
    summary = request_ok(
        client, "GET", f"menus/{own['menus']['id']}/summary", alice["headers"]
    )
    assert summary["menu_name"] == own["menus"]["name"]
    assert (
        summary["recipes"][0]["ingredients"][0]["product_name"]
        == own["products"]["name"]
    )
    denied(client, "GET", f"menus/{foreign['menus']['id']}/summary", alice, bob)
    usage = request_ok(
        client, "GET", f"meal-types/{own['meal-types']['id']}/usage", alice["headers"]
    )
    assert own["menus"]["name"] in str(usage)
    assert bob["nickname"] not in str(usage)
    denied(client, "GET", f"meal-types/{foreign['meal-types']['id']}/usage", alice, bob)


@pytest.mark.parametrize(
    "kind,suffix,body,status",
    [
        ("menus", "copy", None, 201),
        ("shopping-lists", "copy", None, 201),
        ("menus", "shopping-list", None, 200),
        ("menus", "shopping-list/filtered", {"slot_indices": [0]}, 200),
    ],
)
def test_copy_and_generation_require_owner(derived_users, kind, suffix, body, status):
    client, (alice, bob) = derived_users
    own, foreign = alice["objects"], bob["objects"]
    before = [user_data_snapshot(user["id"]) for user in (alice, bob)]
    denied(client, "POST", f"{kind}/{foreign[kind]['id']}/{suffix}", alice, bob, body)
    assert [user_data_snapshot(user["id"]) for user in (alice, bob)] == before
    created = request_ok(
        client,
        "POST",
        f"{kind}/{own[kind]['id']}/{suffix}",
        alice["headers"],
        body,
        status,
    )
    if suffix.startswith("shopping-list"):
        assert created["source_menu_id"] == own[kind]["id"]
        assert [item["product_name"] for item in created["items"]] == [
            own["products"]["name"]
        ]
    elif kind == "menus":
        assert created["slots"][0]["recipe_id"] == own["recipes"]["id"]
    else:
        assert [item["product_name"] for item in created["items"]] == [
            "alice Saved item"
        ]


def recipe_links(row, fmt):
    ingredients = (
        json.loads(row["ingredients_json"]) if fmt == "csv" else row["ingredients"]
    )
    return [(item.get("product_id"), item.get("sub_recipe_id")) for item in ingredients]


@pytest.mark.parametrize("kind,fmt", EXPORT_FORMATS)
@pytest.mark.parametrize("selection", ["all", "foreign", "mixed"])
def test_entity_exports_filter_rows(derived_users, kind, fmt, selection):
    client, (alice, bob) = derived_users
    own, foreign = alice["objects"], bob["objects"]
    if kind == "menus":
        request_ok(
            client,
            "POST",
            f"menus/{own['menus']['id']}/slots",
            alice["headers"],
            {
                "day": 1,
                "meal_type_id": own["meal-types"]["id"],
                "product_id": own["products"]["id"],
                "quantity": 100,
                "unit": "g",
                "member_ids": [own["family-members"]["id"]],
            },
        )
    params = {}
    expected = [(own[kind]["id"], own[kind]["name"])]
    if selection == "foreign":
        params["ids"] = str(foreign[kind]["id"])
        expected = []
    elif selection == "mixed":
        params["ids"] = f"{foreign[kind]['id']},{own[kind]['id']}"
    elif kind == "recipes":
        expected.append((own["parent"]["id"], own["parent"]["name"]))
    response = client.get(
        f"/api/{kind}/export/{fmt}", headers=alice["headers"], params=params
    )
    assert response.status_code == 200, response.text
    extension = "csv" if fmt == "csv" else "json"
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="{kind}.{extension}"'
    )
    rows = (
        list(csv.DictReader(io.StringIO(response.text)))
        if fmt == "csv"
        else response.json()
    )
    assert sorted((int(row["id"]), row["name"]) for row in rows) == sorted(expected)
    assert bob["nickname"] not in response.text
    if kind == "recipes":
        expected_links = {
            own["recipes"]["id"]: (own["products"]["id"], None),
            own["parent"]["id"]: (None, own["recipes"]["id"]),
        }
        for row in rows:
            assert recipe_links(row, fmt) == [expected_links[int(row["id"])]]
    elif kind == "menus":
        for row in rows:
            assert [
                (
                    slot["recipe_id"],
                    slot["product_id"],
                    slot["meal_type_id"],
                    slot["member_ids"],
                )
                for slot in row["slots"]
            ] == [
                (own["recipes"]["id"], None, own["meal-types"]["id"], []),
                (
                    None,
                    own["products"]["id"],
                    own["meal-types"]["id"],
                    [own["family-members"]["id"]],
                ),
            ]


@pytest.mark.parametrize(
    "route,extension",
    [
        ("export/pdf", "pdf"),
        ("shopping-list/export/text", "txt"),
        ("shopping-list/export/csv", "csv"),
        ("shopping-list/export/json", "json"),
        ("shopping-list/export/pdf", "pdf"),
    ],
)
def test_menu_and_shopping_files_require_owner(derived_users, route, extension):
    client, (alice, bob) = derived_users
    own, foreign = alice["objects"], bob["objects"]
    denied(client, "POST", f"menus/{foreign['menus']['id']}/{route}", alice, bob)
    response = client.post(
        f"/api/menus/{own['menus']['id']}/{route}", headers=alice["headers"]
    )
    assert response.status_code == 200
    if extension == "pdf":
        content = "\n".join(
            page.extract_text()
            for page in PdfReader(io.BytesIO(response.content)).pages
        )
    else:
        content = response.text
    if route == "export/pdf":
        assert response.headers["content-disposition"] == (
            'attachment; filename="menu_alice_Private_menu.pdf"; '
            "filename*=UTF-8''menu_alice_Private_menu.pdf"
        )
        assert own["recipes"]["name"] in content
        assert own["meal-types"]["name"] in " ".join(content.split())
    else:
        assert (
            response.headers["content-disposition"]
            == f'attachment; filename="shopping_list.{extension}"'
        )
        assert own["products"]["name"] in content
    assert bob["nickname"] not in content


def import_rows(client, user, kind, fmt, rows):
    if fmt == "csv":
        output = io.StringIO()
        fields = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        content = output.getvalue()
    else:
        content = json.dumps(rows)
    return client.post(
        f"/api/{kind}/import/{fmt}",
        headers=user["headers"],
        files={"file": (f"upload.{fmt}", content.encode())},
    )


def export_row(client, user, kind, fmt):
    entity_id = user["objects"][kind]["id"]
    response = client.get(
        f"/api/{kind}/export/{fmt}", headers=user["headers"], params={"ids": entity_id}
    )
    assert response.status_code == 200
    if fmt == "csv":
        return next(csv.DictReader(io.StringIO(response.text)))
    return response.json()[0]


@pytest.mark.parametrize("kind,fmt", IMPORT_FORMATS)
def test_import_ignores_claimed_owner_and_foreign_id(derived_users, kind, fmt):
    client, (alice, bob) = derived_users
    foreign = bob["objects"][kind]
    row = export_row(client, alice, kind, fmt)
    row.update(name=foreign["name"], user_id=bob["id"])
    before = user_data_snapshot(bob["id"])
    for supplied_id, created, updated in (
        (foreign["id"], 1, 0),
        (alice["objects"][kind]["id"], 0, 1),
    ):
        # The second row uses a distinct name to avoid a same-owner collision.
        response = import_rows(client, alice, kind, fmt, [dict(row, id=supplied_id)])
        assert response.status_code == 200, response.text
        assert response.json() == {"created": created, "updated": updated, "errors": []}
        assert user_data_snapshot(bob["id"]) == before
        data = request_ok(client, "GET", kind, alice["headers"])
        data = data["items"] if kind != "menus" else data
        [imported] = [item for item in data if item["name"] == row["name"]]
        assert imported["id"] != foreign["id"]
        assert persisted_owner(kind, imported["id"]) == alice["id"]
        if updated:
            assert imported["id"] == supplied_id
        row["name"] = "Second imported record"


@pytest.mark.parametrize("kind,fmt", IMPORT_FORMATS)
def test_invalid_import_rolls_back_updates_and_creates(derived_users, kind, fmt):
    client, (alice, bob) = derived_users
    original = export_row(client, alice, kind, fmt)
    rows = [
        dict(original, name="Update to roll back"),
        dict(
            original,
            id=bob["objects"][kind]["id"],
            name="Create to roll back",
            user_id=bob["id"],
        ),
        {"name": ""},
    ]
    before = [user_data_snapshot(user["id"]) for user in (alice, bob)]
    response = import_rows(client, alice, kind, fmt, rows)
    assert response.status_code == 422, response.text
    failed_row = "Строка 4:" if fmt == "csv" else "Элемент 3:"
    assert response.json()["detail"].startswith(failed_row)
    assert bob["nickname"] not in response.text
    assert [user_data_snapshot(user["id"]) for user in (alice, bob)] == before


@pytest.mark.parametrize("fmt", ["json", "csv"])
@pytest.mark.parametrize(
    "field,kind", [("product_id", "products"), ("sub_recipe_id", "recipes")]
)
def test_recipe_import_does_not_link_foreign_ingredients(
    derived_users, fmt, field, kind
):
    client, (alice, bob) = derived_users
    original = export_row(client, alice, "recipes", fmt)
    before = [user_data_snapshot(user["id"]) for user in (alice, bob)]
    invalid = dict(original, id=0, name="Imported recipe")
    ingredients = [ingredient(field, bob["objects"][kind]["id"])]
    if fmt == "csv":
        invalid["ingredients_json"] = json.dumps(ingredients)
    else:
        invalid["ingredients"] = ingredients
    response = import_rows(client, alice, "recipes", fmt, [invalid])
    assert bob["nickname"] not in response.text
    assert user_data_snapshot(bob["id"]) == before[1]
    if field == "product_id":
        assert response.status_code == 422, response.text
        assert user_data_snapshot(alice["id"]) == before[0]
    else:
        # The recipe format treats unavailable sub-recipes as a nonfatal warning.
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["created"] == 1
        assert result["errors"]
        rows = request_ok(client, "GET", "recipes", alice["headers"])["items"]
        [recipe] = [row for row in rows if row["name"] == invalid["name"]]
        assert recipe["ingredients"] == []


@pytest.mark.parametrize(
    "field,kind",
    [
        ("product_id", "products"),
        ("recipe_id", "recipes"),
        ("meal_type_id", "meal-types"),
        ("member_ids", "family-members"),
    ],
)
def test_menu_import_rolls_back_on_foreign_slot_reference(derived_users, field, kind):
    client, (alice, bob) = derived_users
    original = export_row(client, alice, "menus", "json")
    slot = original["slots"][0].copy()
    foreign_id = bob["objects"][kind]["id"]
    slot[field] = [foreign_id] if field == "member_ids" else foreign_id
    if field == "product_id":
        slot.update(recipe_id=None, quantity=100, unit="g")
    before = [user_data_snapshot(user["id"]) for user in (alice, bob)]
    response = import_rows(
        client,
        alice,
        "menus",
        "json",
        [
            dict(original, name="Update to roll back"),
            dict(original, name="Rejected menu", id=0, slots=[slot]),
        ],
    )
    assert response.status_code == 422, response.text
    assert bob["nickname"] not in response.text
    assert [user_data_snapshot(user["id"]) for user in (alice, bob)] == before


def test_filtered_generation_ignores_foreign_exclusion_id(derived_users):
    client, (alice, bob) = derived_users
    own, foreign = alice["objects"], bob["objects"]
    path = f"menus/{own['menus']['id']}"
    request_ok(
        client,
        "POST",
        f"{path}/slots",
        alice["headers"],
        {
            "day": 1,
            "meal_type_id": own["meal-types"]["id"],
            "recipe_id": own["parent"]["id"],
        },
    )
    route = f"{path}/shopping-list/filtered"
    before = user_data_snapshot(bob["id"])
    result = request_ok(
        client,
        "POST",
        route,
        alice["headers"],
        {"slot_indices": [1], "excluded_sub_recipe_ids": [foreign["recipes"]["id"]]},
    )
    assert [item["product_name"] for item in result["items"]] == [
        own["products"]["name"]
    ]
    excluded = request_ok(
        client,
        "POST",
        route,
        alice["headers"],
        {"slot_indices": [1], "excluded_sub_recipe_ids": [own["recipes"]["id"]]},
    )
    assert excluded["items"] == []
    assert user_data_snapshot(bob["id"]) == before


@pytest.mark.parametrize("foreign_link", ["product_id", "sub_recipe_id"])
def test_derived_recipe_reads_skip_legacy_foreign_ingredient(
    derived_users, foreign_link
):
    client, (alice, bob) = derived_users
    own, foreign = alice["objects"], bob["objects"]
    headers = alice["headers"]
    kind = "products" if foreign_link == "product_id" else "recipes"
    # Reproduce a persisted row from before ownership was enforced on writes.
    with client.app.state.container._engine.begin() as connection:
        connection.execute(
            insert(RecipeIngredientRow).values(
                recipe_id=own["recipes"]["id"],
                **{foreign_link: foreign[kind]["id"]},
                amount=100,
                unit="g",
                ingredient_order=1,
            )
        )

    child = ingredient("sub_recipe_id", own["recipes"]["id"])
    parent_path = f"recipes/{own['parent']['id']}"
    before = user_data_snapshot(alice["id"])
    saved = request_ok(client, "GET", parent_path, headers)
    assert saved["cost_per_portion"] == 2
    saved_child = request_ok(client, "GET", f"recipes/{own['recipes']['id']}", headers)
    assert recipe_links(saved_child, "json") == [(own["products"]["id"], None)]
    for fmt in ("csv", "json", "json_compact"):
        row = export_row(client, alice, "recipes", fmt)
        assert recipe_links(row, fmt) == [(own["products"]["id"], None)]
    cost = request_ok(
        client,
        "POST",
        "recipes/cost-preview",
        headers,
        {"servings": 1, "ingredients": [child]},
    )
    assert cost["total_cost"] == 4
    assert [
        (row["product_id"], row["product_name"]) for row in cost["ingredient_costs"]
    ] == [(own["products"]["id"], own["products"]["name"])]

    for method, suffix, body in (
        ("GET", "flattened-products", None),
        ("POST", "flattened-products-preview", {"ingredients": [child]}),
    ):
        rows = request_ok(client, method, f"{parent_path}/{suffix}", headers, body)
        assert [(row["product_id"], row["product_name"]) for row in rows] == [
            (own["products"]["id"], own["products"]["name"])
        ]

    summary = request_ok(client, "GET", f"menus/{own['menus']['id']}/summary", headers)
    assert [row["product_id"] for row in summary["recipes"][0]["ingredients"]] == [
        own["products"]["id"]
    ]
    assert user_data_snapshot(alice["id"]) == before
