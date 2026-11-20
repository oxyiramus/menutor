import pytest
from sqlalchemy.exc import OperationalError

from backend.infrastructure.repositories.orm_product_repository import (
    OrmProductRepository,
)
from backend.infrastructure.repositories.orm_recipe_repository import (
    OrmRecipeRepository,
)
from tests.integration.api_isolation_helpers import request_ok
from tests.integration.test_derived_data_isolation import import_rows


@pytest.mark.parametrize("fmt", ["json", "csv"])
@pytest.mark.parametrize(
    "field,error",
    [
        ("recipe_unit", "неизвестная единица измерения в поле 'recipe_unit'"),
        ("purchase_unit", "неизвестная единица измерения в поле 'purchase_unit'"),
        ("id", "некорректное значение 'id'"),
    ],
)
def test_import_data_error_is_safe_and_rolls_back(isolation_users, fmt, field, error):
    client, (alice, _) = isolation_users
    headers = alice["headers"]
    before = request_ok(client, "GET", "products", headers)
    first = dict(alice["bodies"]["products"], name="First row", price_amount=10)
    second = dict(first, name="Private file record")
    second[field] = "INVALID_UNIT"
    response = import_rows(client, alice, "products", fmt, [first, second])

    assert response.status_code == 422
    location = "Элемент 2" if fmt == "json" else "Строка 3"
    assert response.json() == {"detail": f"{location}: {error}"}
    assert request_ok(client, "GET", "products", headers) == before


@pytest.mark.parametrize("fmt", ["json", "csv"])
def test_import_technical_error_is_safe_and_rolls_back(
    isolation_users, monkeypatch, caplog, fmt
):
    client, (alice, _) = isolation_users
    headers = alice["headers"]
    before = request_ok(client, "GET", "products", headers)
    first = dict(alice["bodies"]["products"], name="First row", price_amount=10)
    second = dict(first, name="Private file record")
    save = OrmProductRepository.save
    calls = []

    def fail_on_second(repo, product):
        calls.append(product.name)
        if product.name == second["name"]:
            raise OperationalError(
                "SELECT name FROM products",
                {"token": "private-token"},
                RuntimeError("/private/file.py password=private-password"),
            )
        return save(repo, product)

    monkeypatch.setattr(OrmProductRepository, "save", fail_on_second)
    response = import_rows(client, alice, "products", fmt, [first, second])

    assert calls == [first["name"], second["name"]]
    assert response.status_code == 500
    assert response.json() == {"detail": "Не удалось выполнить импорт"}
    assert "private-token" not in caplog.text
    assert "private-password" not in caplog.text
    assert request_ok(client, "GET", "products", headers) == before


def test_recipe_reference_lookup_failure_is_technical(isolation_users, monkeypatch):
    client, (alice, _) = isolation_users

    def fail_lookup(*args):
        raise RuntimeError("password=private-password")

    monkeypatch.setattr(OrmRecipeRepository, "get_by_id", fail_lookup)
    row = dict(
        alice["bodies"]["recipes"],
        ingredients=[
            {"sub_recipe_id": 1, "quantity_amount": 1, "quantity_unit": "serv"}
        ],
    )
    response = import_rows(client, alice, "recipes", "json", [row])
    assert response.status_code == 500
    assert response.json() == {"detail": "Не удалось выполнить импорт"}
