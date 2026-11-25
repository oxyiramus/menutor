from backend.domain.entities.recipe import Recipe
from backend.domain.exceptions import ImportValidationError
from backend.domain.ports.category_repository import CategoryRepository
from backend.domain.ports.recipe_repository import RecipeRepository
from backend.domain.value_objects.cooking_step import CookingStep
from backend.domain.value_objects.import_result import ImportResult
from backend.domain.value_objects.types import (
    RecipeCategoryId,
    RecipeId,
    UserId,
)
from backend.infrastructure.import_.category import resolve_category_id
from backend.infrastructure.import_.parsing import json_rows, parse_int
from backend.infrastructure.import_.recipe_ingredients import parse_ingredients

_REQUIRED = {"name", "servings"}


class RecipeJsonImporter:
    def __init__(
        self, repo: RecipeRepository, categories: CategoryRepository | None = None
    ) -> None:
        self._repo = repo
        self._categories = categories

    def import_from_bytes(self, data: bytes, user_id: UserId) -> ImportResult:
        if not data.strip():
            return ImportResult(created=0, updated=0)

        created = updated = 0
        errors: list[str] = []
        for i, row in enumerate(json_rows(data), start=1):
            if not isinstance(row, dict):
                raise ImportValidationError(f"Элемент {i}: ожидается объект")

            missing = _REQUIRED - set(row.keys())
            if missing:
                raise ImportValidationError(
                    f"Элемент {i}: отсутствуют обязательные поля: {', '.join(sorted(missing))}"
                )
            if not str(row.get("name", "")).strip():
                raise ImportValidationError(
                    f"Элемент {i}: поле 'name' не может быть пустым"
                )

            try:
                servings = int(row["servings"])
            except ValueError, TypeError, OverflowError:
                raise ImportValidationError(
                    f"Элемент {i}: некорректное значение 'servings'"
                )

            raw_ingredients = row.get("ingredients") or []
            ingredients = parse_ingredients(
                raw_ingredients, self._repo, user_id, errors, f"Элемент {i}"
            )

            try:
                raw_steps = row.get("steps") or []
                steps = [
                    CookingStep(
                        order=int(s["order"]), description=str(s["description"])
                    )
                    for s in raw_steps
                ]
            except (
                ValueError,
                TypeError,
                KeyError,
                OverflowError,
                RecursionError,
            ) as exc:
                raise ImportValidationError(f"Элемент {i}: некорректный шаг") from exc

            category_id = resolve_category_id(
                row.get("category_id"),
                row.get("category_name"),
                self._categories,
                user_id,
                f"Элемент {i}",
            )

            raw_id = parse_int(row.get("id") or 0, "id", f"Элемент {i}")
            existing = self._repo.get_by_id(RecipeId(raw_id)) if raw_id > 0 else None
            if existing is not None and existing.user_id == user_id:
                entity_id = existing.id
                updated += 1
            else:
                entity_id = RecipeId(0)
                created += 1

            raw_link = row.get("link")
            raw_comment = row.get("comment")
            recipe = Recipe(
                id=entity_id,
                name=str(row["name"]).strip(),
                servings=servings,
                ingredients=ingredients,
                steps=steps,
                category_id=RecipeCategoryId(category_id),
                weight=parse_int(row.get("weight") or 0, "weight", f"Элемент {i}"),
                user_id=user_id,
                total_pieces=(
                    parse_int(row["total_pieces"], "total_pieces", f"Элемент {i}")
                    if row.get("total_pieces") is not None
                    else None
                ),
                pieces_per_portion=(
                    parse_int(
                        row["pieces_per_portion"], "pieces_per_portion", f"Элемент {i}"
                    )
                    if row.get("pieces_per_portion") is not None
                    else None
                ),
                link=str(raw_link) if raw_link is not None else None,
                comment=str(raw_comment) if raw_comment is not None else None,
            )
            self._repo.save(recipe)

        return ImportResult(created=created, updated=updated, errors=errors)

    def supported_extensions(self) -> list[str]:
        return ["json"]
