from dataclasses import dataclass
import json
from pathlib import Path
import pytest
from wasmtime import component, Store, Engine, Config

_TEST_DIR = Path(__file__).resolve().parent
WASM_PATH = _TEST_DIR.parent / "task-component.wasm"
TESTS_PATH = _TEST_DIR.parent.parent.parent / "common" / "functions" / "task-collections" / "count-tasks.test.json"


@dataclass
class TaskValue:
    name: str


def load_test_cases():
    with open(TESTS_PATH) as f:
        data = json.load(f)
    return [(t["description"], t["input"], t["expected"]) for t in data["tests"]]


@pytest.fixture(scope="module")
def count_tasks_func():
    config = Config()
    engine = Engine(config)
    store = Store(engine)

    comp = component.Component.from_file(engine, WASM_PATH)
    linker = component.Linker(engine)
    instance = linker.instantiate(store, comp)

    interface = instance.get_export_index(store, "common:tasks/task-collections")
    assert interface is not None

    count_tasks = instance.get_export_index(store, "count-tasks", interface)
    assert count_tasks is not None

    func = instance.get_func(store, count_tasks)
    assert func is not None

    return store, func


@pytest.mark.parametrize("description,input_data,expected", load_test_cases())
def test_count_tasks(count_tasks_func, description, input_data, expected):
    store, func = count_tasks_func
    tasks = [TaskValue(name=t["name"]) for t in input_data["tasks"]]
    result = func(store, tasks)
    func.post_return(store)
    assert result == expected, f"{description}: expected {expected}, got {result}"
