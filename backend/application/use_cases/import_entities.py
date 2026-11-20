from sqlalchemy.orm import Session

from backend.domain.exceptions import (
    DomainError,
    EntityNotFoundError,
    ImportValidationError,
)
from backend.domain.value_objects.import_result import ImportResult
from backend.domain.value_objects.types import UserId
from backend.infrastructure.export.registry import ImportRegistry


class ImportEntities:
    """Import entities from an uploaded file. All-or-nothing transaction."""

    def __init__(self, import_registry: ImportRegistry, session: Session) -> None:
        self._registry = import_registry
        self._session = session

    def execute(
        self,
        entity_type: str,
        format: str,
        data: bytes,
        user_id: UserId,
    ) -> ImportResult:
        importer = self._registry.get(entity_type, format)
        if importer is None:
            raise ImportValidationError(
                "Тип данных или формат файла не поддерживается для импорта"
            )
        previous_transaction = self._session.info.get("import_transaction")
        self._session.info["import_transaction"] = True
        try:
            result = importer.import_from_bytes(data, user_id)
            self._session.commit()
            return result
        except (DomainError, EntityNotFoundError) as exc:
            self._session.rollback()
            raise ImportValidationError(
                "Запись содержит недопустимые данные или недоступную ссылку"
            ) from exc
        except Exception:
            self._session.rollback()
            raise
        finally:
            if previous_transaction is None:
                self._session.info.pop("import_transaction", None)
            else:
                self._session.info["import_transaction"] = previous_transaction
