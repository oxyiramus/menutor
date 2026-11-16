"""PostgreSQL smoke test using an isolated, automatically cleaned container."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer

from backend.application.use_cases.manage_product import CreateProduct, ProductData
from backend.domain.value_objects.money import Money
from backend.domain.value_objects.types import ProductCategoryId, UserId
from backend.infrastructure.database.models import Base
from backend.infrastructure.repositories.orm_product_repository import (
    OrmProductRepository,
)


@pytest.fixture(scope="module")
def postgres_url():
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
                            "INSERT INTO product_categories (id,name,active) VALUES (1,'Category',1)"
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
