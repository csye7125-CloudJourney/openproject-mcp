"""Shared input validation helpers used by tool impls.

Pulled out of server.py during the tools/ refactor. Behavior is identical
so the existing tests still pass against the same rules.
"""

from typing import Any


def validate_input(value: Any, field_name: str, max_length: int = 1000) -> str:
    if value is None:
        raise ValueError(f"{field_name} cannot be None")
    str_value = str(value).strip()
    if not str_value:
        raise ValueError(f"{field_name} cannot be empty")
    if len(str_value) > max_length:
        raise ValueError(f"{field_name} cannot exceed {max_length} characters")
    for char in ['<', '>', '"', "'", '&', '\x00', '\r', '\n']:
        if char in str_value:
            str_value = str_value.replace(char, '')
    return str_value


def validate_id(id_value: Any, field_name: str) -> str:
    if id_value is None:
        raise ValueError(f"{field_name} is required")
    str_id = str(id_value).strip()
    if not str_id.replace('-', '').replace('_', '').isalnum():
        raise ValueError(f"{field_name} contains invalid characters")
    if len(str_id) > 100:
        raise ValueError(f"{field_name} is too long")
    return str_id
