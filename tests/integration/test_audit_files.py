import json
from dataclasses import asdict, replace

import pytest

from backend.application.use_cases.import_entities import ImportEntities
from backend.domain.entities.menu import MenuSlot, WeeklyMenu
from backend.domain.exceptions import ImportValidationError
from backend.domain.value_objects.types import (
    FamilyMemberId,
    MealTypeId,
    MenuId,
    UserId,
)
from backend.infrastructure.export.menu_json_exporter import MenuJsonExporter
from backend.infrastructure.export.product_csv_exporter import ProductCsvExporter
from backend.infrastructure.export.product_json_exporter import ProductJsonExporter
from backend.infrastructure.export.recipe_csv_exporter import RecipeCsvExporter
from backend.infrastructure.export.recipe_json_exporter import RecipeJsonExporter
from backend.infrastructure.export.registry import ImportRegistry
from backend.infrastructure.import_.menu_json_importer import MenuJsonImporter
from backend.infrastructure.import_.product_csv_importer import ProductCsvImporter
from backend.infrastructure.import_.product_json_importer import ProductJsonImporter
from backend.infrastructure.import_.recipe_csv_importer import RecipeCsvImporter
from backend.infrastructure.import_.recipe_json_importer import RecipeJsonImporter
from tests.integration.test_audit_calculations import calculation as calculation  # noqa: PLC0414 -- register pytest fixture
from tests.integration.test_audit_calculations import rich_recipe


@pytest.mark.parametrize("kind", ["product", "recipe"])
@pytest.mark.parametrize("fmt", ["json", "csv"])
def test_full_file_roundtrip_real_database(conn, calculation, kind, fmt):
    products, recipes, _, _, flour, _ = calculation
    entity = flour if kind == "product" else rich_recipe(calculation, True)
    repo = products if kind == "product" else recipes
    exporter, importer = {
        ("product", "json"): (ProductJsonExporter(), ProductJsonImporter(products)),
        ("product", "csv"): (ProductCsvExporter(), ProductCsvImporter(products)),
        ("recipe", "json"): (RecipeJsonExporter(), RecipeJsonImporter(recipes)),
        ("recipe", "csv"): (RecipeCsvExporter(), RecipeCsvImporter(recipes)),
    }[kind, fmt]
    data = exporter.export_bytes([entity])
    # Mutate the stored entity first: re-import must restore exported data.
    repo.save(replace(entity, name="Changed"))
    registry = ImportRegistry()
    registry.register(kind, fmt, importer)
    result = ImportEntities(registry, conn).execute(kind, fmt, data, UserId(1))
    assert result.updated == 1 and result.created == 0
    conn.expunge_all()
    assert asdict(repo.get_by_id(entity.id)) == asdict(entity)


def test_menu_full_json_roundtrip_preserves_members_and_piece_overrides(
    conn, calculation
):
    from backend.domain.entities.family_member import FamilyMember
    from backend.infrastructure.repositories.orm_family_member_repository import (
        OrmFamilyMemberRepository,
    )

    _, _, menus, _, _, _ = calculation
    recipe = rich_recipe(calculation, True)
    member = OrmFamilyMemberRepository(conn).save(
        FamilyMember(FamilyMemberId(0), "Child", 0.5, user_id=UserId(1))
    )
    menu = menus.save(
        WeeklyMenu(
            MenuId(0),
            "Week",
            [
                MenuSlot(
                    day=1,
                    meal_type_id=MealTypeId(1),
                    recipe_id=recipe.id,
                    pieces_override=3,
                    position=2,
                    member_ids=[member.id],
                )
            ],
            UserId(1),
        )
    )
    data = MenuJsonExporter().export_bytes([menu])
    menus.save(replace(menu, slots=[]))
    MenuJsonImporter(menus).import_from_bytes(data, UserId(1))
    conn.expunge_all()
    assert asdict(menus.get_by_id(menu.id)) == asdict(menu)


