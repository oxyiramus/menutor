"""Related-reference ownership through real HTTP/JWT and fresh DB sessions."""

import pytest

from tests.integration.api_isolation_helpers import request_ok, user_data_snapshot


def snapshots(users):
    return [user_data_snapshot(user["id"]) for user in users]


@pytest.mark.parametrize("direction", [0, 1])
@pytest.mark.parametrize(
    "kind,reference",
    [
        ("preferences", "product_id"),
        ("recipes", "product_id"),
        ("recipes", "sub_recipe_id"),
        ("family-members", "preference_id"),
    ],
)
@pytest.mark.parametrize("method", ["POST", "PUT"])
@pytest.mark.parametrize("mixed", [False, True])
def test_related_references_are_atomic(
    isolation_users, direction, kind, reference, method, mixed
):
    client, users = isolation_users
    own, other = users[direction], users[1 - direction]
    target = {
        "product_id": "products",
        "sub_recipe_id": "recipes",
        "preference_id": "preferences",
    }[reference]
    own_id = own["objects"][target]["id"]
    foreign_id = other["objects"][target]["id"]
    if reference == "sub_recipe_id":
        own_id = request_ok(
            client,
            "POST",
            "recipes",
            own["headers"],
            dict(own["bodies"]["recipes"], name="Owned child"),
            201,
        )["id"]
    path = kind if method == "POST" else f"{kind}/{own['objects'][kind]['id']}"

    def body(ids):
        data = dict(own["bodies"][kind], name="Changed aggregate")
        if kind == "recipes":
            data["ingredients"] = [
                {
                    reference: id_,
                    "quantity_amount": 1,
                    "quantity_unit": "serv" if reference == "sub_recipe_id" else "g",
                }
                for id_ in ids
            ]
            data["steps"] = [{"order": 0, "description": "Changed preparation"}]
        else:
            data["product_ids" if kind == "preferences" else "preference_ids"] = ids
        return data

    # Establish real existing links before testing a rejected replacement.
    if method == "PUT":
        request_ok(client, "PUT", path, own["headers"], body([own_id]))
    before = snapshots(users)
    request_ok(
        client,
        method,
        path,
        own["headers"],
        body([own_id, foreign_id] if mixed else [foreign_id]),
        404,
    )
    assert snapshots(users) == before
    # A valid retry must work even immediately after the rejected request.
    result = request_ok(
        client,
        method,
        path,
        own["headers"],
        body([own_id]),
        201 if method == "POST" else 200,
    )
    assert result["name"] == "Changed aggregate"
    if kind == "recipes":
        assert [item[reference] for item in result["ingredients"]] == [own_id]
        assert result["steps"][0]["description"] == "Changed preparation"
    else:
        field = "product_ids" if kind == "preferences" else "preference_ids"
        assert result[field] == [own_id]
    assert user_data_snapshot(other["id"]) == before[1 - direction]


@pytest.mark.parametrize("direction", [0, 1])
@pytest.mark.parametrize(
    "reference", ["recipe_id", "product_id", "meal_type_id", "member_ids"]
)
@pytest.mark.parametrize("mixed", [False, True])
def test_menu_rejects_foreign_references(isolation_users, direction, reference, mixed):
    client, users = isolation_users
    own, other = users[direction], users[1 - direction]
    path = f"menus/{own['objects']['menus']['id']}/slots"
    slot = {
        "day": 0,
        "meal_type_id": own["objects"]["meal-types"]["id"],
        "recipe_id": own["objects"]["recipes"]["id"],
        "member_ids": [own["objects"]["family-members"]["id"]],
    }
    request_ok(client, "POST", path, own["headers"], slot)
    before = snapshots(users)
    bad = dict(slot, day=1)
    kind = {
        "recipe_id": "recipes",
        "product_id": "products",
        "meal_type_id": "meal-types",
        "member_ids": "family-members",
    }[reference]
    foreign_id = other["objects"][kind]["id"]
    if reference == "product_id":
        bad.pop("recipe_id")
        bad.update(quantity=1, unit="g")
    bad[reference] = (
        ([*slot["member_ids"], foreign_id] if mixed else [foreign_id])
        if reference == "member_ids"
        else foreign_id
    )
    request_ok(client, "POST", path, own["headers"], bad, 404)
    assert snapshots(users) == before
    valid = dict(bad)
    valid[reference] = (
        [own["objects"][kind]["id"]]
        if reference == "member_ids"
        else own["objects"][kind]["id"]
    )
    result = request_ok(client, "POST", path, own["headers"], valid)
    assert len(result["slots"]) == 2
    assert any(
        item[reference] == valid[reference] and item["day"] == 1
        for item in result["slots"]
    )
    assert user_data_snapshot(other["id"]) == before[1 - direction]


