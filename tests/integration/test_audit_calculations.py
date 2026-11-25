"""Real persistence and calculation paths (B5, B7, B8 and cost/round-trip gaps)."""

from dataclasses import asdict, replace
from decimal import Decimal

import pytest

from backend.application.use_cases.calculate_recipe_cost import CalculateRecipeCost
from backend.application.use_cases.manage_product import CreateProduct, ProductData
from backend.application.use_cases.manage_recipe import CreateRecipe, RecipeData
from backend.application.use_cases.plan_menu import (
    AddDishToSlot,
    ClearMenu,
    CreateMenu,
    LoadMenu,
)
from backend.application.use_cases.preview_recipe_cost import (
    CostPreviewIngredient,
    CostPreviewRequest,
    PreviewRecipeCost,
)
from backend.domain.entities.menu import MenuSlot
from backend.domain.services.portion_calculator import PortionCalculator
from backend.domain.services.recipe_cost_calculator import RecipeCostCalculator
from backend.domain.services.shopping_list_builder import ShoppingListBuilder
from backend.domain.services.unit_converter import UnitConverter
from backend.domain.value_objects.cooking_step import CookingStep
from backend.domain.value_objects.money import Money
from backend.domain.value_objects.quantity import Quantity
from backend.domain.value_objects.recipe_ingredient import RecipeIngredient
from backend.domain.value_objects.types import (
    MealTypeId,
    ProductCategoryId,
    RecipeCategoryId,
    UserId,
)
from backend.infrastructure.repositories.orm_menu_repository import OrmMenuRepository
from backend.infrastructure.repositories.orm_product_category_repository import (
    OrmProductCategoryRepository,
)
from backend.infrastructure.repositories.orm_product_repository import (
    OrmProductRepository,
)
from backend.infrastructure.repositories.orm_recipe_repository import (
    OrmRecipeRepository,
)


@pytest.fixture
def calculation(conn):
    products, recipes, menus = (
        OrmProductRepository(conn),
        OrmRecipeRepository(conn),
        OrmMenuRepository(conn),
    )
    builder = ShoppingListBuilder(
        recipes,
        products,
        OrmProductCategoryRepository(conn),
        PortionCalculator(),
        UnitConverter(),
    )
    flour = CreateProduct(products).execute(
        ProductData(
            name="Flour",
            category_id=ProductCategoryId(1),
            recipe_unit="g",
            purchase_unit="kg",
            price=Money(Decimal(80)),
            conversion_factor=1000,
            brand="Brand",
            supplier="Supplier",
        ),
        UserId(1),
    )
    milk = CreateProduct(products).execute(
        ProductData(
            name="Milk",
            category_id=ProductCategoryId(2),
            recipe_unit="ml",
            purchase_unit="l",
            price=Money(Decimal(90)),
            conversion_factor=1000,
        ),
        UserId(1),
    )
    return products, recipes, menus, builder, flour, milk


def rich_recipe(calculation, pieces=False):
    _, recipes, _, _, flour, milk = calculation
    return CreateRecipe(recipes).execute(
        RecipeData(
            name="Pancakes",
            category_id=RecipeCategoryId(1),
            servings=4,
            weight=700,
            ingredients=[
                RecipeIngredient(
                    product_id=flour.id, quantity=Quantity(200, "g"), order=1
                ),
                RecipeIngredient(
                    product_id=milk.id, quantity=Quantity(500, "ml"), order=2
                ),
            ],
            steps=[CookingStep(1, "Mix"), CookingStep(2, "Bake")],
            link="https://example.com/recipe",
            comment="Comment",
            total_pieces=8 if pieces else None,
            pieces_per_portion=2 if pieces else None,
        ),
        UserId(1),
    )


@pytest.mark.parametrize("pieces", [False, True])
def test_create_and_reload_preserves_all_fields(conn, calculation, pieces):
    products, recipes, _, _, flour, _ = calculation
    recipe = rich_recipe(calculation, pieces)
    conn.expunge_all()
    assert asdict(recipes.get_by_id(recipe.id)) == asdict(recipe)
    loaded = products.get_by_id(flour.id)
    assert (
        loaded.user_id,
        loaded.brand,
        loaded.supplier,
        loaded.conversion_factor,
        loaded.price_per_purchase_unit,
    ) == (UserId(1), "Brand", "Supplier", 1000, Money(Decimal(80)))
    assert len(recipe.ingredients) == 2
    assert recipe.steps == [CookingStep(1, "Mix"), CookingStep(2, "Bake")]
    assert (recipe.link, recipe.comment, recipe.weight, recipe.user_id) == (
        "https://example.com/recipe",
        "Comment",
        700,
        UserId(1),
    )


