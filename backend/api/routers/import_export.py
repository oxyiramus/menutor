import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from backend.api.auth import get_current_user
from backend.api.deps import get_container
from backend.api.schemas.import_export import ImportResultResponse
from backend.composition_root import ApplicationContainer
from backend.domain.entities.user import User
from backend.domain.exceptions import ImportLimitExceededError, ImportValidationError
from backend.import_limits import max_file_bytes

router = APIRouter(tags=["import-export"])
logger = logging.getLogger(__name__)


@router.get("/{entity_type}/export/{format}")
def export_entities(
    *,
    entity_type: str,
    format: str,
    ids: str | None = None,
    container: Annotated[ApplicationContainer, Depends(get_container)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    id_list = [int(x) for x in ids.split(",")] if ids else None
    data, content_type, filename = container.export_entities.execute(
        entity_type,
        format,
        user.id,
        id_list,
    )
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{entity_type}/export/{format}/example")
def export_example(
    *,
    entity_type: str,
    format: str,
    container: Annotated[ApplicationContainer, Depends(get_container)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    data, content_type, filename = container.export_entities.example(
        entity_type, format, user.id
    )
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{entity_type}/import/{format}", response_model=ImportResultResponse)
def import_entities(
    *,
    entity_type: str,
    format: str,
    file: Annotated[UploadFile, File(...)],
    container: Annotated[ApplicationContainer, Depends(get_container)],
    user: Annotated[User, Depends(get_current_user)],
) -> ImportResultResponse:
    try:
        limit = max_file_bytes()
        data = file.file.read(limit + 1)
        if len(data) > limit:
            raise ImportLimitExceededError(f"Размер файла превышает {limit} байт")
        result = container.import_entities.execute(entity_type, format, data, user.id)
    except ImportLimitExceededError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from None
    except ImportValidationError:
        raise
    except Exception:  # noqa: BLE001 - Translate unexpected import failures at the HTTP boundary.
        logger.error("Техническая ошибка импорта")
        raise HTTPException(
            status_code=500, detail="Не удалось выполнить импорт"
        ) from None
    return ImportResultResponse(
        created=result.created, updated=result.updated, errors=result.errors
    )
