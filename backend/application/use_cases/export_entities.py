from typing import Any

from backend.domain.exceptions import ImportValidationError
from backend.domain.ports.category_repository import CategoryRepository
from backend.domain.ports.menu_repository import MenuRepository
from backend.domain.ports.product_repository import ProductRepository
from backend.domain.ports.recipe_repository import RecipeRepository
from backend.domain.value_objects.types import UserId
from backend.infrastructure.export.registry import ExportRegistry


class ExportEntities:
    """Export a user's entities by type and format.

    Returns (bytes, content_type, filename).
    """

    def __init__(
        self,
        export_registry: ExportRegistry,
        product_repo: ProductRepository,
        recipe_repo: RecipeRepository,
        menu_repo: MenuRepository,
        product_categories: CategoryRepository | None = None,
        recipe_categories: CategoryRepository | None = None,
    ) -> None:
        self._registry = export_registry
        self._product_repo = product_repo
        self._recipe_repo = recipe_repo
        self._menu_repo = menu_repo
        self._categories = {
            "products": product_categories,
            "recipes": recipe_categories,
        }

    def execute(
        self,
        entity_type: str,
        format: str,
        user_id: UserId,
        entity_ids: list[int] | None = None,
    ) -> tuple[bytes, str, str]:
        exporter = self._registry.get(entity_type, format)
        if exporter is None:
            raise ImportValidationError(
                f"Формат '{format}' не поддерживается для '{entity_type}'"
            )
        entities = self._load_entities(entity_type, user_id, entity_ids)
        data = exporter.export_bytes(entities)
        filename = f"{entity_type}.{exporter.file_extension()}"
        return data, exporter.content_type(), filename

    def example(
        self, entity_type: str, format: str, user_id: UserId | None = None
    ) -> tuple[bytes, str, str]:
        exporter = self._registry.get(entity_type, format)
        if exporter is None:
            raise ImportValidationError(
                f"Формат '{format}' не поддерживается для '{entity_type}'"
            )
        filename = f"example_{entity_type}.{exporter.file_extension()}"
        categories = self._categories.get(entity_type)
        category_id = None
        if user_id is not None and categories is not None and format != "json_compact":
            catalog = categories.find_active(user_id) or categories.find_all(user_id)
            if not catalog:
                raise ImportValidationError(
                    "Создайте категорию, чтобы скачать пример импорта"
                )
            category_id = catalog[0].id
        return (
            exporter.example_bytes(category_id=category_id),
            exporter.content_type(),
            filename,
        )

    def _load_entities(
        self,
        entity_type: str,
        user_id: UserId,
        entity_ids: list[int] | None,
    ) -> list[Any]:
        all_entities: list[Any]
        if entity_type == "products":
            all_entities = self._product_repo.find_all(user_id)
            if entity_ids is not None:
                id_set = set(entity_ids)
                return [e for e in all_entities if e.id in id_set]
            return all_entities

        if entity_type == "recipes":
            all_entities = self._recipe_repo.find_all(user_id)
            if entity_ids is not None:
                id_set = set(entity_ids)
                return [e for e in all_entities if e.id in id_set]
            return all_entities

        if entity_type == "menus":
            all_entities = self._menu_repo.find_all(user_id)
            if entity_ids is not None:
                id_set = set(entity_ids)
                return [e for e in all_entities if e.id in id_set]
            return all_entities

        raise ImportValidationError(f"Неизвестный тип сущности: '{entity_type}'")
