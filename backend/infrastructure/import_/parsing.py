import csv
import io
import json
from collections.abc import Iterator
from typing import Any

from backend.domain.exceptions import ImportValidationError, UnitConversionError
from backend.domain.value_objects.quantity import Quantity


def json_rows(data: bytes) -> list[Any]:
    try:
        rows = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ImportValidationError("Некорректный JSON") from exc
    if not isinstance(rows, list):
        raise ImportValidationError("JSON должен быть массивом объектов")
    return rows


def csv_rows(data: bytes) -> Iterator[dict[str, str]]:
    try:
        yield from csv.DictReader(
            io.StringIO(data.decode("utf-8")), restval="", strict=True
        )
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ImportValidationError("Не удалось прочитать CSV") from exc


def parse_int(value: Any, field: str, location: str) -> int:
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ImportValidationError(
            f"{location}: некорректное значение '{field}'"
        ) from exc


def validate_unit(unit: str, field: str, location: str) -> str:
    try:
        Quantity(0, unit)
    except UnitConversionError as exc:
        raise ImportValidationError(
            f"{location}: неизвестная единица измерения в поле '{field}'"
        ) from exc
    return unit
