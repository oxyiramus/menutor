from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.domain.entities.refresh_token import RefreshToken
from backend.domain.ports.refresh_token_repository import RefreshTokenRepository
from backend.domain.value_objects.types import RefreshTokenId, UserId
from backend.infrastructure.database.models import RefreshTokenRow


class OrmRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def _row_to_entity(self, row: Any) -> RefreshToken:
        # SQLite returns naive timestamps; refresh expiry is stored in UTC.
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return RefreshToken(
            id=RefreshTokenId(row.id),
            user_id=UserId(row.user_id),
            token_hash=row.token_hash,
            expires_at=expires_at,
            revoked=row.revoked,
        )

    def save(self, token: RefreshToken) -> RefreshToken:
        row = self._add(token)
        self._session.flush()
        self._session.commit()
        return self._row_to_entity(row)

    def _add(self, token: RefreshToken) -> RefreshTokenRow:
        row = RefreshTokenRow(
            user_id=int(token.user_id),
            token_hash=token.token_hash,
            expires_at=token.expires_at,
            revoked=token.revoked,
        )
        self._session.add(row)
        return row

    def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        row = (
            self._session.query(RefreshTokenRow)
            .filter(RefreshTokenRow.token_hash == token_hash)
            .first()
        )
        if row is None:
            return None
        return self._row_to_entity(row)

    def rotate(self, token_hash: str, replacement: RefreshToken) -> bool:
        try:
            updated = (
                self._session.query(RefreshTokenRow)
                .filter(
                    RefreshTokenRow.token_hash == token_hash,
                    RefreshTokenRow.user_id == int(replacement.user_id),
                    RefreshTokenRow.revoked.is_(False),
                    RefreshTokenRow.expires_at > datetime.now(UTC),
                )
                .update({"revoked": True}, synchronize_session=False)
            )
            if updated == 0:
                self._session.rollback()
                return False
            self._add(replacement)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return True

    def revoke(self, token_hash: str) -> None:
        row: Any = (
            self._session.query(RefreshTokenRow)
            .filter(RefreshTokenRow.token_hash == token_hash)
            .first()
        )
        if row is not None:
            row.revoked = True
            self._session.commit()

    def revoke_all_for_user(self, user_id: UserId) -> None:
        self._session.query(RefreshTokenRow).filter(
            RefreshTokenRow.user_id == int(user_id),
            RefreshTokenRow.revoked == False,
        ).update({"revoked": True})
        self._session.commit()
