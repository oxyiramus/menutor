"""Tests for RecipeIngredientSchema XOR validation and new schema types."""

import pytest
from pydantic import ValidationError

from backend.api.schemas.recipe import (
    RecipeIngredientSchema,
    ValidateSubRecipeRequest,
)


class TestRecipeIngredientSchemaValidation:
    def test_ingredient_schema_product_valid(self) -> None:
        schema = RecipeIngredientSchema(
            product_id=1,
            sub_recipe_id=None,
            quantity_amount=200.0,
            quantity_unit="g",
        )
        assert schema.product_id == 1
        assert schema.sub_recipe_id is None

    def test_ingredient_schema_sub_recipe_valid(self) -> None:
        schema = RecipeIngredientSchema(
            product_id=None,
            sub_recipe_id=5,
            quantity_amount=1.0,
            quantity_unit="serv",
        )
        assert schema.sub_recipe_id == 5
        assert schema.product_id is None

    def test_ingredient_schema_both_set_invalid(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            RecipeIngredientSchema(
                product_id=1,
                sub_recipe_id=5,
                quantity_amount=100.0,
                quantity_unit="g",
            )
        assert "ИЛИ" in str(exc_info.value)

    def test_ingredient_schema_neither_set_invalid(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            RecipeIngredientSchema(
                product_id=None,
                sub_recipe_id=None,
                quantity_amount=100.0,
                quantity_unit="g",
            )
        assert "ИЛИ" in str(exc_info.value)

    def test_ingredient_schema_backward_compat_no_sub_recipe_field(self) -> None:
        """Old requests without sub_recipe_id key default to None — XOR passes."""
        data = {"product_id": 3, "quantity_amount": 150.0, "quantity_unit": "ml"}
        schema = RecipeIngredientSchema.model_validate(data)
        assert schema.product_id == 3
        assert schema.sub_recipe_id is None

    def test_ingredient_schema_sub_recipe_name_is_optional(self) -> None:
        schema = RecipeIngredientSchema(
            sub_recipe_id=7,
            sub_recipe_name="Соус",
            quantity_amount=1.0,
            quantity_unit="serv",
        )
        assert schema.sub_recipe_name == "Соус"


class TestValidateSubRecipeSchemas:
    def test_validate_request_without_parent(self) -> None:
        req = ValidateSubRecipeRequest(sub_recipe_id=2)
        assert req.parent_recipe_id is None
