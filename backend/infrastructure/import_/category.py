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
    if (
        (raw_id is None or raw_id == "")
        and isinstance(raw_name, str)
        and raw_name.strip()
    ):
        category_id = repo.find_id_by_name(raw_name.strip(), user_id) if repo else None
        if category_id is None:
            raise ImportValidationError(f"{location}: категория не найдена")
        return category_id
    try:
        return int(str(raw_id))
    except (ValueError, TypeError) as exc:
        raise ImportValidationError(
            f"{location}: некорректное значение 'category_id'"
        ) from exc