@pytest.mark.parametrize("reference", ["foreign", "missing"])
def test_recipe_import_subrecipe_warning_and_no_forbidden_link(
    conn, calculation, reference
):
    _, recipes, _, _, _, _ = calculation
    child = rich_recipe(calculation)
    uid = UserId(1)
    if reference == "foreign":
        conn.execute(
            __import__("sqlalchemy").text(
                "INSERT INTO users (id,email,nickname,hashed_password,created_at) VALUES (2,'b@example.com','B','h','2026-01-01')"
            )
        )
        conn.commit()
        uid = UserId(2)
    data = json.dumps(
        [
            {
                "name": "Parent",
                "category_id": 1,
                "servings": 2,
                "ingredients": [
                    {
                        "sub_recipe_id": int(child.id)
                        if reference == "foreign"
                        else 999999,
                        "quantity_amount": 1,
                        "quantity_unit": "serv",
                    }
                ],
            }
        ]
    ).encode()
    result = RecipeJsonImporter(recipes).import_from_bytes(data, uid)
    assert result.errors
    assert recipes.find_by_name("Parent", uid).ingredients == []


@pytest.mark.parametrize("cycle", ["self", "depth"])
def test_recipe_import_rejects_cycle_or_excessive_depth(conn, calculation, cycle):
    _, recipes, _, _, _, _ = calculation
    child = rich_recipe(calculation)
    registry = ImportRegistry()
    registry.register("recipes", "json", RecipeJsonImporter(recipes))
    if cycle == "self":
        rows = [
            {
                "id": int(child.id),
                "name": child.name,
                "category_id": 1,
                "servings": 4,
                "ingredients": [
                    {
                        "sub_recipe_id": int(child.id),
                        "quantity_amount": 1,
                        "quantity_unit": "serv",
                    }
                ],
            }
        ]
    else:
        from backend.application.use_cases.manage_recipe import CreateRecipe, RecipeData
        from backend.domain.value_objects.quantity import Quantity
        from backend.domain.value_objects.recipe_ingredient import RecipeIngredient
        from backend.domain.value_objects.types import RecipeCategoryId

        for i in range(5):
            child = CreateRecipe(recipes).execute(
                RecipeData(
                    name=f"Level{i}",
                    category_id=RecipeCategoryId(1),
                    servings=2,
                    ingredients=[
                        RecipeIngredient(
                            sub_recipe_id=child.id, quantity=Quantity(1, "serv")
                        )
                    ],
                ),
                UserId(1),
            )
        rows = [
            {
                "name": "Too deep",
                "category_id": 1,
                "servings": 2,
                "ingredients": [
                    {
                        "sub_recipe_id": int(child.id),
                        "quantity_amount": 1,
                        "quantity_unit": "serv",
                    }
                ],
            }
        ]
    before = [asdict(r) for r in recipes.find_all(UserId(1))]
    with pytest.raises(ImportValidationError):
        ImportEntities(registry, conn).execute(
            "recipes", "json", json.dumps(rows).encode(), UserId(1)
        )
    conn.expunge_all()
    assert [asdict(r) for r in recipes.find_all(UserId(1))] == before


@pytest.mark.parametrize(
    "kind", ["products-csv", "recipes-json", "recipes-csv", "menus-json"]
)
@pytest.mark.parametrize("update", [False, True])
def test_all_importers_rollback_on_later_invalid_record(
    conn, calculation, kind, update
):
    import csv
    import io

    _, recipes, menus, _, flour, _ = calculation
    products = calculation[0]
    if kind == "products-csv":
        entity, repo, exporter, importer = (
            flour,
            products,
            ProductCsvExporter(),
            ProductCsvImporter(products),
        )
    elif kind.startswith("recipes"):
        entity, repo = rich_recipe(calculation, True), recipes
        exporter, importer = (
            (RecipeJsonExporter(), RecipeJsonImporter(recipes))
            if kind.endswith("json")
            else (RecipeCsvExporter(), RecipeCsvImporter(recipes))
        )
    else:
        entity = menus.save(WeeklyMenu(MenuId(0), "Week", [], UserId(1)))
        repo, exporter, importer = menus, MenuJsonExporter(), MenuJsonImporter(menus)
    data = exporter.export_bytes(
        [replace(entity, id=entity.id if update else 0, name="Imported")]
    )
    if kind.endswith("json"):
        rows = json.loads(data)
        data = json.dumps(rows + [{"name": ""}]).encode()
    else:
        reader = csv.DictReader(io.StringIO(data.decode()))
        rows = list(reader)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(rows + [dict.fromkeys(reader.fieldnames, "")])
        data = output.getvalue().encode()
    registry = ImportRegistry()
    registry.register(kind, "file", importer)
    before = [asdict(e) for e in repo.find_all(UserId(1))]
    with pytest.raises(ImportValidationError):
        ImportEntities(registry, conn).execute(kind, "file", data, UserId(1))
    conn.expunge_all()
    assert [asdict(e) for e in repo.find_all(UserId(1))] == before
    # A failed import must leave a usable session.
    assert (
        ImportEntities(registry, conn)
        .execute(kind, "file", exporter.export_bytes([entity]), UserId(1))
        .updated
        == 1
    )


