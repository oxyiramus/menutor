"""PostgreSQL smoke test using an isolated, automatically cleaned container."""

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer

from backend.application.use_cases.auth import (
    ChangePasswordData,
    LoginData,
    RegisterData,
)
from backend.application.use_cases.manage_product import CreateProduct, ProductData
from backend.composition.container import ApplicationContainer
from backend.domain.exceptions import AuthenticationError
from backend.domain.value_objects.money import Money
from backend.domain.value_objects.types import ProductCategoryId, UserId
from backend.infrastructure.database.models import Base
from backend.infrastructure.repositories.orm_product_repository import (
    OrmProductRepository,
)


@pytest.fixture(scope="module")
def postgres_url():
    url = os.environ.get("TEST_PERSONAL_CATEGORIES_POSTGRES_URL")
    if url:
        yield url
        return
    with PostgresContainer("postgres:18-alpine") as postgres:
        yield postgres.get_connection_url()


def test_postgresql_persist_read_and_delete(postgres_url):
    engine = create_engine(postgres_url)
    schema = f"audit_{uuid4().hex}"
    try:
        with engine.connect() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema}"))
            connection.execute(text(f"SET search_path TO {schema}"))
            connection.commit()
            try:
                Base.metadata.create_all(connection)
                connection.commit()
                with Session(connection) as session:
                    session.execute(
                        text(
                            "INSERT INTO users (id,email,nickname,hashed_password,created_at) VALUES (1,'test@example.com','T','h','2026-01-01')"
                        )
                    )
                    session.execute(
                        text(
                            "INSERT INTO product_categories (id,user_id,name,active) VALUES (1,1,'Category',1)"
                        )
                    )
                    session.execute(
                        text(
                            "INSERT INTO units (name,unit_group) VALUES ('g','weight'),('kg','weight')"
                        )
                    )
                    session.commit()
                    repo = OrmProductRepository(session)
                    product = CreateProduct(repo).execute(
                        ProductData(
                            "Flour",
                            ProductCategoryId(1),
                            "g",
                            "kg",
                            Money(Decimal("12.34")),
                        ),
                        UserId(1),
                    )
                    session.expunge_all()
                    assert repo.get_by_id(
                        product.id
                    ).price_per_purchase_unit.amount == Decimal("12.34")
                    repo.delete([product.id])
                    assert repo.get_by_id(product.id) is None
            finally:
                connection.rollback()
                connection.execute(text("SET search_path TO public"))
                connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
                connection.commit()
    finally:
        engine.dispose()


@pytest.mark.parametrize("refresh_first", [True, False])
def test_password_change_refresh_overlap(postgres_url, refresh_first):
    schema = f"audit_{uuid4().hex}"
    admin = create_engine(postgres_url)
    engine = create_engine(
        postgres_url,
        connect_args={"options": f"-c search_path={schema} -c statement_timeout=15000"},
    )
    try:
        with admin.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema}"))
        Base.metadata.create_all(engine)
        secret = "audit-test-secret-key-with-at-least-32-bytes"
        email = "overlap@example.com"
        password = "correct-password"
        with Session(engine) as session:
            auth = ApplicationContainer(session, secret)
            user = auth.register_user.execute(RegisterData(email, password))
            pair = auth.login_user.execute(LoginData(email, password))

        first_paused = Event()
        second_started = Event()
        release = Event()
        pids = {}

        def run(refresh, first):
            with Session(engine) as session:
                pids[first] = session.execute(
                    text("SELECT pg_backend_pid()")
                ).scalar_one()
                auth = ApplicationContainer(session, secret)
                if first:

                    @event.listens_for(session, "before_commit", once=True)
                    def pause_before_commit(_session):
                        _session.flush()
                        first_paused.set()
                        assert release.wait(12)
                else:
                    second_started.set()

                if refresh:
                    try:
                        return auth.refresh_access_token.execute(pair.refresh_token)
                    except AuthenticationError:
                        return None
                auth.change_password.execute(
                    user, ChangePasswordData(password, "replacement-password")
                )
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run, refresh_first, True)
            try:
                assert first_paused.wait(5)
                second = pool.submit(run, not refresh_first, False)
                assert second_started.wait(5)
                blocked = False
                deadline = monotonic() + 5
                with admin.connect() as connection:
                    while not second.done() and monotonic() < deadline:
                        blockers = connection.execute(
                            text("SELECT pg_blocking_pids(:pid)"), {"pid": pids[False]}
                        ).scalar_one()
                        if pids[True] in blockers:
                            blocked = True
                            break
                        sleep(0.01)
            finally:
                release.set()
            first_result = first.result(timeout=10)
            second_result = second.result(timeout=10)

        with Session(engine) as session:
            auth = ApplicationContainer(session, secret)
            if refresh_first:
                assert first_result is not None
                with pytest.raises(AuthenticationError):
                    auth.refresh_access_token.execute(first_result.refresh_token)
            else:
                assert second_result is None
            with pytest.raises(AuthenticationError):
                auth.refresh_access_token.execute(pair.refresh_token)
        assert blocked, "the second operation must wait for the first transaction"
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        admin.dispose()
