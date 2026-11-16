"""Behavioral regressions identified by the November backend test audit."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import jwt
import pytest
from sqlalchemy import text

from backend.application.paginated_result import PAGE_SIZE
from backend.application.use_cases.auth import (
    ChangePassword,
    ChangePasswordData,
    GetCurrentUser,
    LoginData,
    LoginUser,
    LogoutUser,
    RefreshAccessToken,
    RegisterData,
    RegisterUser,
)
from backend.application.use_cases.crud_base import (
    DeleteEntity,
    GetEntity,
    PaginatedListEntities,
)
from backend.application.use_cases.import_entities import ImportEntities
from backend.application.use_cases.manage_product import (
    CreateProduct,
    EditProduct,
    ProductData,
)
from backend.domain.exceptions import (
    AuthenticationError,
    EntityNotFoundError,
    ImportValidationError,
)
from backend.domain.value_objects.money import Money
from backend.domain.value_objects.types import ProductCategoryId, ProductId, UserId
from backend.infrastructure.auth.bcrypt_password_hasher import BcryptPasswordHasher
from backend.infrastructure.auth.jwt_token_service import JwtTokenService
from backend.infrastructure.export.registry import ImportRegistry
from backend.infrastructure.import_.product_json_importer import ProductJsonImporter
from backend.infrastructure.repositories.orm_family_member_repository import (
    OrmFamilyMemberRepository,
)
from backend.infrastructure.repositories.orm_meal_type_repository import (
    OrmMealTypeRepository,
)
from backend.infrastructure.repositories.orm_product_repository import (
    OrmProductRepository,
)
from backend.infrastructure.repositories.orm_refresh_token_repository import (
    OrmRefreshTokenRepository,
)
from backend.infrastructure.repositories.orm_user_repository import OrmUserRepository


@pytest.fixture
def auth(conn):
    users = OrmUserRepository(conn)
    hasher = BcryptPasswordHasher()
    tokens = JwtTokenService("audit-test-secret-key-with-at-least-32-bytes")
    refresh = OrmRefreshTokenRepository(conn)
    family = OrmFamilyMemberRepository(conn)
    meals = OrmMealTypeRepository(conn)
    user = RegisterUser(users, hasher, family, meals).execute(
        RegisterData("new@example.com", "correct-password", "New user")
    )
    return user, users, hasher, tokens, refresh, family, meals


def test_registration_login_and_password_change(auth):
    user, users, hasher, tokens, refresh, family, meals = auth
    assert user.hashed_password != "correct-password"
    assert hasher.verify("correct-password", users.get_by_id(user.id).hashed_password)
    assert [m.name for m in family.find_all(user.id)] == ["New user"]
    assert {m.name for m in meals.find_all(user.id)} == {"Завтрак", "Обед", "Ужин"}
    login = LoginUser(users, hasher, tokens, refresh)
    with pytest.raises(AuthenticationError):
        login.execute(LoginData(user.email, "wrong-password"))
    pair = login.execute(LoginData(user.email, "correct-password"))
    assert GetCurrentUser(tokens, users).execute(pair.access_token).id == user.id
    ChangePassword(users, hasher).execute(
        user, ChangePasswordData("correct-password", "new-password")
    )
    with pytest.raises(AuthenticationError):
        login.execute(LoginData(user.email, "correct-password"))
    assert login.execute(LoginData(user.email, "new-password")).access_token


def test_refresh_rotation_and_logout(auth):
    user, users, hasher, tokens, refresh, *_ = auth
    pair = LoginUser(users, hasher, tokens, refresh).execute(
        LoginData(user.email, "correct-password")
    )
    rotate = RefreshAccessToken(tokens, refresh, users)
    rotated = rotate.execute(pair.refresh_token)
    assert rotated.refresh_token != pair.refresh_token
    with pytest.raises(AuthenticationError):
        rotate.execute(pair.refresh_token)
    LogoutUser(tokens, refresh).execute(rotated.refresh_token)
    with pytest.raises(AuthenticationError):
        rotate.execute(rotated.refresh_token)


@pytest.mark.parametrize("kind", ["expired", "signature", "refresh-type"])
def test_invalid_access_rejected(auth, kind):
    user, users, _, tokens, *_ = auth
    payload = {
        "sub": str(user.id),
        "type": "access",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    key = "audit-test-secret-key-with-at-least-32-bytes"
    if kind == "expired":
        payload["exp"] = datetime.now(UTC) - timedelta(seconds=1)
    elif kind == "signature":
        key = "another-test-secret-key-with-at-least-32-bytes"
    else:
        payload["type"] = "refresh"
    with pytest.raises(AuthenticationError):
        GetCurrentUser(tokens, users).execute(
            jwt.encode(payload, key, algorithm="HS256")
        )


def product_data(name, category=1):
    return ProductData(
        name=name,
        category_id=ProductCategoryId(category),
        recipe_unit="g",
        purchase_unit="kg",
        price=Money(Decimal("12.34")),
        conversion_factor=1000,
    )


def test_product_ownership_and_mixed_delete(conn, auth):
    user, *_ = auth
    repo = OrmProductRepository(conn)
    own = CreateProduct(repo).execute(product_data("Own"), user.id)
    foreign = CreateProduct(repo).execute(product_data("Foreign"), UserId(1))
    assert GetEntity(repo).execute(foreign.id, user.id) is None
    with pytest.raises(EntityNotFoundError):
        EditProduct(repo).execute(foreign.id, product_data("Stolen"), user.id)
    DeleteEntity(repo).execute([own.id, foreign.id, ProductId(999999)], user.id)
    conn.expire_all()
    assert repo.get_by_id(own.id) is None
    assert repo.get_by_id(foreign.id).name == "Foreign"


def test_paginated_search_category_total_and_owner(conn, auth):
    user, *_ = auth
    repo = OrmProductRepository(conn)
    create = CreateProduct(repo)
    expected = [
        create.execute(product_data(f"Apple {i:04}"), user.id).id
        for i in range(PAGE_SIZE + 3)
    ]
    create.execute(product_data("Apple foreign"), UserId(1))
    create.execute(product_data("Apple other category", 2), user.id)
    create.execute(product_data("Banana"), user.id)
    listing = PaginatedListEntities(repo)
    pages = [
        listing.execute(user.id, ProductCategoryId(1), page=p, search="APPLE")
        for p in (1, 2, 3)
    ]
    assert [p.total for p in pages] == [PAGE_SIZE + 3] * 3
    assert [len(p.items) for p in pages] == [PAGE_SIZE, 3, 0]
    assert [item.id for p in pages for item in p.items] == expected


@pytest.mark.parametrize("update_existing", [False, True])
def test_failed_import_is_atomic_and_session_recovers(conn, update_existing):
    repo = OrmProductRepository(conn)
    existing = CreateProduct(repo).execute(product_data("Original"), UserId(1))
    registry = ImportRegistry()
    registry.register("products", "json", ProductJsonImporter(repo))
    use_case = ImportEntities(registry, conn)
    row = {
        "name": "Imported",
        "category_id": 1,
        "recipe_unit": "g",
        "purchase_unit": "kg",
        "price_amount": "99",
    }
    if update_existing:
        row["id"] = int(existing.id)
    with pytest.raises(ImportValidationError):
        use_case.execute(
            "products",
            "json",
            json.dumps([row, {"name": "Invalid"}]).encode(),
            UserId(1),
        )
    conn.expire_all()
    # Read persisted state after rollback, rather than inspecting commit/rollback calls.
    persisted = repo.find_all(UserId(1))
    assert [(p.id, p.name, p.price_per_purchase_unit.amount) for p in persisted] == [
        (existing.id, "Original", Decimal("12.34"))
    ]
    result = use_case.execute(
        "products", "json", json.dumps([row | {"id": 0}]).encode(), UserId(1)
    )
    assert result.created == 1
    assert repo.find_by_name("Imported", UserId(1)) is not None


@pytest.mark.filterwarnings(
    "error:The default datetime adapter is deprecated:DeprecationWarning"
)
def test_expired_and_unknown_refresh_are_rejected(conn, auth):
    user, users, hasher, tokens, refresh, *_ = auth
    pair = LoginUser(users, hasher, tokens, refresh).execute(
        LoginData(user.email, "correct-password")
    )
    conn.execute(
        text("UPDATE refresh_tokens SET expires_at = :expiry"),
        {"expiry": (datetime.now(UTC) - timedelta(days=1)).isoformat(" ")},
    )
    conn.commit()
    for raw in (pair.refresh_token, "unknown-refresh-token"):
        with pytest.raises(AuthenticationError):
            RefreshAccessToken(tokens, refresh, users).execute(raw)


def test_logout_revokes_without_rotation(auth):
    user, users, hasher, tokens, refresh, *_ = auth
    pair = LoginUser(users, hasher, tokens, refresh).execute(
        LoginData(user.email, "correct-password")
    )
    LogoutUser(tokens, refresh).execute(pair.refresh_token)
    with pytest.raises(AuthenticationError):
        RefreshAccessToken(tokens, refresh, users).execute(pair.refresh_token)
