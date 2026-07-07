"""Conversion between declarative JSON test values and Component Model values.

Two directions:

* ``prepare_args`` -- JSON test input to positional call arguments, built in
  the WIT-declared parameter order (never JSON object insertion order), with
  dicts converted to dataclass instances recursively at any depth (inside
  other dicts, inside lists, inside lists of lists) so wasmtime can marshal
  them as WIT records.
* ``normalize_return`` -- a component's return value to plain
  JSON-compatible values, recursively, so it can be compared to a
  declarative ``expected`` value with a bare ``==``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import make_dataclass
from typing import Any, Sequence


def _make_record_class(data: dict) -> object:
    """Convert a dict to a dataclass instance for wasmtime record passing."""
    cls = make_dataclass("Record", list(data.keys()))
    return cls(**data)


def _convert_value(value: Any) -> Any:
    """Recursively convert dicts -- at any depth, including inside lists and
    lists of lists -- to dataclass instances. Non-dict, non-list values
    (scalars, ``None`` for an absent ``option``) pass through unchanged."""
    if isinstance(value, dict):
        return _make_record_class(
            {key: _convert_value(val) for key, val in value.items()}
        )
    if isinstance(value, list):
        return [_convert_value(item) for item in value]
    return value


def prepare_args(raw_input: dict[str, Any], params: Sequence[str]) -> list[Any]:
    """Convert JSON test input into positional args, in WIT-declared order.

    ``params`` is the WIT function's declared parameter names, in declared
    order (see ``harness.wit.WitFunction.params``). Positional arguments are
    built by looking up each declared name in ``raw_input``; the input
    dict's own (JSON object) key order is irrelevant.

    A mismatch between the input's keys and the declared parameters --
    either a declared parameter missing from the input, or an input key
    that is not a declared parameter -- is a hard failure: it means the
    test suite and the WIT contract have drifted apart, and silently
    dropping or ignoring the mismatched key would hide that.
    """
    param_names = list(params)
    missing = [name for name in param_names if name not in raw_input]
    extra = sorted(set(raw_input) - set(param_names))
    if missing or extra:
        raise ValueError(
            "test input does not match the WIT-declared parameters: "
            f"declared={param_names} missing={missing} extra={extra}"
        )
    return [_convert_value(raw_input[name]) for name in param_names]


def normalize_return(value: Any) -> Any:
    """Recursively normalize a component return value into plain
    JSON-compatible values (dicts, lists, and scalars) for comparison
    against a declarative ``expected`` value with a bare ``==``.

    * A ``dataclasses`` instance (as produced by ``prepare_args`` above, and
      by some wasmtime record types) becomes a dict keyed by field name.
    * Any other record-like object -- notably wasmtime's own
      ``component.Record``, which is a plain attribute holder rather than a
      real ``dataclasses`` type -- becomes a dict via an attribute walk
      (``vars()``), the same shape ``dataclasses.asdict`` would produce for
      a true dataclass.
    * Lists and tuples become lists.
    * Dicts are walked (values normalized) but stay dicts.
    * Everything else, including ``None`` for an absent WIT ``option``,
      passes through unchanged.
    """
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: normalize_return(getattr(value, f.name))
            for f in dataclasses.fields(value)
        }
    if isinstance(value, dict):
        return {key: normalize_return(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_return(item) for item in value]
    if hasattr(value, "__dict__"):
        return {key: normalize_return(val) for key, val in vars(value).items()}
    return value
