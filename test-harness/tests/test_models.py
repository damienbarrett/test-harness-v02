from harness.models import TestCase, discover_test_suites

from .conftest import write_suite


def test_no_functions_dir_returns_empty(tmp_path):
    assert discover_test_suites(tmp_path) == []


def test_functions_dir_with_no_suites_returns_empty(tmp_path):
    (tmp_path / "common" / "functions").mkdir(parents=True)
    assert discover_test_suites(tmp_path) == []


def test_discovers_suite_and_derives_interface_function_from_path(tmp_path):
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [{"description": "d1", "input": {"tasks": []}, "expected": 0}],
    )
    suites = discover_test_suites(tmp_path)
    assert len(suites) == 1
    suite = suites[0]
    assert suite.interface == "task-collections"
    assert suite.function == "count-tasks"
    assert suite.path == (
        tmp_path / "common" / "functions" / "task-collections" / "count-tasks.test.json"
    )
    assert suite.tests == [TestCase(description="d1", input={"tasks": []}, expected=0)]


def test_multiple_suites_discovered_in_sorted_path_order(tmp_path):
    write_suite(tmp_path, "b-iface", "fn-b", [{"description": "d", "input": {}, "expected": 1}])
    write_suite(tmp_path, "a-iface", "fn-a", [{"description": "d", "input": {}, "expected": 1}])
    suites = discover_test_suites(tmp_path)
    assert [s.interface for s in suites] == ["a-iface", "b-iface"]


def test_suite_with_multiple_cases_preserves_order(tmp_path):
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [
            {"description": "first", "input": {"tasks": []}, "expected": 0},
            {"description": "second", "input": {"tasks": [{"name": "x"}]}, "expected": 1},
        ],
    )
    suites = discover_test_suites(tmp_path)
    assert [c.description for c in suites[0].tests] == ["first", "second"]
