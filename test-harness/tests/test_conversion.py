from dataclasses import is_dataclass

from harness.conversion import prepare_args


def test_scalar_values_pass_through_as_positional_args():
    assert prepare_args({"count": 3, "name": "x"}) == [3, "x"]


def test_list_of_records_converted_to_dataclass_instances():
    (tasks,) = prepare_args({"tasks": [{"name": "Task 1"}, {"name": "Task 2"}]})
    assert len(tasks) == 2
    assert all(is_dataclass(t) for t in tasks)
    assert [t.name for t in tasks] == ["Task 1", "Task 2"]


def test_list_of_plain_scalars_passed_through_unconverted():
    assert prepare_args({"values": [1, 2, 3]}) == [[1, 2, 3]]


def test_empty_list_input_stays_an_empty_list():
    assert prepare_args({"tasks": []}) == [[]]


def test_top_level_dict_converted_to_record():
    (record,) = prepare_args({"task": {"name": "Task 1"}})
    assert is_dataclass(record)
    assert record.name == "Task 1"


def test_option_none_value_passes_through_unconverted():
    """WIT `option<T>` values arriving as JSON `null` are not record-shaped,
    so they pass straight through as plain ``None`` positional args."""
    assert prepare_args({"maybe_task": None}) == [None]


def test_dict_nested_inside_a_record_is_not_recursively_converted():
    """CHARACTERIZATION: record conversion is only one level deep today.
    A dict value nested inside another dict value (e.g. a WIT `result<T, E>`
    or nested record represented as JSON) is *not* turned into a dataclass;
    it survives as a plain dict attribute on the outer record. Phase 2 makes
    record conversion recursive (docs/refactoring-plan.md Phase 2)."""
    (record,) = prepare_args({"wrapper": {"inner": {"name": "nested"}}})
    assert is_dataclass(record)
    assert record.inner == {"name": "nested"}
    assert not is_dataclass(record.inner)


def test_list_nested_inside_a_record_is_not_recursively_converted():
    """CHARACTERIZATION: a list nested inside a dict value (as opposed to a
    top-level list argument) is not walked for record conversion either."""
    (record,) = prepare_args({"wrapper": {"items": [{"name": "a"}]}})
    assert record.items == [{"name": "a"}]
    assert not is_dataclass(record.items[0])


def test_dict_nested_inside_a_list_item_is_not_recursively_converted():
    """CHARACTERIZATION: a dict value inside a converted list item's own
    dict is one level too deep for the current conversion to reach."""
    (tasks,) = prepare_args({"tasks": [{"name": "t", "meta": {"owner": "alice"}}]})
    task = tasks[0]
    assert is_dataclass(task)
    assert task.meta == {"owner": "alice"}
    assert not is_dataclass(task.meta)
