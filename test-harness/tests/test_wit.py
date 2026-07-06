import pytest

from harness.models import WitFunction
from harness.wit import DuplicateWorldError, WitParseError, discover_worlds

from .conftest import write_wit_file, write_world


def test_no_wit_dir_returns_empty(tmp_path):
    assert discover_worlds(tmp_path) == []


def test_wit_dir_with_no_wit_files_returns_empty(tmp_path):
    (tmp_path / "common" / "wit").mkdir(parents=True)
    assert discover_worlds(tmp_path) == []


def test_only_wit_extension_files_are_scanned(tmp_path):
    write_world(tmp_path, "task-component")
    (tmp_path / "common" / "wit" / "notes.txt").write_text("world should-be-ignored {\n}\n")
    worlds = discover_worlds(tmp_path)
    assert [w.name for w in worlds] == ["task-component"]


def test_single_world_parses_namespace_package_name_and_exports(tmp_path):
    write_world(tmp_path, "task-component")
    worlds = discover_worlds(tmp_path)
    assert len(worlds) == 1
    world = worlds[0]
    assert world.namespace == "common"
    assert world.package == "tasks"
    assert world.name == "task-component"
    assert world.exports == ("task-collections",)


def test_package_version_suffix_is_tolerated(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks@1.2.0;\n\nworld w {\n  export iface;\n}\n",
    )
    worlds = discover_worlds(tmp_path)
    assert worlds[0].namespace == "common"
    assert worlds[0].package == "tasks"


def test_missing_package_declaration_raises_clear_error_naming_the_file(tmp_path):
    write_wit_file(tmp_path, "broken.wit", "world w {\n  export iface;\n}\n")
    with pytest.raises(WitParseError, match="broken.wit"):
        discover_worlds(tmp_path)


def test_multiple_worlds_in_one_package_each_get_their_own_exports(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "world world-a {\n  export task-collections;\n}\n\n"
        "world world-b {\n  export other-iface;\n}\n",
    )
    worlds = discover_worlds(tmp_path)
    by_name = {w.name: w for w in worlds}
    assert set(by_name) == {"world-a", "world-b"}
    assert by_name["world-a"].exports == ("task-collections",)
    assert by_name["world-b"].exports == ("other-iface",)
    # Both worlds still agree on the shared package identity.
    assert by_name["world-a"].namespace == by_name["world-b"].namespace == "common"
    assert by_name["world-a"].package == by_name["world-b"].package == "tasks"


def test_multiple_wit_packages_produce_distinct_namespace_and_package(tmp_path):
    write_wit_file(tmp_path, "a-pkg.wit", "package common:a;\n\nworld world-a {\n  export foo;\n}\n")
    write_wit_file(tmp_path, "b-pkg.wit", "package common:b;\n\nworld world-b {\n  export bar;\n}\n")
    worlds = discover_worlds(tmp_path)
    by_name = {w.name: w for w in worlds}
    assert by_name["world-a"].namespace == "common"
    assert by_name["world-a"].package == "a"
    assert by_name["world-b"].namespace == "common"
    assert by_name["world-b"].package == "b"


def test_duplicate_world_names_across_packages_hard_fail_naming_both(tmp_path):
    write_wit_file(tmp_path, "a.wit", "package common:a;\n\nworld shared {\n  export foo;\n}\n")
    write_wit_file(tmp_path, "b.wit", "package common:b;\n\nworld shared {\n  export bar;\n}\n")
    with pytest.raises(DuplicateWorldError) as excinfo:
        discover_worlds(tmp_path)
    message = str(excinfo.value)
    assert "shared" in message
    assert "common:a" in message
    assert "common:b" in message


def test_line_and_doc_comments_are_ignored(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "// leading file comment\n"
        "/// doc comment above package\n"
        "package common:tasks; // trailing comment\n"
        "\n"
        "/// doc comment above interface\n"
        "interface task-collections {\n"
        "    /// doc comment above function\n"
        "    count-tasks: func(tasks: string) -> u32; // trailing\n"
        "}\n"
        "\n"
        "/// doc comment above world\n"
        "world task-component {\n"
        "  // a comment inside the world block\n"
        "  export task-collections; /// trailing doc on export\n"
        "}\n",
    )
    worlds = discover_worlds(tmp_path)
    assert len(worlds) == 1
    world = worlds[0]
    assert world.exports == ("task-collections",)
    assert world.function_signature("task-collections", "count-tasks") == WitFunction(
        name="count-tasks", params=("tasks",), param_types=("string",), returns="u32"
    )


