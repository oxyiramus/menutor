from backend.domain.exceptions import ImportValidationError
from backend.domain.ports.category_repository import CategoryRepository
from backend.domain.value_objects.types import UserId


def resolve_category_id(
    raw_id: object,
    raw_name: object,
    repo: CategoryRepository | None,
    user_id: UserId,
    location: str,
) -> int:
    if (raw_id is None or raw_id == "") and isinstance(raw_name, str) and raw_name:
        category_id = repo.find_id_by_name(raw_name, user_id) if repo else None
        trimmed_name = raw_name.strip()
        if category_id is None and repo and trimmed_name and trimmed_name != raw_name:
            category_id = repo.find_id_by_name(trimmed_name, user_id)
        if category_id is None:
            raise ImportValidationError(f"{location}: категория не найдена")
        return category_id
    if isinstance(raw_id, float) and raw_id.is_integer():
        return int(raw_id)
    try:
        return int(str(raw_id))
    except (ValueError, TypeError) as exc:
        raise ImportValidationError(
            f"{location}: некорректное значение 'category_id'"
        ) from exc
