from dataclasses import make_dataclass

from harness import cli

from .conftest import write_component, write_suite, write_wit_file, write_world


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


def test_main_fails_per_case_when_component_artifact_missing(tmp_path, capsys):
    write_world(tmp_path, "task-component")
    write_suite(
        tmp_path, "task-collections", "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    (tmp_path / "python" / "component").mkdir(parents=True)

    exit_code = cli.main(tmp_path)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "WASM file not found" in out
    assert "1/1 test(s) failed." in out


def test_main_reports_instantiation_failure(tmp_path, monkeypatch, capsys):
    write_world(tmp_path, "task-component")
    write_suite(
        tmp_path, "task-collections", "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    write_component(tmp_path, "python", "task-component")

    def boom(engine, wasm_path):
        raise RuntimeError("bad wasm module")

    monkeypatch.setattr(cli, "instantiate_component", boom)

    exit_code = cli.main(tmp_path)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "could not instantiate: bad wasm module" in out


def test_main_reports_invocation_failure(tmp_path, monkeypatch, capsys):
    write_world(tmp_path, "task-component")
    write_suite(
        tmp_path, "task-collections", "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
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
    write_world(tmp_path, "task-component")
    write_suite(
        tmp_path, "task-collections", "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    write_component(tmp_path, "python", "task-component")

    monkeypatch.setattr(cli, "instantiate_component", lambda engine, wasm_path: ("store", "instance"))
    monkeypatch.setattr(cli, "call_function", lambda *a, **k: 0)

    exit_code = cli.main(tmp_path)
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "OK   [python] 1/1 passed" in out
    assert "OK: 1/1 tests passed across 1 implementation(s)." in out


def test_main_reports_mismatch_between_actual_and_expected(tmp_path, monkeypatch, capsys):
    write_world(tmp_path, "task-component")
    write_suite(
        tmp_path, "task-collections", "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    write_component(tmp_path, "python", "task-component")

    monkeypatch.setattr(cli, "instantiate_component", lambda engine, wasm_path: ("store", "instance"))
    monkeypatch.setattr(cli, "call_function", lambda *a, **k: 99)

    exit_code = cli.main(tmp_path)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "expected 0, got 99" in out
    assert "FAIL [python] 1/1 failed" in out


def test_main_structured_return_value_compared_with_bare_equality(tmp_path, monkeypatch, capsys):
    """CHARACTERIZATION: a component return value is compared to the plain
    JSON ``expected`` value with a bare ``==``. A structurally-equivalent but
    differently-typed return (e.g. a WIT record surfaced as a dataclass)
    fails this comparison even though a human would call the two values
    equal. Phase 2 normalizes return values recursively before comparison
    (docs/refactoring-plan.md Phase 2)."""
    write_world(tmp_path, "task-component")
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

    assert exit_code == 1
    assert "expected {'name': 'Task 1'}, got Record(name='Task 1')" in out


def test_main_runs_every_suite_against_every_world_cartesian_product(tmp_path, monkeypatch, capsys):
    """CHARACTERIZATION: every discovered suite runs against every
    discovered world today, even a world that does not export the suite's
    interface. Phase 2 restricts execution to worlds that export the
    suite's interface (docs/refactoring-plan.md Phase 2)."""
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "world world-a {\n  export task-collections;\n}\n\n"
        "world world-b {\n  export other-iface;\n}\n",
    )
    write_suite(
        tmp_path, "task-collections", "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    write_component(tmp_path, "python", "world-a")
    write_component(tmp_path, "python", "world-b")

    monkeypatch.setattr(cli, "instantiate_component", lambda engine, wasm_path: ("store", "instance"))
    monkeypatch.setattr(cli, "call_function", lambda *a, **k: 0)

    exit_code = cli.main(tmp_path)
    out = capsys.readouterr().out

    assert exit_code == 0
    assert out.count("world=world-a") == 1
    assert out.count("world=world-b") == 1
    assert "OK: 2/2 tests passed across 1 implementation(s)." in out
