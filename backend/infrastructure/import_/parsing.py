import csv
import io
import json
from itertools import islice
from typing import Any

from backend.domain.exceptions import (
    ImportLimitExceededError,
    ImportValidationError,
    UnitConversionError,
)
from backend.domain.value_objects.quantity import Quantity
from backend.import_limits import max_records


def _check_record_count(count: int, limit: int) -> None:
    if count > limit:
        raise ImportLimitExceededError(f"Число записей в файле превышает {limit}")


def json_rows(data: bytes) -> list[Any]:
    try:
        rows = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ImportValidationError("Некорректный JSON") from exc
    if not isinstance(rows, list):
        raise ImportValidationError("JSON должен быть массивом объектов")
    _check_record_count(len(rows), max_records())
    return rows


def csv_rows(data: bytes) -> list[dict[str, str]]:
    limit = max_records()
    try:
        reader = csv.DictReader(
            io.StringIO(data.decode("utf-8")), restval="", strict=True
        )
        rows = list(islice(reader, limit + 1))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ImportValidationError("Не удалось прочитать CSV") from exc
    _check_record_count(len(rows), limit)
    return rows


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
