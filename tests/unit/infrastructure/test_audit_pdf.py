from decimal import Decimal
from io import BytesIO

import pytest
from pypdf import PdfReader
from pypdf.generic import ContentStream
from reportlab.lib.pagesizes import A3, A4, landscape

from backend.domain.entities.menu import MenuSlot, WeeklyMenu
from backend.domain.entities.shopping_list import ShoppingList, ShoppingListItem
from backend.domain.value_objects.money import Money
from backend.domain.value_objects.quantity import Quantity
from backend.domain.value_objects.types import MealTypeId, MenuId, ProductId, RecipeId
from backend.infrastructure.export.menu_pdf_exporter import MenuPdfExporter
from backend.infrastructure.export.shopping_list_pdf_exporter import (
    ShoppingListPdfExporter,
)


def read(data):
    return PdfReader(BytesIO(data))


def text(pdf):
    return " ".join(" ".join(page.extract_text().split()) for page in pdf.pages)


def has_red(pdf):
    return any(
        op == b"rg" and [float(x) for x in args] == [1, 0, 0]
        for page in pdf.pages
        for args, op in ContentStream(page.get_contents(), pdf).operations
    )


@pytest.mark.parametrize(("paper", "size"), [("a4", A4), ("a3", A3)])
def test_menu_pdf_actual_page_size_content_and_color(paper, size):
    menu = WeeklyMenu(
        MenuId(1),
        "Меню",
        [
            MenuSlot(
                day=0,
                meal_type_id=MealTypeId(1),
                recipe_id=RecipeId(1),
                servings_override=2,
            )
        ],
    )
    pdf = read(
        MenuPdfExporter().export_bytes(
            menu,
            {1: "Блины"},
            {},
            paper=paper,
            meal_type_names={1: "Завтрак"},
            recipe_colors={1: "#ff0000"},
        )
    )
    assert tuple(float(v) for v in pdf.pages[0].mediabox[2:]) == pytest.approx(
        landscape(size), abs=0.01
    )
    content = text(pdf)
    assert "Блины" in content
    assert "2п" in content
    assert has_red(pdf)


def test_menu_pdf_long_names_and_many_meal_types_are_not_lost():
    names = {
        i: f"Блюдо{i} с очень длинным названием и дополнительным описанием"
        for i in range(1, 16)
    }
    menu = WeeklyMenu(
        MenuId(1),
        "Меню",
        [
            MenuSlot(day=i % 7, meal_type_id=MealTypeId(i), recipe_id=RecipeId(i))
            for i in names
        ],
    )
    pdf = read(
        MenuPdfExporter().export_bytes(
            menu, names, {}, meal_type_names={i: f"Прием{i}" for i in names}
        )
    )
    content = text(pdf)
    for i in names:
        assert f"Блюдо{i} " in content
        assert f"Прием{i}" in content


def test_shopping_pdf_contains_every_item_quantity_total_and_category_color():
    items = [
        ShoppingListItem(
            ProductId(i),
            f"Продукт{i}",
            "Категория",
            Quantity(i, "kg"),
            Money(Decimal(i * 10)),
        )
        for i in range(1, 46)
    ]
    pdf = read(
        ShoppingListPdfExporter().export_bytes(
            [ShoppingList(items)], category_colors={"Категория": "#ff0000"}
        )
    )
    content = text(pdf)
    for i in range(1, 46):
        assert f"Продукт{i}" in content
    assert "45" in content
    assert "10350" in content.replace(" ", "").replace(",", "")
    assert has_red(pdf)


def test_shopping_pdf_prints_exact_recipe_buy_quantities_and_cost():
    item = ShoppingListItem(
        ProductId(1), "Мука", "Категория", Quantity(2.5, "kg"), Money(Decimal(125))
    )
    content = text(read(ShoppingListPdfExporter().export_bytes([ShoppingList([item])])))
    assert "Мука 2.5 кг 3 кг 125.00 руб" in content
    assert "Итого: 125.00 руб" in content
