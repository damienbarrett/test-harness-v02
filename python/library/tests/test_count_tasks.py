import copy
import json
from pathlib import Path
import pytest
from jsonschema import validate

from tasks import Task, count_tasks

COMMON_DIR = Path(__file__).resolve().parent.parent.parent.parent / "common"
TESTS_PATH = COMMON_DIR / "functions" / "task-collections" / "count-tasks.test.json"
FUNCTION_SCHEMA_PATH = COMMON_DIR / "functions" / "task-collections" / "count-tasks.schema.json"
TASK_SCHEMA_PATH = COMMON_DIR / "entities" / "task-schema.json"


def load_test_cases():
    with open(TESTS_PATH) as f:
        data = json.load(f)
    return [(t["description"], t["input"], t["expected"]) for t in data["tests"]]


def load_params_schema():
    with open(FUNCTION_SCHEMA_PATH) as f:
        function_schema = json.load(f)
    with open(TASK_SCHEMA_PATH) as f:
        task_schema = json.load(f)
    params = copy.deepcopy(function_schema["parameters"])
    params["properties"]["tasks"]["items"] = task_schema
    return params, function_schema["returns"]


@pytest.mark.parametrize("description,input_data,expected", load_test_cases())
def test_count_tasks(description, input_data, expected):
    tasks = [Task(name=t["name"]) for t in input_data["tasks"]]
    result = count_tasks(tasks)
    assert result == expected, f"{description}: expected {expected}, got {result}"


@pytest.mark.parametrize("description,input_data,expected", load_test_cases())
def test_test_data_conforms_to_schema(description, input_data, expected):
    params_schema, returns_schema = load_params_schema()
    validate(instance=input_data, schema=params_schema)
    validate(instance=expected, schema=returns_schema)
