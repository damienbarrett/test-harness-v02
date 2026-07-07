from dataclasses import is_dataclass, make_dataclass

import pytest

from harness.conversion import normalize_return, prepare_args


class FakeWasmtimeRecord:
    """Mimics ``wasmtime.component``'s real ``Record`` type: a plain
    attribute holder that is *not* a ``dataclasses`` instance. This is what
    actual component calls return for WIT records -- as opposed to the
    ``dataclasses.make_dataclass`` instances the harness itself builds (in
    ``_make_record_class``) to pass values *into* a component."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


# --- prepare_args: parameter ordering and mismatch detection ---------------


def test_positional_args_follow_declared_param_order():
    assert prepare_args({"count": 3, "name": "x"}, params=("count", "name")) == [3, "x"]


def test_positional_args_use_wit_declared_order_not_json_insertion_order():
    """The WIT contract, not the JSON object's own key order, decides
    positional argument order."""
    raw_input = {"a": "A", "b": "B"}  # JSON insertion order: a, b
    assert prepare_args(raw_input, params=("b", "a")) == ["B", "A"]


def test_missing_declared_param_is_a_hard_failure():
    with pytest.raises(ValueError, match=r"missing=\['b'\]"):
        prepare_args({"a": 1}, params=("a", "b"))


def test_extra_input_key_not_in_params_is_a_hard_failure():
    with pytest.raises(ValueError, match=r"extra=\['c'\]"):
        prepare_args({"a": 1, "b": 2, "c": 3}, params=("a", "b"))


def test_mismatch_error_names_the_declared_params():
    with pytest.raises(ValueError, match=r"declared=\['tasks'\]"):
        prepare_args({"wrong-key": []}, params=("tasks",))


def test_empty_params_with_empty_input_succeeds():
    assert prepare_args({}, params=()) == []


# --- prepare_args: record conversion (now recursive at any depth) --------


def test_list_of_records_converted_to_dataclass_instances():
    (tasks,) = prepare_args(
        {"tasks": [{"name": "Task 1"}, {"name": "Task 2"}]}, params=("tasks",)
    )
    assert len(tasks) == 2
    assert all(is_dataclass(t) for t in tasks)
    assert [t.name for t in tasks] == ["Task 1", "Task 2"]


def test_list_of_plain_scalars_passed_through_unconverted():
    assert prepare_args({"values": [1, 2, 3]}, params=("values",)) == [[1, 2, 3]]


def test_empty_list_input_stays_an_empty_list():
    assert prepare_args({"tasks": []}, params=("tasks",)) == [[]]


def test_top_level_dict_converted_to_record():
    (record,) = prepare_args({"task": {"name": "Task 1"}}, params=("task",))
    assert is_dataclass(record)
    assert record.name == "Task 1"


def test_option_none_value_passes_through_unconverted():
    """WIT `option<T>` values arriving as JSON `null` are not record-shaped,
    so they pass straight through as plain ``None`` positional args."""
    assert prepare_args({"maybe_task": None}, params=("maybe_task",)) == [None]


def test_dict_nested_inside_a_record_is_recursively_converted():
    (record,) = prepare_args(
        {"wrapper": {"inner": {"name": "nested"}}}, params=("wrapper",)
    )
    assert is_dataclass(record)
    assert is_dataclass(record.inner)
    assert record.inner.name == "nested"


def test_list_nested_inside_a_record_is_recursively_converted():
    (record,) = prepare_args(
        {"wrapper": {"items": [{"name": "a"}]}}, params=("wrapper",)
    )
    assert is_dataclass(record.items[0])
    assert record.items[0].name == "a"


def test_dict_nested_inside_a_list_item_is_recursively_converted():
    (tasks,) = prepare_args(
        {"tasks": [{"name": "t", "meta": {"owner": "alice"}}]}, params=("tasks",)
    )
    task = tasks[0]
    assert is_dataclass(task)
    assert is_dataclass(task.meta)
    assert task.meta.owner == "alice"


def test_deeply_nested_records_lists_of_lists_of_records_are_converted():
    (grid,) = prepare_args(
        {"grid": [[{"name": "a"}], [{"name": "b"}, {"name": "c"}]]}, params=("grid",)
    )
    assert is_dataclass(grid[0][0])
    assert grid[0][0].name == "a"
    assert is_dataclass(grid[1][0])
    assert is_dataclass(grid[1][1])
    assert [t.name for t in grid[1]] == ["b", "c"]


def test_record_containing_list_of_records_each_containing_a_nested_record():
    (outer,) = prepare_args(
        {
            "outer": {
                "items": [
                    {
                        "name": "first",
                        "detail": {"owner": "alice", "tags": [{"label": "x"}]},
                    },
                ],
            }
        },
        params=("outer",),
    )
    assert is_dataclass(outer)
    item = outer.items[0]
    assert is_dataclass(item)
    assert is_dataclass(item.detail)
    assert item.detail.owner == "alice"
    assert is_dataclass(item.detail.tags[0])
    assert item.detail.tags[0].label == "x"


# --- normalize_return -------------------------------------------------------


def test_normalize_return_passes_through_plain_scalars():
    assert normalize_return(42) == 42
    assert normalize_return("x") == "x"
    assert normalize_return(True) is True


def test_normalize_return_leaves_none_as_none():
    """A WIT `option<T>` that comes back absent stays `None`."""
    assert normalize_return(None) is None


def test_normalize_return_converts_tuple_to_list():
    assert normalize_return((1, 2, 3)) == [1, 2, 3]


def test_normalize_return_converts_dataclass_record_to_dict():
    record_cls = make_dataclass("Record", ["name"])
    assert normalize_return(record_cls(name="Task 1")) == {"name": "Task 1"}


def test_normalize_return_recurses_into_nested_dataclasses():
    inner_cls = make_dataclass("Inner", ["name"])
    outer_cls = make_dataclass("Outer", ["inner", "items"])
    value = outer_cls(
        inner=inner_cls(name="a"), items=[inner_cls(name="b"), inner_cls(name="c")]
    )
    assert normalize_return(value) == {
        "inner": {"name": "a"},
        "items": [{"name": "b"}, {"name": "c"}],
    }


def test_normalize_return_converts_non_dataclass_record_like_object_via_attribute_walk():
    """Real wasmtime component calls return ``wasmtime.component.Record``
    instances, which are plain attribute holders, not ``dataclasses``
    instances. ``normalize_return`` must handle this shape too, not just
    the harness's own ``make_dataclass`` doubles."""
    value = FakeWasmtimeRecord(name="Task 1")
    assert normalize_return(value) == {"name": "Task 1"}


def test_normalize_return_recurses_into_nested_non_dataclass_records():
    inner = FakeWasmtimeRecord(owner="alice")
    outer = FakeWasmtimeRecord(
        name="t", meta=inner, tags=[FakeWasmtimeRecord(label="x")]
    )
    assert normalize_return(outer) == {
        "name": "t",
        "meta": {"owner": "alice"},
        "tags": [{"label": "x"}],
    }


def test_normalize_return_walks_dict_values_without_changing_shape():
    assert normalize_return({"a": (1, 2), "b": None}) == {"a": [1, 2], "b": None}
