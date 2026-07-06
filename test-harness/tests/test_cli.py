from dataclasses import make_dataclass

from harness import cli

from .conftest import (
    write_component,
    write_function_schema,
    write_suite,
    write_suite_schema,
    write_task_entity_schema,
    write_valid_contract,
    write_wit_file,
    write_world,
)


def test_main_fails_when_no_worlds_found(tmp_path, capsys):
    assert cli.main(tmp_path) == 1
    assert "no worlds found" in capsys.readouterr().err


def test_main_fails_when_no_suites_found(tmp_path, capsys):
    write_world(tmp_path, "task-component")
    assert cli.main(tmp_path) == 1
    assert "no test suites found" in capsys.readouterr().err


def test_main_fails_when_no_implementations_found(tmp_path, capsys):
    write_world(tmp_path, "task-component")
    write_suite(
        tmp_path, "task-collections", "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    assert cli.main(tmp_path) == 1
    assert "no implementation directories found" in capsys.readouterr().err


def test_main_fails_when_duplicate_world_names_are_discovered(tmp_path, capsys):
    """Two packages defining a world with the same name would both need the
    artifact ``shared.wasm`` -- discovery must hard-fail before anything
    else runs, naming both packages."""
    write_wit_file(tmp_path, "a.wit", "package common:a;\n\nworld shared {\n  export foo;\n}\n")
    write_wit_file(tmp_path, "b.wit", "package common:b;\n\nworld shared {\n  export bar;\n}\n")

    exit_code = cli.main(tmp_path)
    err = capsys.readouterr().err

    assert exit_code == 1
    assert "shared" in err
    assert "common:a" in err
    assert "common:b" in err


def test_main_fails_per_case_when_component_artifact_missing(tmp_path, capsys):
    write_valid_contract(tmp_path)
    (tmp_path / "python" / "component").mkdir(parents=True)

    exit_code = cli.main(tmp_path)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "WASM file not found" in out
    assert "1/1 test(s) failed." in out


def test_main_reports_instantiation_failure(tmp_path, monkeypatch, capsys):
    write_valid_contract(tmp_path)
    write_component(tmp_path, "python", "task-component")

    def boom(engine, wasm_path):
        raise RuntimeError("bad wasm module")

    monkeypatch.setattr(cli, "instantiate_component", boom)

    exit_code = cli.main(tmp_path)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "could not instantiate: bad wasm module" in out


def test_main_reports_invocation_failure(tmp_path, monkeypatch, capsys):
    write_valid_contract(tmp_path)
    write_component(tmp_path, "python", "task-component")

    monkeypatch.setattr(cli, "instantiate_component", lambda engine, wasm_path: ("store", "instance"))

    def raise_call(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "call_function", raise_call)

    exit_code = cli.main(tmp_path)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "FAIL [python] d: boom" in out


def test_main_passes_when_actual_matches_expected(tmp_path, monkeypatch, capsys):
    write_valid_contract(tmp_path)
    write_component(tmp_path, "python", "task-component")

    monkeypatch.setattr(cli, "instantiate_component", lambda engine, wasm_path: ("store", "instance"))
    monkeypatch.setattr(cli, "call_function", lambda *a, **k: 0)

    exit_code = cli.main(tmp_path)
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "OK   [python] 1/1 passed" in out
    assert "OK: 1/1 tests passed across 1 implementation(s)." in out


def test_main_reports_mismatch_between_actual_and_expected(tmp_path, monkeypatch, capsys):
    write_valid_contract(tmp_path)
    write_component(tmp_path, "python", "task-component")

    monkeypatch.setattr(cli, "instantiate_component", lambda engine, wasm_path: ("store", "instance"))
    monkeypatch.setattr(cli, "call_function", lambda *a, **k: 99)

    exit_code = cli.main(tmp_path)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "expected 0, got 99" in out
    assert "FAIL [python] 1/1 failed" in out


def test_main_structured_return_value_normalized_before_comparison(tmp_path, monkeypatch, capsys):
    """A component return value structurally equivalent to ``expected`` but
    differently typed (e.g. a WIT record surfaced as a dataclass instance)
    is normalized to a plain dict before comparison, so it counts as a
    match (docs/refactoring-plan.md Phase 2). The WIT function returns a
    record here (rather than the real contract's `u32`) specifically so
    Phase 3's numeric-conformance check does not apply to this fixture."""
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface task-collections {\n"
        "    record task {\n        name: string,\n    }\n"
        "    count-tasks: func(tasks: list<task>) -> task;\n"
        "}\n\n"
        "world task-component {\n  export task-collections;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_task_entity_schema(tmp_path)
    write_function_schema(
        tmp_path, "task-collections", "count-tasks",
        returns={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    )
    write_suite(
        tmp_path, "task-collections", "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": {"name": "Task 1"}}],
    )
    write_component(tmp_path, "python", "task-component")

    record_cls = make_dataclass("Record", ["name"])
    structured_return = record_cls(name="Task 1")

    monkeypatch.setattr(cli, "instantiate_component", lambda engine, wasm_path: ("store", "instance"))
    monkeypatch.setattr(cli, "call_function", lambda *a, **k: structured_return)

    exit_code = cli.main(tmp_path)
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "OK   [python] 1/1 passed" in out


def test_main_runs_suite_only_against_worlds_that_export_its_interface(tmp_path, monkeypatch, capsys):
    """A suite runs only against the world(s) that export its interface --
    never the full Cartesian product of every suite and every world
    (docs/refactoring-plan.md Phase 2)."""
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface task-collections {\n"
        "    record task {\n        name: string,\n    }\n"
        "    count-tasks: func(tasks: list<task>) -> u32;\n"
        "}\n\n"
        "world world-a {\n  export task-collections;\n}\n\n"
        "world world-b {\n  export other-iface;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_task_entity_schema(tmp_path)
    write_function_schema(tmp_path, "task-collections", "count-tasks")
    write_suite(
        tmp_path, "task-collections", "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    write_component(tmp_path, "python", "world-a")
    # No component for world-b at all -- it must never be touched, since
    # this suite's interface is not among its exports.

    monkeypatch.setattr(cli, "instantiate_component", lambda engine, wasm_path: ("store", "instance"))
    monkeypatch.setattr(cli, "call_function", lambda *a, **k: 0)

    exit_code = cli.main(tmp_path)
    out = capsys.readouterr().out

    assert exit_code == 0
    assert out.count("world=world-a") == 1
    assert "world=world-b" not in out
    assert "OK: 1/1 tests passed across 1 implementation(s)." in out


def test_main_hard_fails_when_no_world_exports_the_suites_interface(tmp_path, capsys):
    """A suite whose interface is exported by no discovered world is a hard
    failure, caught by contract validation before any component is
    touched (docs/refactoring-plan.md Phase 2 and Phase 3) -- never a
    silent skip."""
    write_wit_file(
        tmp_path, "tasks.wit", "package common:tasks;\n\nworld w {\n  export other-iface;\n}\n"
    )
    write_suite_schema(tmp_path)
    write_suite(
        tmp_path, "task-collections", "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    write_component(tmp_path, "python", "w")

    exit_code = cli.main(tmp_path)
    err = capsys.readouterr().err

    assert exit_code == 1
    assert "interface 'task-collections' is not exported by any discovered world" in err


def test_main_hard_fails_when_suite_function_not_declared_in_wit_interface(tmp_path, capsys):
    write_world(tmp_path, "task-component")  # declares task-collections.count-tasks only
    write_suite_schema(tmp_path)
    write_suite(
        tmp_path, "task-collections", "not-a-real-function",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    write_component(tmp_path, "python", "task-component")

    exit_code = cli.main(tmp_path)
    err = capsys.readouterr().err

    assert exit_code == 1
    assert (
        "function 'not-a-real-function' is not declared on interface "
        "'task-collections' in the WIT contract" in err
    )


def test_main_hard_fails_before_running_any_suite_when_one_interface_is_unexported(
    tmp_path, monkeypatch, capsys
):
    """Phase 3 changes this from a partial run (the old per-suite loop
    would still execute the valid ``iface-a`` suite while failing
    ``iface-b``) to an all-or-nothing pre-flight gate: ANY contract-invalid
    suite blocks the entire run, including suites that are otherwise
    perfectly valid, and no component is ever instantiated."""
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface iface-a {\n  fn-a: func(x: string) -> string;\n}\n\n"
        "world w {\n  export iface-a;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_function_schema(
        tmp_path, "iface-a", "fn-a",
        parameters={
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
            "additionalProperties": False,
        },
        returns={"type": "string"},
    )
    write_suite(tmp_path, "iface-a", "fn-a", [{"description": "a", "input": {"x": "hi"}, "expected": "hi"}])
    write_suite(tmp_path, "iface-b", "fn-b", [{"description": "b", "input": {"y": 1}, "expected": 1}])
    write_component(tmp_path, "python", "w")

    def boom(engine, wasm_path):
        raise AssertionError("no component may be instantiated when any contract is invalid")

    monkeypatch.setattr(cli, "instantiate_component", boom)

    exit_code = cli.main(tmp_path)
    result = capsys.readouterr()

    assert exit_code == 1
    assert "interface 'iface-b' is not exported by any discovered world" in result.err
    assert "fn-a" not in result.out


def test_main_never_instantiates_a_component_when_contracts_are_invalid(tmp_path, monkeypatch, capsys):
    """End-to-end proof of the Phase 3 "Done when" criterion: an invalid
    contract fails before any component is invoked."""
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    write_suite(
        tmp_path, "task-collections", "not-a-real-function",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    write_component(tmp_path, "python", "task-component")

    def boom(engine, wasm_path):
        raise AssertionError("instantiate_component must not be called when contracts are invalid")

    monkeypatch.setattr(cli, "instantiate_component", boom)

    exit_code = cli.main(tmp_path)
    err = capsys.readouterr().err

    assert exit_code == 1
    assert "FAIL: contract validation failed; no component was invoked:" in err
    assert "function 'not-a-real-function' is not declared" in err


def test_main_uses_wit_declared_param_order_not_json_insertion_order(tmp_path, monkeypatch, capsys):
    """End to end: positional args are built from the WIT function's
    declared parameter order, not the JSON test input's own key order
    (docs/refactoring-plan.md Phase 2)."""
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface ordering {\n"
        "  combine: func(b: string, a: string) -> string;\n"
        "}\n\n"
        "world w {\n  export ordering;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_function_schema(
        tmp_path, "ordering", "combine",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
            "required": ["a", "b"],
            "additionalProperties": False,
        },
        returns={"type": "string"},
    )
    # JSON insertion order is a, b -- the reverse of the declared params.
    write_suite(
        tmp_path, "ordering", "combine",
        [{"description": "d", "input": {"a": "A", "b": "B"}, "expected": "BA"}],
    )
    write_component(tmp_path, "python", "w")

    captured: dict[str, list] = {}

    def fake_call_function(store, instance, interface_export, function_name, args):
        captured["args"] = args
        return args[0] + args[1]

    monkeypatch.setattr(cli, "instantiate_component", lambda engine, wasm_path: ("store", "instance"))
    monkeypatch.setattr(cli, "call_function", fake_call_function)

    exit_code = cli.main(tmp_path)

    assert exit_code == 0
    assert captured["args"] == ["B", "A"]


def test_main_routes_two_packages_and_two_suites_to_their_own_worlds(tmp_path, monkeypatch, capsys):
    """Two WIT packages in separate files, each with its own interface and
    suite, are routed to the correct component/world -- not mixed
    (docs/refactoring-plan.md Phase 2)."""
    write_wit_file(
        tmp_path,
        "pkg-a.wit",
        "package common:a;\n\ninterface iface-a {\n  fn-a: func(x: string) -> string;\n}\n\n"
        "world world-a {\n  export iface-a;\n}\n",
    )
    write_wit_file(
        tmp_path,
        "pkg-b.wit",
        "package common:b;\n\ninterface iface-b {\n  fn-b: func(y: string) -> string;\n}\n\n"
        "world world-b {\n  export iface-b;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_function_schema(
        tmp_path, "iface-a", "fn-a",
        parameters={
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
            "additionalProperties": False,
        },
        returns={"type": "string"},
    )
    write_function_schema(
        tmp_path, "iface-b", "fn-b",
        parameters={
            "type": "object",
            "properties": {"y": {"type": "string"}},
            "required": ["y"],
            "additionalProperties": False,
        },
        returns={"type": "string"},
    )
    write_suite(tmp_path, "iface-a", "fn-a", [{"description": "d-a", "input": {"x": "A"}, "expected": "A"}])
    write_suite(tmp_path, "iface-b", "fn-b", [{"description": "d-b", "input": {"y": "B"}, "expected": "B"}])
    write_component(tmp_path, "python", "world-a")
    write_component(tmp_path, "python", "world-b")

    seen_exports: list[str] = []

    def fake_call_function(store, instance, interface_export, function_name, args):
        seen_exports.append(interface_export)
        return args[0]

    monkeypatch.setattr(cli, "instantiate_component", lambda engine, wasm_path: ("store", "instance"))
    monkeypatch.setattr(cli, "call_function", fake_call_function)

    exit_code = cli.main(tmp_path)
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "world=world-a  interface=iface-a  function=fn-a" in out
    assert "world=world-b  interface=iface-b  function=fn-b" in out
    assert seen_exports == ["common:a/iface-a", "common:b/iface-b"]
    assert "OK: 2/2 tests passed across 1 implementation(s)." in out
