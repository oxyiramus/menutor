from typing import Any

from sqlalchemy.orm import Session

from backend.domain.entities.user import User
from backend.domain.exceptions import RepositoryError
from backend.domain.ports.user_repository import UserRepository
from backend.domain.value_objects.types import UserId
from backend.infrastructure.database.models import (
    ProductCategoryRow,
    RecipeCategoryRow,
    RefreshTokenRow,
    UserRow,
)
from backend.infrastructure.repositories.base import BaseOrmRepository

_DEFAULT_RECIPE_CATEGORIES = (
    "Завтраки",
    "Обеды",
    "Ужины",
    "Основные",
    "Салаты",
    "Десерты",
)
_DEFAULT_PRODUCT_CATEGORIES = (
    "Сыпучие",
    "Молочные",
    "Мясо",
    "Овощи",
    "Фрукты",
    "Консервы",
    "Напитки",
    "Прочее",
)


class OrmUserRepository(
    BaseOrmRepository[User, UserId],
    UserRepository,
):
    _row_class = UserRow

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def _get_entity_id(self, entity: User) -> int:
        return entity.id

    def _wrap_id(self, raw_id: int) -> UserId:
        return UserId(raw_id)

    def _make_new_row(self, entity: User) -> UserRow:
        return UserRow(
            product_categories=[
                ProductCategoryRow(name=name) for name in _DEFAULT_PRODUCT_CATEGORIES
            ],
            recipe_categories=[
                RecipeCategoryRow(name=name) for name in _DEFAULT_RECIPE_CATEGORIES
            ],
            email=entity.email,
            nickname=entity.nickname,
            hashed_password=entity.hashed_password,
            created_at=entity.created_at,
            last_login_at=entity.last_login_at,
        )

    def _update_row(self, row: Any, entity: User) -> None:
        row.email = entity.email
        row.nickname = entity.nickname
        row.hashed_password = entity.hashed_password
        row.last_login_at = entity.last_login_at

    def _row_to_entity(self, row: Any) -> User:
        return User(
            id=UserId(row.id),
            email=row.email,
            nickname=row.nickname,
            hashed_password=row.hashed_password,
            created_at=row.created_at,
            last_login_at=row.last_login_at,
        )

    def update_nickname(self, user_id: UserId, nickname: str) -> User:
        row = self._session.get(UserRow, int(user_id))
        if row is None:
            raise RepositoryError(f"Entity {user_id} not found in users")
        row.nickname = nickname
        self._session.commit()
        self._session.refresh(row)
        return self._row_to_entity(row)

    def get_by_email(self, email: str) -> User | None:
        row = self._session.query(UserRow).filter(UserRow.email == email).first()
        if row is None:
            return None
        return self._row_to_entity(row)

    def change_password_and_revoke_sessions(
        self, user_id: UserId, expected_hash: str, new_hash: str
    ) -> bool:
        try:
            updated = (
                self._session.query(UserRow)
                .filter(
                    UserRow.id == int(user_id), UserRow.hashed_password == expected_hash
                )
                .update({"hashed_password": new_hash}, synchronize_session=False)
            )
            if updated == 0:
                self._session.rollback()
                return False
            (
                self._session.query(RefreshTokenRow)
                .filter(
                    RefreshTokenRow.user_id == int(user_id),
                    RefreshTokenRow.revoked.is_(False),
                )
                .update({"revoked": True}, synchronize_session=False)
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return True
