from decimal import Decimal

import pytest

from backend.domain.exceptions import CurrencyMismatchError
from backend.domain.value_objects.money import Money
from backend.domain.value_objects.quantity import Quantity


@pytest.mark.parametrize(("unit", "amount", "ml"), [("tsp", 3, 15), ("tbsp", 2, 30)])
def test_spoons_convert_to_ml_and_l(unit, amount, ml):
    assert Quantity(amount, unit).convert_to("ml") == Quantity(ml, "ml")
    assert Quantity(amount, unit).convert_to("l") == Quantity(ml / 1000, "l")
    assert Quantity(ml, "ml").convert_to(unit) == Quantity(amount, unit)


def test_money_sum_retains_decimal_precision():
    assert Money(Decimal(".1")) + Money(Decimal(".2")) == Money(Decimal(".3"))
    assert Money(Decimal("19.99")) * 3 == Money(Decimal("59.97"))


def test_money_sum_rejects_different_currencies():
    with pytest.raises(CurrencyMismatchError):
        Money(Decimal(1), "RUB") + Money(Decimal(1), "USD")
