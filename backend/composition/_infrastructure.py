"""Infrastructure layer objects — DB, repos, auth services, exporters."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.orm import Session, sessionmaker

from backend.domain.services.password_hasher import PasswordHasher
from backend.domain.services.portion_calculator import PortionCalculator
from backend.domain.services.shopping_list_builder import ShoppingListBuilder
from backend.domain.services.unit_converter import UnitConverter
from backend.infrastructure.auth.bcrypt_password_hasher import BcryptPasswordHasher
from backend.infrastructure.auth.jwt_token_service import JwtTokenService
from backend.infrastructure.database.connection import (
    apply_schema,
    get_engine,
    seed_defaults,
)
from backend.infrastructure.export.csv_exporter import ShoppingListCsvExporter
from backend.infrastructure.export.shopping_list_json_exporter import (
    ShoppingListJsonExporter,
)
from backend.infrastructure.export.shopping_list_pdf_exporter import (
    ShoppingListPdfExporter,
)
from backend.infrastructure.export.text_exporter import ShoppingListTextExporter
from backend.infrastructure.repositories.orm_family_member_repository import (
    OrmFamilyMemberRepository,
)
from backend.infrastructure.repositories.orm_meal_type_repository import (
    OrmMealTypeRepository,
)
from backend.infrastructure.repositories.orm_menu_repository import (
    OrmMenuRepository,
)
from backend.infrastructure.repositories.orm_product_category_repository import (
    OrmProductCategoryRepository,
)
from backend.infrastructure.repositories.orm_product_repository import (
    OrmProductRepository,
)
from backend.infrastructure.repositories.orm_recipe_category_repository import (
    OrmRecipeCategoryRepository,
)
from backend.infrastructure.repositories.orm_recipe_repository import (
    OrmRecipeRepository,
)
from backend.infrastructure.repositories.orm_refresh_token_repository import (
    OrmRefreshTokenRepository,
)
from backend.infrastructure.repositories.orm_saved_shopping_list_repository import (
    OrmSavedShoppingListRepository,
)
from backend.infrastructure.repositories.orm_user_repository import (
    OrmUserRepository,
)


@dataclass
class _Infrastructure:
    """Infrastructure objects bound to one session."""

    session: Session
    user_repo: OrmUserRepository
    refresh_token_repo: OrmRefreshTokenRepository
    password_hasher: PasswordHasher
    token_service: JwtTokenService
    recipe_repo: OrmRecipeRepository
    product_repo: OrmProductRepository
    menu_repo: OrmMenuRepository
    family_repo: OrmFamilyMemberRepository
    product_category_repo: OrmProductCategoryRepository
    recipe_category_repo: OrmRecipeCategoryRepository
    text_exporter: ShoppingListTextExporter
    csv_exporter: ShoppingListCsvExporter
    json_exporter: ShoppingListJsonExporter
    pdf_exporter: ShoppingListPdfExporter
    builder: ShoppingListBuilder
    saved_shopping_list_repo: OrmSavedShoppingListRepository
    meal_type_repo: OrmMealTypeRepository


_JWT_SECRET_PLACEHOLDERS = frozenset(
    {"test-only-secret-do-not-use-in-production", "some_awesome_key"}
)


def _get_jwt_secret() -> str:
    """Require an explicit JWT secret before initializing the database."""
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret or secret in _JWT_SECRET_PLACEHOLDERS:
        raise RuntimeError(
            "Set JWT_SECRET_KEY to a non-empty custom key in .config/.env "
            "or your environment."
        )
    return secret


class ApplicationDatabase:
    """Application-scoped engine and session factory."""

    def __init__(self) -> None:
        env_path = Path(__file__).resolve().parents[2] / ".config" / ".env"
        load_dotenv(env_path)
        db_url = os.environ.get("DATABASE_URL", "sqlite:///data/menutor.db")

        self.jwt_secret = _get_jwt_secret()
        self.engine = get_engine(db_url)
        self.sessions = sessionmaker(self.engine)
        try:
            apply_schema(self.engine)
            with self.sessions() as session:
                seed_defaults(session)
        except BaseException:
            self.engine.dispose()
            raise


def _create_infrastructure(session: Session, jwt_secret: str) -> _Infrastructure:
    recipe_repo = OrmRecipeRepository(session)
    product_repo = OrmProductRepository(session)
    product_category_repo = OrmProductCategoryRepository(session)

    return _Infrastructure(
        session=session,
        user_repo=OrmUserRepository(session),
        refresh_token_repo=OrmRefreshTokenRepository(session),
        password_hasher=BcryptPasswordHasher(),
        token_service=JwtTokenService(jwt_secret),
        recipe_repo=recipe_repo,
        product_repo=product_repo,
        menu_repo=OrmMenuRepository(session),
        family_repo=OrmFamilyMemberRepository(session),
        product_category_repo=product_category_repo,
        recipe_category_repo=OrmRecipeCategoryRepository(session),
        text_exporter=ShoppingListTextExporter(),
        csv_exporter=ShoppingListCsvExporter(),
        json_exporter=ShoppingListJsonExporter(),
        pdf_exporter=ShoppingListPdfExporter(),
        builder=ShoppingListBuilder(
            recipe_repo=recipe_repo,
            product_repo=product_repo,
            product_category_repo=product_category_repo,
            portion_calc=PortionCalculator(),
            unit_converter=UnitConverter(),
        ),
        saved_shopping_list_repo=OrmSavedShoppingListRepository(session),
        meal_type_repo=OrmMealTypeRepository(session),
    )
