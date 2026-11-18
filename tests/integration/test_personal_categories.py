import json

import pytest

from tests.integration.api_isolation_helpers import request_ok


@pytest.mark.parametrize("kind", ["product", "recipe"])
def test_personal_category_catalog(isolation_users, kind):
    client, (alice, bob) = isolation_users
    path = f"{kind}-categories"
    a, b = alice["headers"], bob["headers"]
    original = request_ok(client, "GET", path, b)
    personal = request_ok(client, "GET", path, a)
    assert [c["name"] for c in personal] == [c["name"] for c in original]
    assert {c["id"] for c in personal}.isdisjoint(c["id"] for c in original)
    source = personal[0]["id"]
    foreign = original[0]["id"]
    own_path = f"{path}/{source}"
    foreign_path = f"{path}/{foreign}"
    body = {"name": "Renamed", "color": "#ABCDEF"}
    request_ok(client, "PUT", own_path, a, body)
    request_ok(client, "DELETE", own_path, a, status=204)
    assert source not in {
        c["id"] for c in request_ok(client, "GET", f"{kind}s/categories", a)
    }
    assert client.put(f"/api/{foreign_path}", headers=a, json=body).status_code == 404
    assert client.get(f"/api/{foreign_path}/used", headers=a).status_code == 404
    assert client.post(f"/api/{foreign_path}/activate", headers=a).status_code == 404
    assert client.delete(f"/api/{foreign_path}?hard=true", headers=a).status_code == 404
    for src, dst in ((own_path, foreign), (foreign_path, source)):
        assert (
            client.post(
                f"/api/{src}/move-and-delete",
                headers=a,
                json={"target_category_id": dst},
            ).status_code
            == 422
        )
    assert request_ok(client, "GET", path, b) == original


@pytest.mark.parametrize(
    "kind", ["products", "recipes", "category_ids", "recipe_category_ids"]
)
def test_foreign_category_references(isolation_users, kind):
    client, (alice, bob) = isolation_users
    headers = alice["headers"]
    if kind.endswith("_ids"):
        entity_type = "recipes" if kind.startswith("recipe") else "products"
        body = dict(alice["bodies"]["preferences"])
        body[kind] = [bob["bodies"][entity_type]["category_id"]]
        kind = "preferences"
    else:
        body = dict(
            alice["bodies"][kind], category_id=bob["bodies"][kind]["category_id"]
        )
    body["name"] = "Foreign category"
    assert client.post(f"/api/{kind}", headers=headers, json=body).status_code == 404
    entity_id = alice["objects"][kind]["id"]
    assert (
        client.put(f"/api/{kind}/{entity_id}", headers=headers, json=body).status_code
        == 404
    )
    if kind != "preferences":
        response = client.post(
            f"/api/{kind}/import/json",
            headers=headers,
            files={"file": ("import.json", json.dumps([body]), "application/json")},
        )
        assert response.status_code == 422


@pytest.mark.parametrize("kind", ["products", "recipes"])
@pytest.mark.parametrize("fmt", ["csv", "json"])
def test_import_category_name_resolves_only_current_catalog(isolation_users, kind, fmt):
    from tests.integration.test_derived_data_isolation import import_rows

    client, (alice, bob) = isolation_users
    a, b = alice["headers"], bob["headers"]
    path = f"{kind[:-1]}-categories"
    name = "Imported category"
    request_ok(client, "POST", path, b, {"name": name}, 201)
    row = dict(alice["bodies"][kind], name="Imported item", category_name=name)
    del row["category_id"]
    assert import_rows(client, alice, kind, fmt, [row]).status_code == 422
    owned = request_ok(client, "POST", path, a, {"name": name}, 201)
    response = import_rows(client, alice, kind, fmt, [row])
    assert response.status_code == 200, response.text
    [item] = [
        item
        for item in request_ok(client, "GET", kind, a)["items"]
        if item["name"] == row["name"]
    ]
    assert item["category_id"] == owned["id"]


def test_registration_seed_after_restart(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.api.main import app

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'restart.sqlite'}")
    monkeypatch.setenv("JWT_SECRET_KEY", "restart-test-secret-key-at-least-32-bytes")

    def register(client, email):
        login = {"email": email, "password": "Password123!"}
        user = request_ok(client, "POST", "auth/register", {}, login, 201)
        return user, login_headers(client, login)

    def login_headers(client, login):
        pair = request_ok(client, "POST", "auth/login", {}, login)
        return {"Authorization": f"Bearer {pair['access_token']}"}

    initial = {}
    expected = {}
    alice_email = "alice@test.example"
    paths = ("product-categories", "recipe-categories")
    with TestClient(app) as client:
        try:
            alice, headers = register(client, alice_email)
            for path in paths:
                initial[path] = request_ok(client, "GET", path, headers)
                removed, edited = initial[path][:2]
                request_ok(
                    client,
                    "DELETE",
                    f"{path}/{removed['id']}?hard=true",
                    headers,
                    status=204,
                )
                request_ok(
                    client,
                    "PUT",
                    f"{path}/{edited['id']}",
                    headers,
                    {"name": "Личная", "color": "#ABCDEF"},
                )
                expected[path] = request_ok(client, "GET", path, headers)
        finally:
            app.state.container._session.close()
            app.state.container._engine.dispose()

    with TestClient(app) as client:
        try:
            headers = login_headers(
                client, {"email": alice_email, "password": "Password123!"}
            )
            bob, bob_headers = register(client, "bob@test.example")
            for path in paths:
                assert request_ok(client, "GET", path, headers) == expected[path]
                bob_categories = request_ok(client, "GET", path, bob_headers)
                assert [c["name"] for c in bob_categories] == [
                    c["name"] for c in initial[path]
                ]
                assert {c["id"] for c in bob_categories}.isdisjoint(
                    c["id"] for c in expected[path]
                )
                table = path.replace("-", "_")
                with app.state.container._engine.connect() as conn:
                    from sqlalchemy import text

                    catalog = dict(
                        conn.execute(text(f"SELECT id,user_id FROM {table}")).all()
                    )
                    assert all(catalog[c["id"]] == alice["id"] for c in expected[path])
                    assert all(catalog[c["id"]] == bob["id"] for c in bob_categories)
        finally:
            app.state.container._session.close()
            app.state.container._engine.dispose()
