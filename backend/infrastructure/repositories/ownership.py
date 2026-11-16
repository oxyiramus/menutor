"""Validate ownership of references before storing user-owned aggregates."""

from sqlalchemy.orm import Session

from backend.domain.exceptions import EntityNotFoundError


def require_owned(session: Session, model: type, entity_id: int, user_id: int) -> None:
    row = session.get(model, int(entity_id))
    if row is None or row.user_id != user_id:
        raise EntityNotFoundError("Связанный объект не найден")