@pytest.mark.parametrize("reference", ["foreign-product", "missing-product"])
def test_import_does_not_create_invalid_product_links(conn, calculation, reference):
    from sqlalchemy import text

    _, recipes, _, _, flour, _ = calculation
    uid = UserId(1)
    if reference == "foreign-product":
        conn.execute(
            text(
                "INSERT INTO users (id,email,nickname,hashed_password,created_at) VALUES (2,'b@example.com','B','h','2026-01-01')"
            )
        )
        conn.commit()
        uid = UserId(2)
    row = {
        "name": "Attempt",
        "category_id": 1,
        "servings": 2,
        "ingredients": [
            {
                "product_id": int(flour.id) if uid == 2 else 999999,
                "quantity_amount": 100,
                "quantity_unit": "g",
            }
        ],
    }
    registry = ImportRegistry()
    registry.register("recipes", "json", RecipeJsonImporter(recipes))
    try:
        result = ImportEntities(registry, conn).execute(
            "recipes", "json", json.dumps([row]).encode(), uid
        )
    except ImportValidationError:
        assert recipes.find_by_name("Attempt", uid) is None
    else:
        assert result.errors
        assert recipes.find_by_name("Attempt", uid).ingredients == []


@pytest.mark.parametrize(
    "field", ["product_id", "recipe_id", "meal_type_id", "member_ids"]
)
def test_menu_import_rejects_foreign_links(conn, calculation, field):
    from datetime import time

    from sqlalchemy import text

    from backend.domain.entities.family_member import FamilyMember
    from backend.domain.entities.meal_type import MealType
    from backend.infrastructure.repositories.orm_family_member_repository import (
        OrmFamilyMemberRepository,
    )
    from backend.infrastructure.repositories.orm_meal_type_repository import (
        OrmMealTypeRepository,
    )

    _, recipes, menus, _, flour, _ = calculation
    foreign_recipe = rich_recipe(calculation)
    conn.execute(
        text(
            "INSERT INTO users (id,email,nickname,hashed_password,created_at) VALUES (2,'b@example.com','B','h','2026-01-01')"
        )
    )
    conn.commit()
    own_recipe = recipes.save(
        replace(foreign_recipe, id=0, name="Own", user_id=UserId(2), ingredients=[])
    )
    own_meal = OrmMealTypeRepository(conn).save(
        MealType(MealTypeId(0), UserId(2), "Own", time(12), False, 0)
    )
    foreign_member = OrmFamilyMemberRepository(conn).save(
        FamilyMember(FamilyMemberId(0), "Secret", user_id=UserId(1))
    )
    slot = {"day": 0, "meal_type_id": int(own_meal.id), "recipe_id": int(own_recipe.id)}
    if field == "product_id":
        slot.pop("recipe_id")
        slot.update(product_id=int(flour.id), quantity=100, unit="g")
    elif field == "recipe_id":
        slot["recipe_id"] = int(foreign_recipe.id)
    elif field == "meal_type_id":
        slot["meal_type_id"] = 1
    else:
        slot["member_ids"] = [int(foreign_member.id)]
    registry = ImportRegistry()
    registry.register("menus", "json", MenuJsonImporter(menus))
    data = json.dumps([{"name": "Attempt", "slots": [slot]}]).encode()
    with pytest.raises(ImportValidationError):
        ImportEntities(registry, conn).execute("menus", "json", data, UserId(2))
    assert menus.find_all(UserId(2)) == []
