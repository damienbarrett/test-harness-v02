from harness.models import WitWorld
from harness.wit import discover_worlds

from .conftest import write_wit_file, write_world


def test_no_wit_dir_returns_empty(tmp_path):
    assert discover_worlds(tmp_path) == []


def test_wit_dir_with_no_wit_files_returns_empty(tmp_path):
    (tmp_path / "common" / "wit").mkdir(parents=True)
    assert discover_worlds(tmp_path) == []


def test_single_world_discovered(tmp_path):
    write_world(tmp_path, "task-component")
    assert discover_worlds(tmp_path) == [WitWorld(name="task-component")]


def test_multiple_worlds_in_one_package(tmp_path):
    """CHARACTERIZATION: current behavior. The regex extracts every ``world``
    block from a WIT file with no regard for which interface a test suite
    actually needs, so a package with two worlds returns both. Phase 2 will
    match suites only to worlds that export their interface
    (docs/refactoring-plan.md Phase 2)."""
    write_wit_file(
        tmp_path,
        "tasks.wit",
        "package common:tasks;\n\n"
        "world world-a {\n  export task-collections;\n}\n\n"
        "world world-b {\n  export other-iface;\n}\n",
    )
    worlds = discover_worlds(tmp_path)
    assert worlds == [WitWorld(name="world-a"), WitWorld(name="world-b")]


def test_multiple_wit_packages_are_pooled_together(tmp_path):
    """CHARACTERIZATION: current behavior. Discovery globs every ``*.wit``
    file and concatenates all world names into one flat list -- there is no
    per-package grouping or namespace/package tagging yet. Phase 2
    introduces namespace/package-aware discovery and matching."""
    write_wit_file(tmp_path, "a-pkg.wit", "package common:a;\n\nworld world-a {\n  export foo;\n}\n")
    write_wit_file(tmp_path, "b-pkg.wit", "package common:b;\n\nworld world-b {\n  export bar;\n}\n")
    worlds = discover_worlds(tmp_path)
    assert worlds == [WitWorld(name="world-a"), WitWorld(name="world-b")]


def test_only_wit_extension_files_are_scanned(tmp_path):
    write_world(tmp_path, "task-component")
    (tmp_path / "common" / "wit" / "notes.txt").write_text("world should-be-ignored {\n}\n")
    worlds = discover_worlds(tmp_path)
    assert worlds == [WitWorld(name="task-component")]
