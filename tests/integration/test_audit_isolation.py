"""Two-owner behavior across real repositories and application boundaries."""

import json
from dataclasses import asdict

import pytest
from sqlalchemy import text

from backend.application.paginated_result import PAGE_SIZE
from backend.application.use_cases.crud_base import (
    DeleteEntity,
    GetEntity,
    PaginatedListEntities,
)
from backend.application.use_cases.export_entities import ExportEntities
from backend.application.use_cases.manage_family import (
    CreateFamilyMember,
    EditFamilyMember,
    FamilyMemberData,
)
from backend.application.use_cases.manage_recipe import (
    CreateRecipe,
    EditRecipe,
    RecipeData,
)
from backend.application.use_cases.plan_menu import ClearMenu, CreateMenu
from backend.domain.exceptions import EntityNotFoundError
from backend.domain.value_objects.types import RecipeCategoryId, UserId
from backend.infrastructure.export.menu_json_exporter import MenuJsonExporter
from backend.infrastructure.export.product_json_exporter import ProductJsonExporter
from backend.infrastructure.export.recipe_json_exporter import RecipeJsonExporter
from backend.infrastructure.export.registry import ExportRegistry
from backend.infrastructure.repositories.orm_family_member_repository import (
    OrmFamilyMemberRepository,
)
from backend.infrastructure.repositories.orm_menu_repository import OrmMenuRepository
from backend.infrastructure.repositories.orm_product_repository import (
    OrmProductRepository,
)
from backend.infrastructure.repositories.orm_recipe_repository import (
    OrmRecipeRepository,
)


@pytest.fixture
def second_owner(conn):
    conn.execute(
        text(
            "INSERT INTO users (id,email,nickname,hashed_password,created_at) VALUES (2,'second@example.com','B','hash','2026-01-01')"
        )
    )
    conn.commit()
    return UserId(2)


@pytest.mark.parametrize("kind", ["recipe", "family", "menu"])
def test_two_owners_read_edit_batch_delete(conn, second_owner, kind):
    uid, other = UserId(1), second_owner
    if kind == "recipe":
        repo = OrmRecipeRepository(conn)
        create = lambda name, owner: CreateRecipe(repo).execute(
            RecipeData(name, RecipeCategoryId(1), 2), owner
        )
        edit = lambda entity: EditRecipe(repo).execute(
            entity.id, RecipeData("Stolen", RecipeCategoryId(1), 2), other
        )
    elif kind == "family":
        repo = OrmFamilyMemberRepository(conn)
        create = lambda name, owner: CreateFamilyMember(repo).execute(
            FamilyMemberData(name), owner
        )
        edit = lambda entity: EditFamilyMember(repo).execute(
            entity.id, FamilyMemberData("Stolen"), other
        )
    else:
        repo = OrmMenuRepository(conn)
        create = lambda name, owner: CreateMenu(repo).execute(name, owner)
        edit = lambda entity: ClearMenu(repo).execute(entity.id, other)
    foreign, own = create("A", uid), create("B", other)
    before = asdict(foreign)
    assert GetEntity(repo).execute(foreign.id, other) is None
    assert [e.id for e in repo.find_all(other)] == [own.id]
    with pytest.raises(EntityNotFoundError):
        edit(foreign)
    DeleteEntity(repo).execute([foreign.id, own.id, 999999], other)
    conn.expunge_all()
    assert repo.get_by_id(own.id) is None
    assert asdict(repo.get_by_id(foreign.id)) == before


def test_recipe_pagination_combines_search_category_owner(conn, second_owner):
    repo = OrmRecipeRepository(conn)
    create = CreateRecipe(repo)
    expected = [
        create.execute(
            RecipeData(f"Apple {i:04}", RecipeCategoryId(1), 2), UserId(1)
        ).id
        for i in range(PAGE_SIZE + 2)
    ]
    create.execute(RecipeData("Apple foreign", RecipeCategoryId(1), 2), second_owner)
    create.execute(
        RecipeData("Apple other category", RecipeCategoryId(2), 2), UserId(1)
    )
    create.execute(RecipeData("Banana", RecipeCategoryId(1), 2), UserId(1))
    pages = [
        PaginatedListEntities(repo).execute(UserId(1), RecipeCategoryId(1), p, "APPLE")
        for p in (1, 2, 3)
    ]
    assert [p.total for p in pages] == [PAGE_SIZE + 2] * 3
    assert [len(p.items) for p in pages] == [PAGE_SIZE, 2, 0]
    assert [e.id for p in pages for e in p.items] == expected


@pytest.mark.parametrize("kind", ["products", "recipes", "menus"])
def test_export_excludes_foreign_ids_even_when_explicitly_requested(
    conn, second_owner, kind
):
    from decimal import Decimal

    from backend.application.use_cases.manage_product import CreateProduct, ProductData
    from backend.domain.value_objects.money import Money
    from backend.domain.value_objects.types import ProductCategoryId

    products, recipes, menus = (
        OrmProductRepository(conn),
        OrmRecipeRepository(conn),
        OrmMenuRepository(conn),
    )
    registry = ExportRegistry()
    registry.register("products", "json", ProductJsonExporter())
    registry.register("recipes", "json", RecipeJsonExporter())
    registry.register("menus", "json", MenuJsonExporter())
    if kind == "products":
        create = lambda name, uid: CreateProduct(products).execute(
            ProductData(name, ProductCategoryId(1), "g", "kg", Money(Decimal(1))), uid
        )
    elif kind == "recipes":
        create = lambda name, uid: CreateRecipe(recipes).execute(
            RecipeData(name, RecipeCategoryId(1), 2), uid
        )
    else:
        create = lambda name, uid: CreateMenu(menus).execute(name, uid)
    own, foreign = create("Visible", UserId(1)), create("Secret", second_owner)
    export = ExportEntities(registry, products, recipes, menus)
    for ids in (None, [own.id, foreign.id, 999999]):
        data, _, _ = export.execute(kind, "json", UserId(1), ids)
        assert [row["name"] for row in json.loads(data)] == ["Visible"]
