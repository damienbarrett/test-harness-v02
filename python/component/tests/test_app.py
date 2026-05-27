"""Host-side contract tests for the Python component entry point.

These tests import the *real* wit-bindgen-generated `wit_world` bindings (made
importable via `conftest.py`) and exercise `app.TaskCollections` against real
`Task` dataclass instances. Loading the actual generated abstract Protocol
catches signature drift between `app.py` and `common/wit/tasks.wit` at host
test time — replacing an earlier mocked harness that accepted `[object(),
object()]` and only verified `len()`, which never actually exercised the
contract.

The complementary `test_wasm_count_tasks.py` runs the compiled `.wasm`
through wasmtime; this file pins the host-side surface that gets compiled
into it.
"""

import json
from pathlib import Path

import pytest

# Provided by the generated bindings package emitted to `../bindings/` by
# `componentize-py bindings` (see Taskfile.yml / justfile `build` target).
from wit_world.exports.task_collections import Task

# Provided by `src/app.py`.
from app import TaskCollections

_TESTS_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "common"
    / "functions"
    / "task-collections"
    / "count-tasks.test.json"
)


def _load_test_cases():
    with open(_TESTS_PATH) as fh:
        return [
            (case["description"], case["input"], case["expected"])
            for case in json.load(fh)["tests"]
        ]


@pytest.mark.parametrize("description,input_data,expected", _load_test_cases())
def test_count_tasks_matches_contract(description, input_data, expected):
    tasks = [Task(name=t["name"]) for t in input_data["tasks"]]
    actual = TaskCollections().count_tasks(tasks)
    assert actual == expected, f"{description}: expected {expected}, got {actual}"
