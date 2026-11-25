from decimal import Decimal, InvalidOperation

from backend.domain.entities.product import Product
from backend.domain.exceptions import ImportValidationError
from backend.domain.ports.category_repository import CategoryRepository
from backend.domain.ports.product_repository import ProductRepository
from backend.domain.value_objects.import_result import ImportResult
from backend.domain.value_objects.money import Money
from backend.domain.value_objects.types import ProductCategoryId, ProductId, UserId
from backend.infrastructure.import_.category import resolve_category_id
from backend.infrastructure.import_.parsing import json_rows, parse_int, validate_unit

_REQUIRED = {"name", "category_id", "recipe_unit", "purchase_unit", "price_amount"}


class ProductJsonImporter:
    def __init__(
        self, repo: ProductRepository, categories: CategoryRepository | None = None
    ) -> None:
        self._repo = repo
        self._categories = categories

    def import_from_bytes(self, data: bytes, user_id: UserId) -> ImportResult:
        if not data.strip():
            return ImportResult(created=0, updated=0)

        created = updated = 0
        for i, row in enumerate(json_rows(data), start=1):
            if not isinstance(row, dict):
                raise ImportValidationError(f"Элемент {i}: ожидается объект")

            missing = _REQUIRED - set(row.keys())
            if row.get("category_name"):
                missing.discard("category_id")
            if missing:
                raise ImportValidationError(
                    f"Элемент {i}: отсутствуют обязательные поля: {', '.join(sorted(missing))}"
                )
            if not str(row.get("name", "")).strip():
                raise ImportValidationError(
                    f"Элемент {i}: поле 'name' не может быть пустым"
                )

            try:
                price_amount = Decimal(str(row["price_amount"]))
            except InvalidOperation:
                raise ImportValidationError(
                    f"Элемент {i}: некорректное значение 'price_amount'"
                )

            category_id = resolve_category_id(
                row.get("category_id"),
                row.get("category_name"),
                self._categories,
                user_id,
                f"Элемент {i}",
            )

            try:
                conversion_factor = float(row.get("conversion_factor") or 1.0)
            except ValueError, TypeError, OverflowError:
                raise ImportValidationError(
                    f"Элемент {i}: некорректное значение 'conversion_factor'"
                )

            raw_id = parse_int(row.get("id") or 0, "id", f"Элемент {i}")
            existing = self._repo.get_by_id(ProductId(raw_id)) if raw_id > 0 else None
            if existing is not None and existing.user_id == user_id:
                entity_id = existing.id
                updated += 1
            else:
                entity_id = ProductId(0)
                created += 1

            product = Product(
                id=entity_id,
                name=str(row["name"]).strip(),
                recipe_unit=validate_unit(
                    str(row["recipe_unit"]).strip(), "recipe_unit", f"Элемент {i}"
                ),
                purchase_unit=validate_unit(
                    str(row["purchase_unit"]).strip(), "purchase_unit", f"Элемент {i}"
                ),
                price_per_purchase_unit=Money(
                    price_amount,
                    str(row.get("price_currency") or "RUB").strip(),
                ),
                brand=str(row.get("brand") or "").strip(),
                supplier=str(row.get("supplier") or "").strip(),
                conversion_factor=conversion_factor,
                category_id=ProductCategoryId(category_id),
                user_id=user_id,
            )
            self._repo.save(product)

        return ImportResult(created=created, updated=updated)

    def supported_extensions(self) -> list[str]:
        return ["json"]