@pytest.mark.parametrize("pieces", [False, True])
def test_saved_and_preview_cost_agree_with_manual_amounts(calculation, pieces):
    products, recipes, _, builder, _, _ = calculation
    recipe = rich_recipe(calculation, pieces)
    saved = CalculateRecipeCost(
        recipes, products, builder, RecipeCostCalculator()
    ).execute(recipe.id, UserId(1))
    request = CostPreviewRequest(
        [
            CostPreviewIngredient(
                i.product_id, i.sub_recipe_id, i.quantity.amount, i.quantity.unit
            )
            for i in recipe.ingredients
        ],
        4,
        recipe.total_pieces,
        recipe.pieces_per_portion,
    )
    preview = PreviewRecipeCost(products, builder, RecipeCostCalculator()).execute(
        recipe.id, UserId(1), request
    )
    assert saved == preview
    assert saved.total_cost == pytest.approx(61)
    assert saved.cost_per_portion == pytest.approx(15.25)
    assert not saved.is_partial


def test_pipeline_quantities_cost_and_clear_nonempty_menu(conn, calculation):
    _, _, menus, builder, _, _ = calculation
    recipe = rich_recipe(calculation)
    menu = CreateMenu(menus).execute("Week", UserId(1))
    menu = AddDishToSlot(menus).execute(
        menu.id,
        MenuSlot(
            day=0, meal_type_id=MealTypeId(1), recipe_id=recipe.id, servings_override=4
        ),
        UserId(1),
    )
    result = builder.build(menu)
    items = {i.product_name: i for i in result.items}
    assert items["Flour"].quantity == Quantity(0.2, "kg")
    assert items["Milk"].quantity == Quantity(0.5, "l")
    assert items["Flour"].cost.amount == Decimal(16)
    assert items["Milk"].cost.amount == Decimal(90)
    assert result.total_cost().amount == Decimal(106)
    assert len(LoadMenu(menus).execute(menu.id, UserId(1)).slots) == 1
    ClearMenu(menus).execute(menu.id, UserId(1))
    conn.expunge_all()
    assert LoadMenu(menus).execute(menu.id, UserId(1)).slots == []


@pytest.mark.parametrize("pieces", [False, True])
@pytest.mark.parametrize("weight", [0, 700])
def test_nested_cost_and_zero_weight_partial(calculation, pieces, weight):
    products, recipes, _, builder, _, _ = calculation
    child = rich_recipe(calculation, pieces)
    recipes.save(replace(child, weight=weight))
    parent = CreateRecipe(recipes).execute(
        RecipeData(
            name="Parent",
            category_id=RecipeCategoryId(1),
            servings=2,
            ingredients=[
                RecipeIngredient(
                    sub_recipe_id=child.id,
                    quantity=Quantity(2, "serv") if pieces else Quantity(350, "g"),
                )
            ],
        ),
        UserId(1),
    )
    result = CalculateRecipeCost(
        recipes, products, builder, RecipeCostCalculator()
    ).execute(parent.id, UserId(1))
    if weight == 0 and not pieces:
        assert result.is_partial and result.total_cost is None
    else:
        assert not result.is_partial
        assert result.total_cost == pytest.approx(30.5)


@pytest.mark.parametrize("pieces", [False, True])
def test_filtered_all_and_nested_exclusions_preserve_values(calculation, pieces):
    _, recipes, menus, builder, flour, _ = calculation
    child = rich_recipe(calculation, pieces)
    parent = CreateRecipe(recipes).execute(
        RecipeData(
            name="Parent",
            category_id=RecipeCategoryId(1),
            servings=2,
            ingredients=[
                RecipeIngredient(product_id=flour.id, quantity=Quantity(100, "g")),
                RecipeIngredient(
                    sub_recipe_id=child.id,
                    quantity=Quantity(2, "serv") if pieces else Quantity(350, "g"),
                ),
            ],
        ),
        UserId(1),
    )
    menu = CreateMenu(menus).execute("Week", UserId(1))
    menu = AddDishToSlot(menus).execute(
        menu.id,
        MenuSlot(
            day=0, meal_type_id=MealTypeId(1), recipe_id=parent.id, servings_override=4
        ),
        UserId(1),
    )
    full = builder.build(menu)
    for exclusions in (None, set()):
        filtered = builder.build_filtered(menu, {0}, excluded_sub_recipe_ids=exclusions)
        assert asdict(filtered) == asdict(full)
    excluded = builder.build_filtered(menu, {0}, excluded_sub_recipe_ids={child.id})
    assert len(excluded.items) == 1
    assert excluded.items[0].product_id == flour.id
    assert excluded.items[0].quantity == Quantity(0.2, "kg")
    assert excluded.items[0].cost.amount == Decimal(16)