def test_interface_function_params_parsed_in_declared_order(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface task-collections {\n"
        "    record task {\n"
        "        name: string,\n"
        "    }\n\n"
        "    count-tasks: func(tasks: list<task>) -> u32;\n"
        "}\n\n"
        "world task-component {\n  export task-collections;\n}\n",
    )
    worlds = discover_worlds(tmp_path)
    world = worlds[0]
    fn = world.function_signature("task-collections", "count-tasks")
    assert fn == WitFunction(
        name="count-tasks", params=("tasks",), param_types=("list<task>",), returns="u32"
    )


def test_function_param_order_matches_declaration_not_alphabetical(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface ordering {\n"
        "  combine: func(b: string, a: string) -> string;\n"
        "}\n\n"
        "world w {\n  export ordering;\n}\n",
    )
    worlds = discover_worlds(tmp_path)
    fn = worlds[0].function_signature("ordering", "combine")
    assert fn.params == ("b", "a")


def test_param_names_split_on_top_level_commas_with_nested_generics(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  do-it: func(pairs: list<tuple<u32, u32>>, label: string) -> bool;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    worlds = discover_worlds(tmp_path)
    fn = worlds[0].function_signature("things", "do-it")
    assert fn.params == ("pairs", "label")


def test_multiline_function_signature_is_parsed(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  do-it: func(\n"
        "    tasks: list<task>,\n"
        "    label: string,\n"
        "  ) -> u32;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    worlds = discover_worlds(tmp_path)
    fn = worlds[0].function_signature("things", "do-it")
    assert fn.params == ("tasks", "label")


def test_function_with_no_params_parses_to_empty_tuple(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  ping: func() -> bool;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    worlds = discover_worlds(tmp_path)
    fn = worlds[0].function_signature("things", "ping")
    assert fn.params == ()


def test_non_function_simple_statements_are_ignored(tmp_path):
    """A `;`-terminated statement that isn't a function signature (e.g. a
    type alias) has no braces, so it is not filtered out by the nested-block
    check -- it must instead simply fail to match the function pattern and
    be skipped, leaving only the real function behind."""
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  type task-id = u32;\n"
        "  do-it: func(a: string) -> string;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    world = discover_worlds(tmp_path)[0]
    iface = world.interfaces["things"]
    assert set(iface.functions) == {"do-it"}
    assert iface.functions["do-it"].params == ("a",)


def test_function_with_no_return_type_is_parsed(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  log: func(message: string);\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    worlds = discover_worlds(tmp_path)
    fn = worlds[0].function_signature("things", "log")
    assert fn.params == ("message",)
    assert fn.returns is None


def test_function_param_types_captured_alongside_names(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  combine: func(a: string, b: u32) -> string;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    fn = discover_worlds(tmp_path)[0].function_signature("things", "combine")
    assert fn.params == ("a", "b")
    assert fn.param_types == ("string", "u32")


def test_function_return_type_text_is_captured_verbatim(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  get-count: func() -> u64;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    fn = discover_worlds(tmp_path)[0].function_signature("things", "get-count")
    assert fn.returns == "u64"


def test_record_fields_parsed_in_declared_order_with_type_text(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  record widget {\n"
        "    id: u32,\n"
        "    label: string,\n"
        "  }\n\n"
        "  make: func(w: widget) -> bool;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    world = discover_worlds(tmp_path)[0]
    iface = world.interfaces["things"]
    assert set(iface.records) == {"widget"}
    record = iface.records["widget"]
    assert record.field_names == ("id", "label")
    assert [f.type for f in record.fields] == ["u32", "string"]
    # The function's declared param type text is captured too, so
    # `harness.contracts` can discover that `w: widget` reaches `widget`.
    fn = world.function_signature("things", "make")
    assert fn.param_types == ("widget",)


def test_interface_with_no_records_has_empty_records_mapping(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  ping: func() -> bool;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    world = discover_worlds(tmp_path)[0]
    assert world.interfaces["things"].records == {}


def test_interface_with_multiple_functions_captures_each_distinctly(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  first: func(a: string) -> bool;\n"
        "  second: func(x: u32, y: u32) -> u32;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    world = discover_worlds(tmp_path)[0]
    assert world.function_signature("things", "first").params == ("a",)
    assert world.function_signature("things", "second").params == ("x", "y")


def test_function_signature_returns_none_for_unexported_interface(tmp_path):
    """A world's ``exports`` may name an interface the harness cannot find a
    signature for (e.g. it belongs to a different package, or is not
    defined at all). ``function_signature`` returns ``None`` instead of
    raising, so callers (the CLI) can hard-fail with a clear message rather
    than crash."""
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\nworld w {\n  export not-defined-anywhere;\n}\n",
    )
    world = discover_worlds(tmp_path)[0]
    assert world.function_signature("not-defined-anywhere", "whatever") is None


def test_function_signature_returns_none_for_unknown_function_name(tmp_path):
    write_world(tmp_path, "task-component")
    world = discover_worlds(tmp_path)[0]
    assert world.function_signature("task-collections", "no-such-function") is None


def test_two_worlds_in_same_package_share_the_same_interface_definitions(tmp_path):
    """Interfaces are declared once per package; every world in that
    package -- whichever interfaces it exports -- can look up the same
    function signatures."""
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface task-collections {\n"
        "  count-tasks: func(tasks: list<task>) -> u32;\n"
        "}\n\n"
        "world world-a {\n  export task-collections;\n}\n\n"
        "world world-b {\n  export task-collections;\n}\n",
    )
    worlds = discover_worlds(tmp_path)
    by_name = {w.name: w for w in worlds}
    assert by_name["world-a"].function_signature("task-collections", "count-tasks").params == (
        "tasks",
    )
    assert by_name["world-b"].function_signature("task-collections", "count-tasks").params == (
        "tasks",
    )
