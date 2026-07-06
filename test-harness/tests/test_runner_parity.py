from harness.runner_parity import (
    canonical_name,
    compare,
    main,
    normalize_command,
    parse_justfile,
    parse_taskfile,
)


def test_canonical_name_maps_colon_and_dash_forms_together():
    assert canonical_name("container:build") == "container-build"
    assert canonical_name("container-build") == "container-build"


def test_normalize_command_collapses_whitespace_and_continuations():
    assert normalize_command("echo  hi \\\n  there") == "echo hi there"


def test_normalize_command_upper_cases_template_vars_and_strips_comments():
    assert normalize_command('echo {{.Foo}} # a comment') == "echo {{FOO}}"


def test_parse_taskfile_direct_skips_default_and_reads_deps_and_cmds(tmp_path):
    taskfile = tmp_path / "Taskfile.yml"
    taskfile.write_text(
        """
version: "3"
tasks:
  default:
    cmds: [task --list]
  build:
    cmds:
      - echo build
  test:
    deps: [build]
    cmds:
      - {task: build}
      - echo test
"""
    )
    tf = parse_taskfile(taskfile)
    assert "default" not in tf
    assert tf["build"] == {"deps": [], "cmds": ["echo build"]}
    assert tf["test"] == {"deps": ["build", "build"], "cmds": ["echo test"]}


def test_parse_taskfile_deps_entry_as_dict_form(tmp_path):
    taskfile = tmp_path / "Taskfile.yml"
    taskfile.write_text(
        """
version: "3"
tasks:
  build:
    cmds:
      - echo build
  test:
    deps:
      - {task: build}
    cmds:
      - echo test
"""
    )
    tf = parse_taskfile(taskfile)
    assert tf["test"]["deps"] == ["build"]


def test_parse_taskfile_includes_one_level_of_children_dict_form(tmp_path):
    child_dir = tmp_path / "child"
    child_dir.mkdir()
    (child_dir / "Taskfile.yml").write_text(
        'version: "3"\ntasks:\n  build:\n    cmds:\n      - echo build\n'
    )
    parent = tmp_path / "Taskfile.yml"
    parent.write_text(
        'version: "3"\n'
        "includes:\n"
        "  child:\n"
        "    taskfile: ./child/Taskfile.yml\n"
        "tasks:\n"
        "  test:\n"
        "    cmds:\n"
        "      - echo hi\n"
    )
    tf = parse_taskfile(parent)
    assert tf["child-build"] == {"deps": [], "cmds": []}


def test_parse_taskfile_includes_string_form(tmp_path):
    child_dir = tmp_path / "child"
    child_dir.mkdir()
    (child_dir / "Taskfile.yml").write_text(
        'version: "3"\ntasks:\n  build:\n    cmds:\n      - echo build\n'
    )
    parent = tmp_path / "Taskfile.yml"
    parent.write_text(
        'version: "3"\nincludes:\n  child: ./child/Taskfile.yml\ntasks: {}\n'
    )
    tf = parse_taskfile(parent)
    assert "child-build" in tf


def test_parse_taskfile_includes_skips_entry_missing_taskfile_key(tmp_path):
    parent = tmp_path / "Taskfile.yml"
    parent.write_text('version: "3"\nincludes:\n  child: {}\ntasks: {}\n')
    tf = parse_taskfile(parent)
    assert tf == {}


def test_parse_taskfile_includes_skips_missing_child_file(tmp_path):
    parent = tmp_path / "Taskfile.yml"
    parent.write_text(
        'version: "3"\nincludes:\n  child:\n    taskfile: ./missing/Taskfile.yml\ntasks: {}\n'
    )
    tf = parse_taskfile(parent)
    assert tf == {}


def test_parse_justfile_covers_directives_defaults_and_deps(tmp_path):
    justfile = tmp_path / "justfile"
    justfile.write_text(
        "export UV_CACHE_DIR := env_var_or_default('UV_CACHE_DIR', '.cache/uv')\n"
        "\n"
        "# a comment line\n"
        'import "shared.just"\n'
        "\n"
        "# List available commands\n"
        "default:\n"
        "    @just --list\n"
        "\n"
        "build:\n"
        "    echo build\n"
        "\n"
        "test: build\n"
        "    echo test\n"
    )
    jf = parse_justfile(justfile)
    assert "default" not in jf
    assert jf["build"] == {"deps": [], "cmds": ["echo build"]}
    assert jf["test"] == {"deps": ["build"], "cmds": ["echo test"]}


