"""Verify the lifetime of real HTTP request sessions."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api.main import app
from backend.application.use_cases.auth import GetCurrentUser
from backend.application.use_cases.manage_product import ListProducts
from backend.domain.exceptions import DomainError
from backend.infrastructure.repositories.orm_product_repository import (
    OrmProductRepository,
)
from tests.integration.test_audit_http import active_category_id, register_login
from tests.integration.test_personal_category_migration import (
    migration_database as migration_database,
)


def test_overlapping_requests_use_distinct_sessions(migration_database, monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "request-session-test-secret-at-least-32-bytes"
    )
    with TestClient(app) as client:
        first = register_login(client, "first@example.com")
        second = register_login(client, "second@example.com")
        auth_sessions = {}
        first_ready = Event()
        release_first = Event()
        authenticate = GetCurrentUser.execute
        list_products = ListProducts.execute

        def record_auth(use_case, token):
            user = authenticate(use_case, token)
            auth_sessions[user.id] = use_case._user_repo._session
            return user

        def check_handler(use_case, user_id, *args, **kwargs):
            session = use_case._repo._session
            assert session is auth_sessions[user_id]
            if len(auth_sessions) == 1:
                first_ready.set()
                assert release_first.wait(timeout=10)
            else:
                assert all(
                    other_session is not session
                    for owner, other_session in auth_sessions.items()
                    if owner != user_id
                ), "Concurrent HTTP requests share a Session"
            return list_products(use_case, user_id, *args, **kwargs)

        monkeypatch.setattr(GetCurrentUser, "execute", record_auth)
        monkeypatch.setattr(ListProducts, "execute", check_handler)
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(client.get, "/api/products", headers=first)
            try:
                assert first_ready.wait(timeout=10)
                assert client.get("/api/products", headers=second).status_code == 200
                assert not pending.done()
            finally:
                release_first.set()
            assert pending.result(timeout=10).status_code == 200


@pytest.mark.parametrize("outcome", ["success", "handled", "unhandled"])
def test_request_closes_session_and_discards_pending_changes(
    isolation_client, monkeypatch, outcome
):
    headers = register_login(isolation_client, "cleanup@example.com")
    list_products = ListProducts.execute
    used = []
    closed = []
    close = Session.close

    def track_close(session):
        closed.append(session)
        close(session)

    def leave_pending(use_case, *args, **kwargs):
        session = use_case._repo._session
        used.append(session)
        assert (
            session.execute(
                text("SELECT unit_group FROM units WHERE name = 'g'")
            ).scalar_one()
            == "weight"
        )
        if len(used) == 1:
            session.execute(
                text("UPDATE units SET unit_group = 'test' WHERE name = 'g'")
            )
            if outcome == "handled":
                raise DomainError("test")
            if outcome == "unhandled":
                raise RuntimeError("test")
        return list_products(use_case, *args, **kwargs)

    monkeypatch.setattr(Session, "close", track_close)
    monkeypatch.setattr(ListProducts, "execute", leave_pending)
    if outcome == "unhandled":
        with pytest.raises(RuntimeError, match="test"):
            isolation_client.get("/api/products", headers=headers)
    else:
        response = isolation_client.get("/api/products", headers=headers)
        assert response.status_code == (422 if outcome == "handled" else 200)

    assert used[0] in closed
    assert not used[0].in_transaction()
    with app.state.database.engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT unit_group FROM units WHERE name = 'g'")
            ).scalar_one()
            == "weight"
        )
    assert isolation_client.get("/api/products", headers=headers).status_code == 200
    assert used[1] is not used[0]
    assert used[1] in closed


@pytest.mark.parametrize("migration_database", ["postgresql"], indirect=True)
def test_login_cannot_commit_another_requests_import(migration_database, monkeypatch):
    engine, _ = migration_database
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "request-session-test-secret-at-least-32-bytes"
    )
    first_saved = Event()
    resume_import = Event()
    save_product = OrmProductRepository.save
    product_name = "Pending import"

    def pause_after_save(repo, product):
        saved = save_product(repo, product)
        if product.name == product_name:
            first_saved.set()
            assert resume_import.wait(timeout=10), "Import was not resumed"
        return saved

    def persisted_state():
        with engine.connect() as connection:
            products = (
                connection.execute(text("SELECT name FROM products")).scalars().all()
            )
            refresh_counts = dict(
                connection.execute(
                    text(
                        "SELECT users.email, count(refresh_tokens.id) FROM users "
                        "LEFT JOIN refresh_tokens ON refresh_tokens.user_id = users.id "
                        "GROUP BY users.email"
                    )
                )
                .tuples()
                .all()
            )
        return products, refresh_counts

    with TestClient(app) as client:
        headers = register_login(client, "importer@example.com")
        register_login(client, "login@example.com")
        valid = {
            "name": product_name,
            "category_id": active_category_id(client, "products", headers),
            "recipe_unit": "g",
            "purchase_unit": "kg",
            "price_amount": "99",
        }
        payload = json.dumps([valid, {"name": "Invalid"}])
        monkeypatch.setattr(OrmProductRepository, "save", pause_after_save)

        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(
                client.post,
                "/api/products/import/json",
                headers=headers,
                files={"file": ("products.json", payload, "application/json")},
            )
            try:
                assert first_saved.wait(timeout=10), "First import row was not saved"
                login = client.post(
                    "/api/auth/login",
                    json={"email": "login@example.com", "password": "Password123!"},
                )
                assert login.status_code == 200, login.text
                assert not pending.done()
                during_import = persisted_state()
            finally:
                resume_import.set()
            failed_import = pending.result(timeout=10)

        assert failed_import.status_code == 422, failed_import.text
        expected = ([], {"importer@example.com": 1, "login@example.com": 2})
        assert during_import == expected
        assert persisted_state() == expected
