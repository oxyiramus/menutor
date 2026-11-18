"""Shared persistence for personal product and recipe categories."""

from typing import Any, ClassVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.domain.exceptions import DuplicateNameError, EntityNotFoundError
from backend.domain.value_objects.category import ActiveCategory, Category


class BaseOrmCategoryRepository:
    _cat_class: ClassVar[Any]
    _linked_class: ClassVar[Any]

    def __init__(self, session: Session) -> None:
        self._session = session

    def _categories(self, user_id: int) -> Any:
        return self._session.query(self._cat_class).filter(
            self._cat_class.user_id == user_id
        )

    def _get_owned(self, category_id: int, user_id: int) -> Any:
        row = (
            self._categories(user_id)
            .filter(self._cat_class.id == category_id)
            .one_or_none()
        )
        if row is None:
            raise EntityNotFoundError(f"Категория с id={category_id} не найдена")
        return row

    def _linked(self, category_id: int, user_id: int) -> Any:
        return self._session.query(self._linked_class).filter(
            self._linked_class.category_id == category_id,
            self._linked_class.user_id == user_id,
        )

    def find_active(self, user_id: int) -> list[ActiveCategory]:
        rows = (
            self._categories(user_id)
            .filter(self._cat_class.active == 1)
            .order_by(self._cat_class.name)
            .all()
        )
        return [ActiveCategory(r.id, r.name, r.color) for r in rows]

    def find_all(self, user_id: int) -> list[Category]:
        rows = self._categories(user_id).order_by(self._cat_class.name).all()
        return [Category(r.id, r.name, bool(r.active), r.color) for r in rows]

    def find_id_by_name(self, name: str, user_id: int) -> int | None:
        row = (
            self._categories(user_id).filter(self._cat_class.name == name).one_or_none()
        )
        category_id: int | None = row.id if row is not None else None
        return category_id

    def save(
        self,
        name: str,
        category_id: int | None = None,
        *,
        user_id: int,
        color: str | None = None,
    ) -> int:
        if category_id is None:
            row = self._cat_class(user_id=user_id)
            self._session.add(row)
        else:
            row = self._get_owned(category_id, user_id)
        row.name = name
        row.active = 1
        row.color = color
        try:
            self._session.flush()
            saved_id: int = row.id
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            if (
                self._categories(user_id).filter(self._cat_class.name == name).first()
                is not None
            ):
                raise DuplicateNameError("категория") from exc
            raise
        return saved_id

    def delete(self, category_id: int, user_id: int) -> None:
        row = self._get_owned(category_id, user_id)
        row.active = 0
        self._session.commit()

    def hard_delete(self, category_id: int, user_id: int) -> None:
        row = self._get_owned(category_id, user_id)
        try:
            self._delete_linked(category_id, user_id)
            self._session.delete(row)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def _delete_linked(self, category_id: int, user_id: int) -> None:
        self._linked(category_id, user_id).delete(synchronize_session=False)

    def activate(self, category_id: int, user_id: int) -> None:
        row = self._get_owned(category_id, user_id)
        row.active = 1
        self._session.commit()

    def is_used(self, category_id: int, user_id: int) -> bool:
        self._get_owned(category_id, user_id)
        return self._linked(category_id, user_id).first() is not None

    def move_and_delete(self, from_id: int, to_id: int, user_id: int) -> None:
        row = self._get_owned(from_id, user_id)
        self._get_owned(to_id, user_id)
        try:
            self._linked(from_id, user_id).update(
                {"category_id": to_id}, synchronize_session=False
            )
            self._session.delete(row)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
