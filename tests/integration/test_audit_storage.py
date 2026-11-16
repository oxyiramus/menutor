from dataclasses import asdict, replace
from datetime import time

from backend.domain.entities.family_member import FamilyMember
from backend.domain.entities.meal_type import MealType
from backend.domain.entities.preference import Preference
from backend.domain.value_objects.preference_enums import PreferenceMode, PreferenceType
from backend.domain.value_objects.types import (
    FamilyMemberId,
    MealTypeId,
    PreferenceId,
    ProductCategoryId,
    RecipeCategoryId,
    UserId,
)
from backend.infrastructure.repositories.orm_family_member_repository import (
    OrmFamilyMemberRepository,
)
from backend.infrastructure.repositories.orm_meal_type_repository import (
    OrmMealTypeRepository,
)
from backend.infrastructure.repositories.orm_preference_repository import (
    OrmPreferenceRepository,
)


def test_preference_roundtrip_replacement_and_delete_cascades(conn):
    prefs, family = OrmPreferenceRepository(conn), OrmFamilyMemberRepository(conn)
    pref = prefs.save(
        Preference(
            PreferenceId(0),
            "Allergy",
            PreferenceType.ALLERGY,
            PreferenceMode.BLOCKED,
            category_ids=[ProductCategoryId(1)],
            recipe_category_ids=[RecipeCategoryId(1)],
            user_id=UserId(1),
        )
    )
    member = family.save(
        FamilyMember(FamilyMemberId(0), "Member", 0.5, "Comment", UserId(1), [pref.id])
    )
    conn.expunge_all()
    assert asdict(prefs.get_by_id(pref.id)) == asdict(pref)
    assert asdict(family.get_by_id(member.id)) == asdict(member)
    prefs.save(
        replace(
            pref,
            category_ids=[ProductCategoryId(2)],
            recipe_category_ids=[RecipeCategoryId(2)],
        )
    )
    conn.expunge_all()
    assert prefs.get_by_id(pref.id).category_ids == [ProductCategoryId(2)]
    prefs.delete([pref.id])
    conn.expunge_all()
    assert prefs.get_by_id(pref.id) is None
    assert family.get_by_id(member.id).preference_ids == []


def test_custom_meal_type_roundtrip(conn):
    repo = OrmMealTypeRepository(conn)
    meal = repo.save(
        MealType(MealTypeId(0), UserId(1), "Snack", time(15, 30), False, 4)
    )
    conn.expunge_all()
    assert asdict(repo.get_by_id(meal.id)) == asdict(meal)
    assert meal.id in {m.id for m in repo.find_all(UserId(1))}
    repo.delete([meal.id])
    assert repo.get_by_id(meal.id) is None