@pytest.mark.parametrize("direction", [0, 1])
@pytest.mark.parametrize(
    "operation,reference",
    [
        (operation, reference)
        for operation in ("move", "remove")
        for reference in ("recipe_id", "product_id", "meal_type_id", "to_meal_type_id")
        if operation == "move" or reference != "to_meal_type_id"
    ],
)
def test_menu_move_and_remove_foreign_selectors(
    isolation_users, direction, operation, reference
):
    client, users = isolation_users
    own, other = users[direction], users[1 - direction]
    path = f"menus/{own['objects']['menus']['id']}/slots"
    slot = {
        "day": 0,
        "meal_type_id": own["objects"]["meal-types"]["id"],
        "recipe_id": own["objects"]["recipes"]["id"],
    }
    request_ok(client, "POST", path, own["headers"], slot)
    body = dict(slot)
    if operation == "move":
        body.update(to_day=1, to_meal_type_id=slot["meal_type_id"])
    kind = (
        "meal-types"
        if "meal_type" in reference
        else "products" if reference == "product_id" else "recipes"
    )
    if reference == "product_id":
        body.pop("recipe_id")
    body[reference] = other["objects"][kind]["id"]
    before = snapshots(users)
    # Unknown removal selectors are deliberately ignored; a move needs a source.
    expected = (
        200 if operation == "remove" else 404 if reference == "to_meal_type_id" else 422
    )
    request_ok(
        client,
        "DELETE" if operation == "remove" else "POST",
        path if operation == "remove" else path + "/move",
        own["headers"],
        body,
        expected,
    )
    after = snapshots(users)
    if operation == "remove":
        # Successful saves replace slot rows; their surrogate IDs are private.
        # Compare every persisted slot field and relation, excluding only its PK.
        for state in (before[direction], after[direction]):
            state["menu_slots"] = sorted(
                (row[1:] for row in state["menu_slots"]), key=repr
            )
    assert after == before


@pytest.mark.parametrize("direction", [0, 1])
def test_nested_shopping_items_are_scoped_to_list(isolation_users, direction):
    client, users = isolation_users
    own, other = users[direction], users[1 - direction]
    own_list = own["objects"]["shopping-lists"]
    foreign_list = other["objects"]["shopping-lists"]
    second = request_ok(
        client,
        "POST",
        f"shopping-lists/{own_list['id']}/copy",
        own["headers"],
        status=201,
    )
    before = snapshots(users)
    for list_id, item_id in [
        (foreign_list["id"], foreign_list["items"][0]["id"]),
        (own_list["id"], foreign_list["items"][0]["id"]),
        (own_list["id"], second["items"][0]["id"]),
    ]:
        request_ok(
            client,
            "POST",
            f"shopping-lists/{list_id}/items/{item_id}/toggle-purchased",
            own["headers"],
            status=404,
        )
        assert snapshots(users) == before
    result = request_ok(
        client,
        "POST",
        f"shopping-lists/{own_list['id']}/items/{own_list['items'][0]['id']}/toggle-purchased",
        own["headers"],
    )
    assert result["items"][0]["purchased"] is True
    assert user_data_snapshot(other["id"]) == before[1 - direction]


@pytest.mark.parametrize("direction", [0, 1])
def test_assigning_preferences_requires_member_owner(isolation_users, direction):
    client, users = isolation_users
    own, other = users[direction], users[1 - direction]
    before = snapshots(users)
    request_ok(
        client,
        "PUT",
        f"family-members/{other['objects']['family-members']['id']}",
        own["headers"],
        dict(
            own["bodies"]["family-members"],
            preference_ids=[own["objects"]["preferences"]["id"]],
        ),
        404,
    )
    assert snapshots(users) == before
