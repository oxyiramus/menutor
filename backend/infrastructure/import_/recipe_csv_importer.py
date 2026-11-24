import json

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
from backend.infrastructure.import_.parsing import csv_rows, parse_int
from backend.infrastructure.import_.recipe_ingredients import parse_ingredients

_REQUIRED = {"name", "category_id", "servings"}


class RecipeCsvImporter:
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
        for i, row in enumerate(csv_rows(data), start=2):
            missing = _REQUIRED - set(row.keys())
            if row.get("category_name"):
                missing.discard("category_id")
            if missing:
                raise ImportValidationError(
                    f"Строка {i}: отсутствуют обязательные поля: {', '.join(sorted(missing))}"
                )
            if not row.get("name", "").strip():
                raise ImportValidationError(
                    f"Строка {i}: поле 'name' не может быть пустым"
                )

            try:
                servings = int(row["servings"])
            except ValueError:
                raise ImportValidationError(
                    f"Строка {i}: некорректное значение 'servings'"
                )

            category_id = resolve_category_id(
                row.get("category_id"),
                row.get("category_name"),
                self._categories,
                user_id,
                f"Строка {i}",
            )

            try:
                weight = int(row.get("weight") or 0)
            except ValueError:
                raise ImportValidationError(
                    f"Строка {i}: некорректное значение 'weight'"
                )

            try:
                raw_ingredients = json.loads(row.get("ingredients_json") or "[]")
            except (ValueError, RecursionError) as exc:
                raise ImportValidationError(
                    f"Строка {i}: некорректный 'ingredients_json'"
                ) from exc
            ingredients = parse_ingredients(
                raw_ingredients, self._repo, user_id, errors, f"Строка {i}"
            )

            try:
                raw_steps = json.loads(row.get("steps_json") or "[]")
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
                raise ImportValidationError(
                    f"Строка {i}: некорректный 'steps_json'"
                ) from exc

            raw_id = parse_int(row.get("id") or 0, "id", f"Строка {i}")
            existing = self._repo.get_by_id(RecipeId(raw_id)) if raw_id > 0 else None
            if existing is not None and existing.user_id == user_id:
                entity_id = existing.id
                updated += 1
            else:
                entity_id = RecipeId(0)
                created += 1

            raw_link = row.get("link") or None
            raw_comment = row.get("comment") or None
            recipe = Recipe(
                id=entity_id,
                name=row["name"].strip(),
                servings=servings,
                ingredients=ingredients,
                steps=steps,
                category_id=RecipeCategoryId(category_id),
                weight=weight,
                user_id=user_id,
                total_pieces=(
                    parse_int(row["total_pieces"], "total_pieces", f"Строка {i}")
                    if row.get("total_pieces")
                    else None
                ),
                pieces_per_portion=(
                    parse_int(
                        row["pieces_per_portion"], "pieces_per_portion", f"Строка {i}"
                    )
                    if row.get("pieces_per_portion")
                    else None
                ),
                link=raw_link,
                comment=raw_comment,
            )
            self._repo.save(recipe)

        return ImportResult(created=created, updated=updated, errors=errors)

    def supported_extensions(self) -> list[str]:
        return ["csv"]
