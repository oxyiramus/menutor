"""Production app/lifespan/container, without mock use cases or auth overrides."""

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture
def http_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'http.sqlite'}")
    monkeypatch.setenv("JWT_SECRET_KEY", "audit-http-test-secret-key-at-least-32-bytes")
    with TestClient(app) as client:
        yield client
        app.state.container._session.close()
        app.state.container._engine.dispose()


def register_login(client, email):
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "nickname": email.split("@")[0],
        },
    )
    assert response.status_code == 201, response.text
    assert "hash" not in response.text.lower()
    pair = client.post(
        "/api/auth/login", json={"email": email, "password": "Password123!"}
    )
    assert pair.status_code == 200, pair.text
    return {"Authorization": f"Bearer {pair.json()['access_token']}"}


def test_real_http_register_write_read_calculate_and_error(http_client):
    c = http_client
    assert c.get("/api/products").status_code == 401
    headers = register_login(c, "alice@example.com")
    assert c.get("/api/auth/me", headers=headers).json()["email"] == "alice@example.com"
    assert "hash" not in c.get("/api/auth/me", headers=headers).text.lower()
    bad = c.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "wrong"}
    )
    assert bad.status_code == 401 and "access_token" not in bad.json()
    assert bad.headers["www-authenticate"] == "Bearer"
    product = c.post(
        "/api/products",
        headers=headers,
        json={
            "name": "Flour",
            "category_id": 1,
            "recipe_unit": "g",
            "purchase_unit": "kg",
            "price_amount": "80",
            "conversion_factor": 1000,
        },
    )
    assert product.status_code == 201, product.text
    recipe = c.post(
        "/api/recipes",
        headers=headers,
        json={
            "name": "Bread",
            "category_id": 1,
            "servings": 2,
            "ingredients": [
                {
                    "product_id": product.json()["id"],
                    "quantity_amount": 200,
                    "quantity_unit": "g",
                }
            ],
        },
    )
    assert recipe.status_code == 201, recipe.text
    rid = recipe.json()["id"]
    loaded = c.get(f"/api/recipes/{rid}", headers=headers)
    assert loaded.status_code == 200
    assert loaded.json()["cost_per_portion"] == pytest.approx(8)
    assert loaded.json()["ingredients"][0]["quantity_amount"] == 200
    assert c.get(f"/api/recipes/{rid}", headers=headers).json() == loaded.json()
    assert c.get("/api/recipes/999999", headers=headers).status_code == 404
    other = register_login(c, "bob@example.com")
    assert c.get(f"/api/recipes/{rid}", headers=other).status_code == 404
    assert c.get("/api/recipes", headers=other).json()["items"] == []


@pytest.mark.parametrize("route", ["recipes", "recipes/cost-preview"])
def test_http_rejects_foreign_product_links(http_client, route):
    c = http_client
    owner = register_login(c, "alice@example.com")
    product = c.post(
        "/api/products",
        headers=owner,
        json={
            "name": "Secret",
            "category_id": 1,
            "recipe_unit": "g",
            "purchase_unit": "kg",
            "price_amount": "80",
            "conversion_factor": 1000,
        },
    ).json()
    other = register_login(c, "bob@example.com")
    body = {
        "name": "Attempt",
        "category_id": 1,
        "servings": 2,
        "ingredients": [
            {"product_id": product["id"], "quantity_amount": 200, "quantity_unit": "g"}
        ],
    }
    response = c.post(f"/api/{route}", headers=other, json=body)
    assert response.status_code in (404, 422), response.text
    assert c.get("/api/recipes", headers=other).json()["items"] == []


@pytest.mark.parametrize(
    "foreign_field", ["product_id", "recipe_id", "meal_type_id", "member_ids"]
)
def test_http_menu_rejects_foreign_nested_links(http_client, foreign_field):
    c = http_client
    a = register_login(c, "alice@example.com")
    b = register_login(c, "bob@example.com")
    foreign_product = c.post(
        "/api/products",
        headers=a,
        json={
            "name": "Secret",
            "category_id": 1,
            "recipe_unit": "g",
            "purchase_unit": "kg",
            "price_amount": "80",
            "conversion_factor": 1000,
        },
    ).json()["id"]
    foreign_recipe = c.post(
        "/api/recipes",
        headers=a,
        json={"name": "Secret recipe", "category_id": 1, "servings": 2},
    ).json()["id"]
    own_recipe = c.post(
        "/api/recipes",
        headers=b,
        json={"name": "Own recipe", "category_id": 1, "servings": 2},
    ).json()["id"]
    own_meal = c.get("/api/meal-types", headers=b).json()[0]["id"]
    foreign_meal = c.get("/api/meal-types", headers=a).json()[0]["id"]
    foreign_member = c.get("/api/family-members", headers=a).json()[0]["id"]
    menu = c.post("/api/menus", headers=b, json={"name": "Own menu"}).json()["id"]
    slot = {"day": 0, "meal_type_id": own_meal, "recipe_id": own_recipe}
    if foreign_field == "product_id":
        slot.pop("recipe_id")
        slot.update(product_id=foreign_product, quantity=100, unit="g")
    elif foreign_field == "recipe_id":
        slot["recipe_id"] = foreign_recipe
    elif foreign_field == "meal_type_id":
        slot["meal_type_id"] = foreign_meal
    else:
        slot["member_ids"] = [foreign_member]
    response = c.post(f"/api/menus/{menu}/slots", headers=b, json=slot)
    assert response.status_code in (404, 422), response.text
    assert c.get(f"/api/menus/{menu}", headers=b).json()["slots"] == []


@pytest.mark.parametrize("preview", [False, True])
def test_http_recipe_rejects_foreign_subrecipe(http_client, preview):
    c = http_client
    a = register_login(c, "alice@example.com")
    rid = c.post(
        "/api/recipes",
        headers=a,
        json={"name": "Secret recipe", "category_id": 1, "servings": 2},
    ).json()["id"]
    b = register_login(c, "bob@example.com")
    route = "/api/recipes/cost-preview" if preview else "/api/recipes"
    response = c.post(
        route,
        headers=b,
        json={
            "name": "Attempt",
            "category_id": 1,
            "servings": 2,
            "ingredients": [
                {"sub_recipe_id": rid, "quantity_amount": 1, "quantity_unit": "serv"}
            ],
        },
    )
    assert response.status_code in (404, 422), response.text
