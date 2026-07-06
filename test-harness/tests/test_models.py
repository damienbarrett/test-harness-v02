from harness.models import TestCase, WitFunction, WitInterface, WitWorld, discover_test_suites

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


def _make_world(**overrides) -> WitWorld:
    defaults = dict(
        namespace="common",
        package="tasks",
        name="task-component",
        exports=("task-collections",),
        interfaces={
            "task-collections": WitInterface(
                name="task-collections",
                functions={
                    "count-tasks": WitFunction(name="count-tasks", params=("tasks",)),
                },
            ),
        },
    )
    defaults.update(overrides)
    return WitWorld(**defaults)


def test_wit_world_exports_interface_true_for_exported_name():
    world = _make_world()
    assert world.exports_interface("task-collections") is True


def test_wit_world_exports_interface_false_for_unexported_name():
    world = _make_world()
    assert world.exports_interface("other-iface") is False


def test_wit_world_interface_export_builds_namespace_package_interface_string():
    world = _make_world()
    assert world.interface_export("task-collections") == "common:tasks/task-collections"


def test_wit_world_interface_export_uses_this_worlds_own_namespace_and_package():
    world = _make_world(namespace="acme", package="widgets")
    assert world.interface_export("task-collections") == "acme:widgets/task-collections"


def test_wit_world_function_signature_looks_up_declared_params():
    world = _make_world()
    fn = world.function_signature("task-collections", "count-tasks")
    assert fn == WitFunction(name="count-tasks", params=("tasks",))


def test_wit_world_function_signature_none_for_unknown_interface():
    world = _make_world()
    assert world.function_signature("no-such-interface", "count-tasks") is None


def test_wit_world_function_signature_none_for_unknown_function():
    world = _make_world()
    assert world.function_signature("task-collections", "no-such-function") is None


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
