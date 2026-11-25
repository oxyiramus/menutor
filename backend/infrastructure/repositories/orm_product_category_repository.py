from sqlalchemy import select

from backend.domain.exceptions import DomainError
from backend.domain.ports.product_category_repository import ProductCategoryRepository
from backend.infrastructure.database.models import (
    MenuRow,
    MenuSlotRow,
    PreferenceProductRow,
    PreferenceRow,
    ProductCategoryRow,
    ProductRow,
    RecipeIngredientRow,
    RecipeRow,
    ShoppingListItemRow,
    ShoppingListRow,
)
from backend.infrastructure.repositories.base_category import BaseOrmCategoryRepository


class OrmProductCategoryRepository(
    BaseOrmCategoryRepository,
    ProductCategoryRepository,
):
    _cat_class = ProductCategoryRow
    _linked_class = ProductRow

    def _delete_linked(self, category_id: int, user_id: int) -> None:
        products = self._linked(category_id, user_id)
        product_ids = products.with_entities(ProductRow.id).statement
        ingredients = self._session.query(RecipeIngredientRow).filter(
            RecipeIngredientRow.product_id.in_(product_ids)
        )
        slots = self._session.query(MenuSlotRow).filter(
            MenuSlotRow.product_id.in_(product_ids)
        )

        # Older data can contain cross-owner references created before ownership checks.
        foreign_links = (
            ingredients.filter(
                RecipeIngredientRow.recipe_id.in_(
                    select(RecipeRow.id).where(RecipeRow.user_id != user_id)
                )
            ),
            slots.filter(
                MenuSlotRow.menu_id.in_(
                    select(MenuRow.id).where(MenuRow.user_id != user_id)
                )
            ),
            self._session.query(PreferenceProductRow)
            .join(PreferenceRow)
            .filter(
                PreferenceProductRow.product_id.in_(product_ids),
                PreferenceRow.user_id != user_id,
            ),
            self._session.query(ShoppingListItemRow)
            .join(ShoppingListRow)
            .filter(
                ShoppingListItemRow.product_id.in_(product_ids),
                ShoppingListRow.user_id != user_id,
            ),
        )
        if any(query.first() is not None for query in foreign_links):
            raise DomainError("Не удалось удалить категорию со связанными объектами")

        ingredients.delete(synchronize_session=False)
        slots.delete(synchronize_session=False)
        products.delete(synchronize_session=False)
