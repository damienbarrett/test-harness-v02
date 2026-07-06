"""Shared fixture-tree builders for harness unit tests.

All tests build fake repo trees under ``tmp_path`` -- none of these helpers
touch the real repository, the network, or built ``.wasm`` artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path


def write_wit_file(root: Path, filename: str, text: str) -> Path:
    wit_dir = root / "common" / "wit"
    wit_dir.mkdir(parents=True, exist_ok=True)
    path = wit_dir / filename
    path.write_text(text)
    return path


def write_world(root: Path, world_name: str, exported_interface: str = "task-collections") -> Path:
    """Write a single-package WIT file with one world exporting one
    interface that declares a ``count-tasks(tasks: list<task>) -> u32``
    function -- the same shape as the real ``common/wit/tasks.wit``
    contract, so suite-driven tests that build a ``task-collections/
    count-tasks`` suite (the common case) get a matching WIT signature for
    free."""
    return write_wit_file(
        root,
        "tasks.wit",
        f"package common:tasks;\n\n"
        f"interface {exported_interface} {{\n"
        f"    record task {{\n"
        f"        name: string,\n"
        f"    }}\n\n"
        f"    count-tasks: func(tasks: list<task>) -> u32;\n"
        f"}}\n\n"
        f"world {world_name} {{\n  export {exported_interface};\n}}\n",
    )


def write_suite(root: Path, interface: str, function: str, tests: list[dict]) -> Path:
    d = root / "common" / "functions" / interface
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{function}.test.json"
    path.write_text(json.dumps({"function": function, "tests": tests}))
    return path


def write_component(root: Path, lang: str, world_name: str, content: bytes = b"fake-wasm") -> Path:
    d = root / lang / "component"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{world_name}.wasm"
    path.write_bytes(content)
    return path


# test-harness/tests/conftest.py -> repo root is two levels up.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def write_suite_schema(root: Path) -> Path:
    """Copy the real ``common/schemas/test-suite.schema.json`` into a fake
    repo tree, so contract-validation tests get the canonical suite-format
    schema without duplicating its content by hand (and so a change to the
    real schema is automatically reflected here)."""
    real = _REPO_ROOT / "common" / "schemas" / "test-suite.schema.json"
    dest_dir = root / "common" / "schemas"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "test-suite.schema.json"
    dest.write_text(real.read_text())
    return dest


def write_task_entity_schema(root: Path, *, properties: dict | None = None, required: list | None = None) -> Path:
    """Write ``common/entities/task-schema.json`` -- by default the same
    shape as the real contract's ``task`` record (a single ``name: string``
    field), matching ``write_world``'s default WIT text."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "common/entities/task-schema.json",
        "type": "object",
        "title": "Task",
        "properties": properties if properties is not None else {"name": {"type": "string"}},
        "required": required if required is not None else ["name"],
        "additionalProperties": False,
    }
    d = root / "common" / "entities"
    d.mkdir(parents=True, exist_ok=True)
    path = d / "task-schema.json"
    path.write_text(json.dumps(schema))
    return path


def write_function_schema(
    root: Path,
    interface: str,
    function: str,
    *,
    parameters: dict | None = None,
    returns: dict | None = None,
) -> Path:
    """Write ``common/functions/{interface}/{function}.schema.json``. By
    default declares the same shape as the real ``count-tasks`` contract: a
    single ``tasks: list<task>`` parameter (via a relative ``$ref`` to
    ``task-schema.json``) and a ``u32``-bounded integer return."""
    if parameters is None:
        parameters = {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {"$ref": "../../entities/task-schema.json"},
                },
            },
            "required": ["tasks"],
            "additionalProperties": False,
        }
    if returns is None:
        returns = {"type": "integer", "minimum": 0, "maximum": 4294967295}
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"common/functions/{interface}/{function}.schema.json",
        "name": function,
        "parameters": parameters,
        "returns": returns,
    }
    d = root / "common" / "functions" / interface
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{function}.schema.json"
    path.write_text(json.dumps(schema))
    return path


def write_valid_contract(
    root: Path,
    *,
    interface: str = "task-collections",
    function: str = "count-tasks",
    world_name: str = "task-component",
    tests: list[dict] | None = None,
) -> None:
    """Write a complete contract that ``validate_contracts`` accepts as-is:
    a WIT world exporting ``interface`` with ``function`` declared on it,
    the suite-format schema, a matching entity schema, a matching function
    schema, and the test suite itself -- all agreeing on the default
    ``task-collections``/``count-tasks`` shape unless overridden."""
    if tests is None:
        tests = [{"description": "d", "input": {"tasks": []}, "expected": 0}]
    write_world(root, world_name, exported_interface=interface)
    write_suite_schema(root)
    write_task_entity_schema(root)
    write_function_schema(root, interface, function)
    write_suite(root, interface, function, tests)
