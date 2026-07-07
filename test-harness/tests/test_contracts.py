import json
import shutil

from harness import contracts
from harness.contracts import (
    build_registry,
    validate_contracts,
)
from harness.wit import discover_worlds

from .conftest import (
    write_function_schema,
    write_suite,
    write_suite_schema,
    write_task_entity_schema,
    write_valid_contract,
    write_wit_file,
    write_world,
)


# --- validate_contracts: top-level discovery ---------------------------


def test_no_functions_dir_is_valid(tmp_path):
    assert validate_contracts(tmp_path) == []


def test_functions_dir_with_no_suites_is_valid(tmp_path):
    (tmp_path / "common" / "functions").mkdir(parents=True)
    assert validate_contracts(tmp_path) == []


def test_wit_discovery_failure_surfaces_as_a_single_error(tmp_path):
    write_wit_file(tmp_path, "broken.wit", "world w {\n  export iface;\n}\n")
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "WIT discovery failed" in errors[0]
    assert "broken.wit" in errors[0]


def test_fully_valid_contract_has_no_errors(tmp_path):
    write_valid_contract(tmp_path)
    assert validate_contracts(tmp_path) == []


def test_errors_aggregate_across_multiple_suites_in_sorted_order(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    write_task_entity_schema(tmp_path)
    write_function_schema(tmp_path, "task-collections", "count-tasks")
    # a-suite: valid. b-suite: function name does not match its filename.
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    (
        tmp_path / "common" / "functions" / "task-collections" / "bogus.test.json"
    ).write_text(
        json.dumps(
            {
                "function": "not-bogus",
                "tests": [{"description": "d", "input": {}, "expected": 1}],
            }
        )
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "bogus.test.json" in errors[0]
    assert "not-bogus" in errors[0]


def test_validate_contracts_uses_caller_provided_worlds_without_rediscovery(tmp_path):
    """When the caller passes ``worlds`` (as ``harness.cli.main`` does with
    the worlds it has already discovered), ``validate_contracts`` must use
    them as-is instead of re-running WIT discovery. Proof: the WIT tree is
    deleted after discovery, so a re-discovery would find no worlds and
    report the suite's interface as unexported."""
    write_valid_contract(tmp_path)
    worlds = discover_worlds(tmp_path)
    shutil.rmtree(tmp_path / "common" / "wit")

    assert validate_contracts(tmp_path, worlds=worlds) == []


def test_malformed_schema_file_is_a_per_file_error_not_a_traceback(tmp_path):
    """A schema file under ``common/`` that is not valid JSON must surface
    as a clear per-file validation error naming the file -- never a raw
    ``json.JSONDecodeError`` traceback out of ``build_registry``."""
    write_valid_contract(tmp_path)
    (tmp_path / "common" / "schemas" / "test-suite.schema.json").write_text("{not json")

    errors = validate_contracts(tmp_path)

    assert len(errors) == 1
    assert "common/schemas/test-suite.schema.json" in errors[0]
    assert "invalid JSON" in errors[0]


# --- suite-format schema violations --------------------------------------


def test_invalid_json_is_reported(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    d = tmp_path / "common" / "functions" / "task-collections"
    d.mkdir(parents=True)
    (d / "count-tasks.test.json").write_text("{not json")
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "invalid JSON" in errors[0]


def test_missing_required_top_level_key_is_a_schema_violation(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    d = tmp_path / "common" / "functions" / "task-collections"
    d.mkdir(parents=True)
    (d / "count-tasks.test.json").write_text(json.dumps({"function": "count-tasks"}))
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "suite schema violation" in errors[0]
    assert "'tests' is a required property" in errors[0]


def test_case_missing_expected_is_a_schema_violation_naming_its_location(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    d = tmp_path / "common" / "functions" / "task-collections"
    d.mkdir(parents=True)
    (d / "count-tasks.test.json").write_text(
        json.dumps(
            {"function": "count-tasks", "tests": [{"description": "d", "input": {}}]}
        )
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "suite schema violation at" in errors[0]


def test_empty_description_is_a_schema_violation(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    d = tmp_path / "common" / "functions" / "task-collections"
    d.mkdir(parents=True)
    (d / "count-tasks.test.json").write_text(
        json.dumps(
            {
                "function": "count-tasks",
                "tests": [{"description": "", "input": {}, "expected": 0}],
            }
        )
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "suite schema violation" in errors[0]


def test_empty_tests_array_is_a_schema_violation(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    d = tmp_path / "common" / "functions" / "task-collections"
    d.mkdir(parents=True)
    (d / "count-tasks.test.json").write_text(
        json.dumps({"function": "count-tasks", "tests": []})
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "suite schema violation" in errors[0]


def test_bad_targets_value_is_a_schema_violation(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    d = tmp_path / "common" / "functions" / "task-collections"
    d.mkdir(parents=True)
    (d / "count-tasks.test.json").write_text(
        json.dumps(
            {
                "function": "count-tasks",
                "targets": ["not-a-real-target"],
                "tests": [{"description": "d", "input": {}, "expected": 0}],
            }
        )
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "suite schema violation" in errors[0]


def test_valid_targets_value_is_accepted(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    write_task_entity_schema(tmp_path)
    write_function_schema(tmp_path, "task-collections", "count-tasks")
    d = tmp_path / "common" / "functions" / "task-collections"
    d.mkdir(parents=True, exist_ok=True)
    (d / "count-tasks.test.json").write_text(
        json.dumps(
            {
                "function": "count-tasks",
                "targets": ["native", "component"],
                "tests": [{"description": "d", "input": {"tasks": []}, "expected": 0}],
            }
        )
    )
    assert validate_contracts(tmp_path) == []


def test_empty_targets_array_is_a_schema_violation(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    d = tmp_path / "common" / "functions" / "task-collections"
    d.mkdir(parents=True)
    (d / "count-tasks.test.json").write_text(
        json.dumps(
            {
                "function": "count-tasks",
                "targets": [],
                "tests": [{"description": "d", "input": {}, "expected": 0}],
            }
        )
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "suite schema violation" in errors[0]


def test_duplicate_targets_are_a_schema_violation(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    d = tmp_path / "common" / "functions" / "task-collections"
    d.mkdir(parents=True)
    (d / "count-tasks.test.json").write_text(
        json.dumps(
            {
                "function": "count-tasks",
                "targets": ["native", "native"],
                "tests": [{"description": "d", "input": {}, "expected": 0}],
            }
        )
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "suite schema violation" in errors[0]


# --- function-name / interface / WIT-declaration checks -------------------


def test_function_name_must_match_filename_stem(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    d = tmp_path / "common" / "functions" / "task-collections"
    d.mkdir(parents=True)
    (d / "count-tasks.test.json").write_text(
        json.dumps(
            {
                "function": "wrong-name",
                "tests": [{"description": "d", "input": {}, "expected": 0}],
            }
        )
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "does not match filename stem 'count-tasks'" in errors[0]


def test_interface_not_exported_by_any_world_is_reported(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\nworld w {\n  export other-iface;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert (
        "interface 'task-collections' is not exported by any discovered world"
        in errors[0]
    )


def test_function_not_declared_on_interface_is_reported(tmp_path):
    write_world(
        tmp_path, "task-component"
    )  # declares task-collections.count-tasks only
    write_suite_schema(tmp_path)
    write_suite(
        tmp_path,
        "task-collections",
        "not-a-real-function",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert (
        "function 'not-a-real-function' is not declared on interface 'task-collections' "
        "in the WIT contract" in errors[0]
    )


def test_missing_function_schema_file_is_reported(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "missing function schema" in errors[0]
    assert "count-tasks.schema.json" in errors[0]


# --- per-case input/expected schema validation ---------------------------


def test_case_input_violating_parameters_schema_is_reported(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    write_task_entity_schema(tmp_path)
    write_function_schema(tmp_path, "task-collections", "count-tasks")
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [
            {
                "description": "bad input",
                "input": {"tasks": [{"not-a-name": 1}]},
                "expected": 0,
            }
        ],
    )
    errors = validate_contracts(tmp_path)
    assert any("case 'bad input': input invalid" in e for e in errors)


def test_case_expected_violating_returns_schema_is_reported(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    write_task_entity_schema(tmp_path)
    write_function_schema(tmp_path, "task-collections", "count-tasks")
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [
            {
                "description": "bad expected",
                "input": {"tasks": []},
                "expected": "not-a-number",
            }
        ],
    )
    errors = validate_contracts(tmp_path)
    assert any("case 'bad expected': expected invalid" in e for e in errors)


def test_duplicate_case_descriptions_are_reported(tmp_path):
    write_valid_contract(
        tmp_path,
        tests=[
            {"description": "same", "input": {"tasks": []}, "expected": 0},
            {"description": "same", "input": {"tasks": [{"name": "x"}]}, "expected": 1},
        ],
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "duplicate case description(s)" in errors[0]
    assert "same" in errors[0]


# --- fixture resolution (before schema validation) -------------------------


def write_page_contract(tmp_path, html_schema: dict | None = None) -> None:
    """A ``pages/parse-page`` contract whose single ``html`` parameter is a
    plain WIT ``string`` -- the schema can only be satisfied by a case whose
    ``$fixture`` descriptor was materialized to text BEFORE validation."""
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface pages {\n"
        "  parse-page: func(html: string) -> string;\n"
        "}\n\n"
        "world w {\n  export pages;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_function_schema(
        tmp_path,
        "pages",
        "parse-page",
        parameters={
            "type": "object",
            "properties": {"html": html_schema or {"type": "string"}},
            "required": ["html"],
            "additionalProperties": False,
        },
        returns={"type": "string"},
    )


def test_fixture_input_is_materialized_before_parameter_schema_validation(tmp_path):
    """The parameter schema requires ``html`` to be a string; the raw
    descriptor (an object) could never satisfy it. Passing proves the
    MATERIALIZED input is what gets validated (docs/refactoring-plan.md
    Phase 4)."""
    write_page_contract(tmp_path)
    fixtures = tmp_path / "common" / "fixtures" / "html-parser"
    fixtures.mkdir(parents=True)
    (fixtures / "page.html").write_text("<html></html>")
    write_suite(
        tmp_path,
        "pages",
        "parse-page",
        [
            {
                "description": "materialized",
                "input": {
                    "html": {"$fixture": "common/fixtures/html-parser/page.html"}
                },
                "expected": "ok",
            }
        ],
    )
    assert validate_contracts(tmp_path) == []


def test_materialized_fixture_input_violating_the_schema_is_reported(tmp_path):
    write_page_contract(tmp_path, html_schema={"type": "string", "maxLength": 5})
    fixtures = tmp_path / "common" / "fixtures" / "html-parser"
    fixtures.mkdir(parents=True)
    (fixtures / "page.html").write_text("<html>much longer than five characters</html>")
    write_suite(
        tmp_path,
        "pages",
        "parse-page",
        [
            {
                "description": "too long",
                "input": {
                    "html": {"$fixture": "common/fixtures/html-parser/page.html"}
                },
                "expected": "ok",
            }
        ],
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "case 'too long': input invalid" in errors[0]


def test_fixture_resolution_failure_is_a_contract_validation_error(tmp_path):
    write_page_contract(tmp_path)
    fixtures = tmp_path / "common" / "fixtures" / "html-parser"
    fixtures.mkdir(parents=True)
    (fixtures / "page.html").write_text("<html></html>")
    write_suite(
        tmp_path,
        "pages",
        "parse-page",
        [
            {
                "description": "bad compression",
                "input": {
                    "html": {
                        "$fixture": "common/fixtures/html-parser/page.html",
                        "compression": "zstd",
                    }
                },
                "expected": "ok",
            }
        ],
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "case 'bad compression'" in errors[0]
    assert "unsupported compression 'zstd'" in errors[0]


def test_unknown_descriptor_key_is_a_contract_validation_error(tmp_path):
    write_page_contract(tmp_path)
    fixtures = tmp_path / "common" / "fixtures" / "html-parser"
    fixtures.mkdir(parents=True)
    (fixtures / "page.html").write_text("<html></html>")
    write_suite(
        tmp_path,
        "pages",
        "parse-page",
        [
            {
                "description": "typo",
                "input": {
                    "html": {
                        "$fixture": "common/fixtures/html-parser/page.html",
                        "encodings": "utf-8",
                    }
                },
                "expected": "ok",
            }
        ],
    )
    errors = validate_contracts(tmp_path)
    assert len(errors) == 1
    assert "case 'typo'" in errors[0]
    assert "unknown fixture descriptor key(s) ['encodings']" in errors[0]


def test_fixture_reference_that_does_not_exist_is_reported(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    write_task_entity_schema(tmp_path)
    write_function_schema(
        tmp_path,
        "task-collections",
        "count-tasks",
        parameters={
            "type": "object"
        },  # permissive: input carries a $fixture descriptor, not a task list
    )
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [
            {
                "description": "missing fixture",
                "input": {
                    "tasks": {"$fixture": "common/fixtures/html-parser/missing.html"}
                },
                "expected": 0,
            }
        ],
    )
    errors = validate_contracts(tmp_path)
    assert any(
        "fixture 'common/fixtures/html-parser/missing.html' does not exist" in e
        for e in errors
    )


def test_fixture_reference_escaping_common_fixtures_is_reported(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    write_task_entity_schema(tmp_path)
    write_function_schema(
        tmp_path, "task-collections", "count-tasks", parameters={"type": "object"}
    )
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [
            {
                "description": "escaping fixture",
                "input": {"tasks": {"$fixture": "../outside/evil.html"}},
                "expected": 0,
            }
        ],
    )
    errors = validate_contracts(tmp_path)
    assert any("must resolve under common/fixtures/" in e for e in errors)


def test_fixture_nested_inside_a_list_that_exists_is_accepted(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    write_task_entity_schema(tmp_path)
    write_function_schema(
        tmp_path, "task-collections", "count-tasks", parameters={"type": "object"}
    )
    fixtures_dir = tmp_path / "common" / "fixtures" / "html-parser"
    fixtures_dir.mkdir(parents=True)
    (fixtures_dir / "ok.html").write_text("<html></html>")
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [
            {
                "description": "fixture in a list",
                "input": {
                    "tasks": [{"$fixture": "common/fixtures/html-parser/ok.html"}]
                },
                "expected": 0,
            }
        ],
    )
    assert validate_contracts(tmp_path) == []


# --- WIT numeric conformance -----------------------------------------------


def test_missing_numeric_bounds_are_reported(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    write_task_entity_schema(tmp_path)
    write_function_schema(
        tmp_path, "task-collections", "count-tasks", returns={"type": "integer"}
    )
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    errors = validate_contracts(tmp_path)
    assert any("must declare minimum >= 0" in e for e in errors)
    assert any("must declare maximum <= 4294967295" in e for e in errors)


def test_tight_numeric_bounds_are_accepted(tmp_path):
    write_valid_contract(tmp_path)
    assert validate_contracts(tmp_path) == []


def test_looser_than_wit_maximum_is_reported(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    write_task_entity_schema(tmp_path)
    write_function_schema(
        tmp_path,
        "task-collections",
        "count-tasks",
        returns={"type": "integer", "minimum": 0, "maximum": 5000000000},
    )
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    errors = validate_contracts(tmp_path)
    assert any("must declare maximum <= 4294967295" in e for e in errors)


def test_signed_integer_bounds_are_checked(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  get-delta: func() -> s16;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_function_schema(
        tmp_path,
        "things",
        "get-delta",
        parameters={"type": "object"},
        returns={"type": "integer"},
    )
    write_suite(
        tmp_path,
        "things",
        "get-delta",
        [{"description": "d", "input": {}, "expected": 1}],
    )
    errors = validate_contracts(tmp_path)
    assert any("must declare minimum >= -32768" in e for e in errors)
    assert any("must declare maximum <= 32767" in e for e in errors)


def test_signed_integer_within_wit_tight_bounds_is_accepted(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  get-delta: func() -> s16;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_function_schema(
        tmp_path,
        "things",
        "get-delta",
        parameters={"type": "object"},
        returns={"type": "integer", "minimum": -32768, "maximum": 32767},
    )
    write_suite(
        tmp_path,
        "things",
        "get-delta",
        [{"description": "d", "input": {}, "expected": 1}],
    )
    assert validate_contracts(tmp_path) == []


def test_float_return_type_must_declare_number(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  get-ratio: func() -> float64;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_function_schema(
        tmp_path,
        "things",
        "get-ratio",
        parameters={"type": "object"},
        returns={"type": "integer"},
    )
    write_suite(
        tmp_path,
        "things",
        "get-ratio",
        [{"description": "d", "input": {}, "expected": 1}],
    )
    errors = validate_contracts(tmp_path)
    assert any("must declare type 'number'" in e for e in errors)


def test_float_return_type_declaring_number_is_accepted(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  get-ratio: func() -> float64;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_function_schema(
        tmp_path,
        "things",
        "get-ratio",
        parameters={"type": "object"},
        returns={"type": "number"},
    )
    write_suite(
        tmp_path,
        "things",
        "get-ratio",
        [{"description": "d", "input": {}, "expected": 1.5}],
    )
    assert validate_contracts(tmp_path) == []


def test_non_numeric_return_type_skips_numeric_conformance(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  greet: func() -> string;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_function_schema(
        tmp_path,
        "things",
        "greet",
        parameters={"type": "object"},
        returns={"type": "string"},
    )
    write_suite(
        tmp_path,
        "things",
        "greet",
        [{"description": "d", "input": {}, "expected": "hi"}],
    )
    assert validate_contracts(tmp_path) == []


def test_no_return_type_skips_numeric_conformance(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  log: func(message: string);\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_function_schema(
        tmp_path,
        "things",
        "log",
        parameters={"type": "object"},
        returns={},
    )
    write_suite(
        tmp_path,
        "things",
        "log",
        [{"description": "d", "input": {"message": "hi"}, "expected": None}],
    )
    assert validate_contracts(tmp_path) == []


# --- WIT-vs-schema record conformance --------------------------------------


def test_record_field_mismatch_is_reported(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    # Entity schema drifted: declares `label` instead of the WIT record's `name`.
    write_task_entity_schema(
        tmp_path, properties={"label": {"type": "string"}}, required=["label"]
    )
    write_function_schema(tmp_path, "task-collections", "count-tasks")
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    errors = validate_contracts(tmp_path)
    assert any(
        "entity schema 'common/entities/task-schema.json' properties" in e
        and "task" in e
        for e in errors
    )


def test_record_without_a_matching_entity_schema_is_not_an_error(tmp_path):
    write_world(tmp_path, "task-component")
    write_suite_schema(tmp_path)
    # No common/entities/task-schema.json at all -- nothing to mirror-check.
    write_function_schema(tmp_path, "task-collections", "count-tasks")
    write_suite(
        tmp_path,
        "task-collections",
        "count-tasks",
        [{"description": "d", "input": {"tasks": []}, "expected": 0}],
    )
    assert validate_contracts(tmp_path) == []


def test_transitively_reachable_nested_record_is_checked(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  record detail {\n    owner: string,\n  }\n\n"
        "  record item {\n    name: string,\n    detail: detail,\n  }\n\n"
        "  make: func(items: list<item>) -> u32;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    write_suite_schema(tmp_path)
    d = tmp_path / "common" / "entities"
    d.mkdir(parents=True)
    (d / "detail-schema.json").write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {"wrong": {"type": "string"}},
            }
        )
    )
    write_function_schema(
        tmp_path,
        "things",
        "make",
        parameters={"type": "object"},
        returns={"type": "integer", "minimum": 0, "maximum": 4294967295},
    )
    write_suite(
        tmp_path,
        "things",
        "make",
        [{"description": "d", "input": {"items": []}, "expected": 0}],
    )
    errors = validate_contracts(tmp_path)
    assert any("detail-schema.json" in e and "detail" in e for e in errors)


def test_param_type_naming_a_non_record_type_is_skipped(tmp_path):
    """`status` is a bareword type name (not a WIT keyword), but it isn't
    declared as a `record` in this interface (e.g. it could be a `variant`
    or a type from another package) -- reachability must skip it rather
    than error."""
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  set-status: func(s: status) -> bool;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_function_schema(
        tmp_path,
        "things",
        "set-status",
        parameters={"type": "object"},
        returns={"type": "boolean"},
    )
    write_suite(
        tmp_path,
        "things",
        "set-status",
        [{"description": "d", "input": {"s": "ok"}, "expected": True}],
    )
    assert validate_contracts(tmp_path) == []


def test_param_type_not_naming_any_record_has_no_reachable_records(tmp_path):
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "interface things {\n"
        "  greet: func(name: string) -> string;\n"
        "}\n\n"
        "world w {\n  export things;\n}\n",
    )
    write_suite_schema(tmp_path)
    write_function_schema(
        tmp_path,
        "things",
        "greet",
        parameters={"type": "object"},
        returns={"type": "string"},
    )
    write_suite(
        tmp_path,
        "things",
        "greet",
        [{"description": "d", "input": {"name": "x"}, "expected": "hi"}],
    )
    assert validate_contracts(tmp_path) == []


# --- build_registry ---------------------------------------------------------


def test_build_registry_registers_by_both_id_and_path_when_they_differ(tmp_path):
    d = tmp_path / "common" / "entities"
    d.mkdir(parents=True)
    (d / "widget-schema.json").write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "https://example.test/widget",
                "type": "object",
            }
        )
    )
    registry, schemas_by_path = build_registry(tmp_path)
    assert (
        schemas_by_path["common/entities/widget-schema.json"]["$id"]
        == "https://example.test/widget"
    )
    assert registry.contents("common/entities/widget-schema.json")["type"] == "object"
    assert registry.contents("https://example.test/widget")["type"] == "object"


def test_build_registry_ignores_schema_without_id_beyond_its_path(tmp_path):
    d = tmp_path / "common" / "entities"
    d.mkdir(parents=True)
    (d / "plain-schema.json").write_text(json.dumps({"type": "string"}))
    registry, schemas_by_path = build_registry(tmp_path)
    assert schemas_by_path["common/entities/plain-schema.json"] == {"type": "string"}
    assert registry.contents("common/entities/plain-schema.json") == {"type": "string"}


# --- CLI entry point (harness.contracts.main) -------------------------------


def test_main_returns_zero_and_prints_ok_for_a_valid_contract(tmp_path, capsys):
    write_valid_contract(tmp_path)
    exit_code = contracts.main(tmp_path)
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "OK: all contracts valid." in out


def test_main_returns_one_and_prints_each_error_to_stderr(tmp_path, capsys):
    write_wit_file(tmp_path, "broken.wit", "world w {\n  export iface;\n}\n")
    exit_code = contracts.main(tmp_path)
    err = capsys.readouterr().err
    assert exit_code == 1
    assert "FAIL: contract validation failed:" in err
    assert "WIT discovery failed" in err


def test_main_defaults_to_the_real_repository_root_and_it_is_valid(capsys):
    """No explicit root -- exercises ``main``'s ``root is None`` default,
    against the real repository this test suite lives in. If this fails,
    the real common/ contracts are broken, not just the test fixture."""
    exit_code = contracts.main()
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "OK" in out
