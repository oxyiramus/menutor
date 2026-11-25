"""Process environment settings for import limits."""

import os
import sys


def _positive_limit(key: str, default: int) -> int:
    value = int(os.environ.get(key, str(default)))
    if not 0 < value < sys.maxsize:
        raise ValueError(f"{key} must be a positive integer below {sys.maxsize}")
    return value


def max_file_bytes() -> int:
    return _positive_limit("IMPORT_MAX_FILE_BYTES", 1024 * 1024)


def max_records() -> int:
    return _positive_limit("IMPORT_MAX_RECORDS", 1000)