def test_parse_justfile_ignores_malformed_recipe_head(tmp_path):
    justfile = tmp_path / "justfile"
    justfile.write_text(": stray colon line\nbuild:\n    echo build\n")
    jf = parse_justfile(justfile)
    assert jf == {"build": {"deps": [], "cmds": ["echo build"]}}


def test_parse_justfile_ignores_lines_without_a_colon(tmp_path):
    justfile = tmp_path / "justfile"
    justfile.write_text("just a stray word with no colon\nbuild:\n    echo build\n")
    jf = parse_justfile(justfile)
    assert jf == {"build": {"deps": [], "cmds": ["echo build"]}}


def test_parse_justfile_ignores_invalid_recipe_names(tmp_path):
    justfile = tmp_path / "justfile"
    justfile.write_text("1bad: dep\n    echo nope\nbuild:\n    echo build\n")
    jf = parse_justfile(justfile)
    assert "1bad" not in jf
    assert jf["build"] == {"deps": [], "cmds": ["echo build"]}


def test_compare_reports_only_in_taskfile_and_only_in_justfile():
    tf = {"a": {"deps": [], "cmds": ["x"]}}
    jf = {"b": {"deps": [], "cmds": ["y"]}}
    failures, warnings = compare(tf, jf)
    assert any("only in Taskfile.yml" in f for f in failures)
    assert any("only in justfile" in f for f in failures)
    assert warnings == []


def test_compare_reports_deps_differ_as_failure():
    tf = {"a": {"deps": ["x"], "cmds": ["echo a"]}}
    jf = {"a": {"deps": ["y"], "cmds": ["echo a"]}}
    failures, warnings = compare(tf, jf)
    assert any("deps differ" in f for f in failures)


def test_compare_reports_cmds_differ_as_warning_only():
    tf = {"a": {"deps": [], "cmds": ["echo a"]}}
    jf = {"a": {"deps": [], "cmds": ["echo b"]}}
    failures, warnings = compare(tf, jf)
    assert failures == []
    assert any("command bodies differ" in w for w in warnings)


def _write_pair(tmp_path, taskfile_text: str, justfile_text: str) -> None:
    (tmp_path / "Taskfile.yml").write_text(taskfile_text)
    (tmp_path / "justfile").write_text(justfile_text)


def test_main_reports_ok_for_matching_pair(tmp_path, capsys):
    _write_pair(
        tmp_path,
        'version: "3"\ntasks:\n  test:\n    cmds:\n      - echo hi\n',
        "test:\n    echo hi\n",
    )
    assert main(tmp_path) == 0
    assert "OK: 1 Taskfile.yml/justfile pair(s) in parity." in capsys.readouterr().out


def test_main_reports_ok_with_warnings_when_only_cmds_differ(tmp_path, capsys):
    _write_pair(
        tmp_path,
        'version: "3"\ntasks:\n  test:\n    cmds:\n      - echo hi\n',
        "test:\n    echo different\n",
    )
    exit_code = main(tmp_path)
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "warn ./test: command bodies differ" in out
    assert "command-body warning" in out


def test_main_fails_on_missing_recipe(tmp_path, capsys):
    _write_pair(
        tmp_path,
        'version: "3"\ntasks:\n  test:\n    cmds:\n      - echo hi\n  extra:\n    cmds:\n      - echo extra\n',
        "test:\n    echo hi\n",
    )
    exit_code = main(tmp_path)
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "only in Taskfile.yml" in captured.out
    assert "location(s) with drift" in captured.err


def test_main_fails_on_dependency_mismatch(tmp_path, capsys):
    _write_pair(
        tmp_path,
        'version: "3"\ntasks:\n  build:\n    cmds:\n      - echo build\n  test:\n    deps: [build]\n    cmds:\n      - echo test\n',
        "build:\n    echo build\n\ntest:\n    echo test\n",
    )
    exit_code = main(tmp_path)
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "deps differ" in out


def test_main_ignores_directories_with_only_one_of_the_pair(tmp_path):
    (tmp_path / "Taskfile.yml").write_text("version: '3'\ntasks: {}\n")
    assert main(tmp_path) == 0


def test_main_skips_paths_under_skip_parts(tmp_path):
    nested = tmp_path / "node_modules" / "pkg"
    nested.mkdir(parents=True)
    (nested / "Taskfile.yml").write_text("version: '3'\ntasks: {}\n")
    (nested / "justfile").write_text("")
    assert main(tmp_path) == 0


def test_main_reports_parse_error(tmp_path, capsys):
    (tmp_path / "Taskfile.yml").write_text(": not valid: yaml: [")
    (tmp_path / "justfile").write_text("test:\n    echo hi\n")
    exit_code = main(tmp_path)
    err = capsys.readouterr().err
    assert exit_code == 1
    assert "parse error" in err
