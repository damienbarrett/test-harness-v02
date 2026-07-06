"""Conversion of declarative JSON test input into Component Model call args.

Phase 1 preserves current behavior exactly, including its known limitation:
only one level of dict-to-record conversion is performed (dicts nested
inside lists become dataclass instances; dicts nested inside other dicts do
not get converted). Phase 2 makes record conversion recursive.
"""

from __future__ import annotations

from dataclasses import make_dataclass
from typing import Any


def _make_record_class(data: dict) -> object:
    """Convert a dict to a dataclass instance for wasmtime record passing."""
    cls = make_dataclass("Record", list(data.keys()))
    return cls(**data)


def prepare_args(raw_input: dict[str, Any]) -> list[Any]:
    """Convert JSON input to positional args with record conversion.

    Each top-level value in the input dict becomes a positional argument
    (matching the Component Model calling convention). Dicts nested inside
    lists are converted to dataclass instances so wasmtime can marshal them
    as WIT records.
    """
    args: list[Any] = []
    for val in raw_input.values():
        if isinstance(val, list):
            args.append([_make_record_class(item) if isinstance(item, dict) else item for item in val])
        elif isinstance(val, dict):
            args.append(_make_record_class(val))
        else:
            args.append(val)
    return args
