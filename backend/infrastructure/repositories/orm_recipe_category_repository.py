from sqlalchemy import select

from backend.domain.exceptions import DomainError
from backend.domain.ports.recipe_category_repository import RecipeCategoryRepository
from backend.infrastructure.database.models import (
    CookingStepRow,
    MenuRow,
    MenuSlotRow,
    RecipeCategoryRow,
    RecipeIngredientRow,
    RecipeRow,
)
from backend.infrastructure.repositories.base_category import BaseOrmCategoryRepository


class OrmRecipeCategoryRepository(
    BaseOrmCategoryRepository,
    RecipeCategoryRepository,
):
    _cat_class = RecipeCategoryRow
    _linked_class = RecipeRow

    def _delete_linked(self, category_id: int, user_id: int) -> None:
        recipes = self._linked(category_id, user_id)
        recipe_ids = recipes.with_entities(RecipeRow.id).statement
        slots = self._session.query(MenuSlotRow).filter(
            MenuSlotRow.recipe_id.in_(recipe_ids)
        )
        if (
            slots.filter(
                MenuSlotRow.menu_id.in_(
                    select(MenuRow.id).where(MenuRow.user_id != user_id)
                )
            ).first()
            is not None
        ):
            raise DomainError("Не удалось удалить категорию со связанными объектами")

        self._session.query(RecipeIngredientRow).filter(
            RecipeIngredientRow.recipe_id.in_(recipe_ids)
        ).delete(synchronize_session=False)
        self._session.query(CookingStepRow).filter(
            CookingStepRow.recipe_id.in_(recipe_ids)
        ).delete(synchronize_session=False)
        slots.delete(synchronize_session=False)
        recipes.delete(synchronize_session=False)
