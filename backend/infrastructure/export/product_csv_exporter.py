import csv
import io
from typing import Any, ClassVar

from backend.domain.entities.product import Product


class ProductCsvExporter:
    """Exports Product entities to CSV bytes."""

    _HEADERS: ClassVar[list[str]] = [
        "id",
        "name",
        "category_id",
        "recipe_unit",
        "purchase_unit",
        "price_amount",
        "price_currency",
        "brand",
        "supplier",
        "conversion_factor",
    ]

    def export_bytes(self, entities: list[Any]) -> bytes:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(self._HEADERS)
        for p in entities:
            product: Product = p
            writer.writerow(
                [
                    product.id,
                    product.name,
                    product.category_id,
                    product.recipe_unit,
                    product.purchase_unit,
                    str(product.price_per_purchase_unit.amount),
                    product.price_per_purchase_unit.currency,
                    product.brand,
                    product.supplier,
                    product.conversion_factor,
                ]
            )
        return buf.getvalue().encode("utf-8")

    def example_bytes(self, *, category_id: int | None = None) -> bytes:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(self._HEADERS)
        writer.writerow(
            [None, "Мука", category_id, "g", "kg", "60.00", "RUB", "", "", 1000]
        )
        writer.writerow(
            [None, "Молоко", category_id, "ml", "l", "80.00", "RUB", "", "", 1000]
        )
        return buf.getvalue().encode("utf-8")

    def content_type(self) -> str:
        return "text/csv; charset=utf-8"

    def file_extension(self) -> str:
        return "csv"
