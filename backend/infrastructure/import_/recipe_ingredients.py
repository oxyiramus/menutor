from backend.domain.exceptions import ImportValidationError, UnitConversionError
from backend.domain.ports.recipe_repository import RecipeRepository
from backend.domain.value_objects.quantity import Quantity
from backend.domain.value_objects.recipe_ingredient import RecipeIngredient
from backend.domain.value_objects.types import ProductId, RecipeId, UserId


def parse_ingredients(
    raw_ingredients: object,
    repo: RecipeRepository,
    user_id: UserId,
    errors: list[str],
    location: str,
) -> list[RecipeIngredient]:
    if not isinstance(raw_ingredients, list):
        raise ImportValidationError(f"{location}: ожидается массив ингредиентов")

    ingredients = []
    for raw in raw_ingredients:
        if not isinstance(raw, dict):
            raise ImportValidationError(f"{location}: некорректный ингредиент")
        product_id = sub_recipe_id = None
        try:
            if raw.get("product_id") is not None:
                product_id = ProductId(int(raw["product_id"]))
            elif "sub_recipe_id" in raw:
                sub_recipe_id = RecipeId(int(raw["sub_recipe_id"]))
            else:
                continue
        except (ValueError, TypeError, OverflowError) as exc:
            raise ImportValidationError(
                f"{location}: некорректная ссылка на ингредиент"
            ) from exc

        if sub_recipe_id is not None:
            sub = repo.get_by_id(sub_recipe_id)
            if sub is None or sub.user_id != user_id:
                errors.append(
                    f"Рецепт-ингредиент с ID {sub_recipe_id} не найден, пропущен"
                )
                continue

        try:
            ingredients.append(
                RecipeIngredient(
                    product_id=product_id,
                    sub_recipe_id=sub_recipe_id,
                    quantity=Quantity(
                        float(raw["quantity_amount"]), raw["quantity_unit"]
                    ),
                    order=int(raw.get("order", 0)),
                )
            )
        except UnitConversionError as exc:
            raise ImportValidationError(
                f"{location}: неизвестная единица измерения ингредиента"
            ) from exc
        except (KeyError, ValueError, TypeError, OverflowError) as exc:
            raise ImportValidationError(f"{location}: некорректный ингредиент") from exc
    return ingredients
