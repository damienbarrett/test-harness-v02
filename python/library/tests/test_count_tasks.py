import json
from pathlib import Path
import pytest

from tasks import Task, count_tasks

COMMON_DIR = Path(__file__).resolve().parent.parent.parent.parent / "common"
TESTS_PATH = COMMON_DIR / "functions" / "task-collections" / "count-tasks.test.json"


def load_test_cases():
    with open(TESTS_PATH) as f:
        data = json.load(f)
    return [(t["description"], t["input"], t["expected"]) for t in data["tests"]]


@pytest.mark.parametrize("description,input_data,expected", load_test_cases())
def test_count_tasks(description, input_data, expected):
    tasks = [Task(name=t["name"]) for t in input_data["tasks"]]
    result = count_tasks(tasks)
    assert result == expected, f"{description}: expected {expected}, got {result}"
