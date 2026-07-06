"""Data models for discovered WIT worlds, test suites, and test cases.

These dataclasses replace the ad-hoc dicts (``_path``/``_interface``/
``_function`` keys bolted onto the raw JSON payload) used by the original
monolithic ``run-wasm-tests.py`` script.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WitFunction:
    """A function signature declared inside a WIT interface.

    ``params`` holds the function's declared parameter names in declared
    order -- this is the authority for positional argument order when
    calling into a component; JSON object insertion order in a test suite
    is never used for this purpose.

    ``param_types`` holds each parameter's declared type text, aligned by
    index with ``params`` (e.g. for ``count-tasks: func(tasks: list<task>)``,
    ``param_types == ("list<task>",)``). ``returns`` is the function's
    declared return type text verbatim (e.g. ``"u32"``), or ``None`` for a
    function with no return type. Both are used by ``harness.contracts`` to
    check WIT/JSON-Schema conformance (numeric bounds and record shape).
    """

    name: str
    params: tuple[str, ...] = ()
    param_types: tuple[str, ...] = ()
    returns: str | None = None


@dataclass(frozen=True)
class WitRecordField:
    """A single field inside a WIT ``record { ... }`` declaration."""

    name: str
    type: str


@dataclass(frozen=True)
class WitRecord:
    """A ``record { ... }`` type declared inside a WIT interface."""

    name: str
    fields: tuple[WitRecordField, ...] = ()

    @property
    def field_names(self) -> tuple[str, ...]:
        """The record's declared field names, in declared order."""
        return tuple(f.name for f in self.fields)


@dataclass(frozen=True)
class WitInterface:
    """An ``interface { ... }`` block declared inside a WIT package."""

    name: str
    functions: dict[str, WitFunction] = field(default_factory=dict)
    records: dict[str, WitRecord] = field(default_factory=dict)


@dataclass(frozen=True)
class WitWorld:
    """A WIT world discovered from a ``common/wit/*.wit`` file.

    ``exports`` is the tuple of interface names the world's ``export``
    statements reference (in file order). ``interfaces`` is the full set of
    interfaces declared in the world's own package, keyed by interface
    name, giving the world access to its package's function signatures
    (parameter names, in declared order) for any of those interfaces.
    """

    namespace: str
    package: str
    name: str
    exports: tuple[str, ...] = ()
    interfaces: dict[str, WitInterface] = field(default_factory=dict)

    def exports_interface(self, interface: str) -> bool:
        """Whether this world's ``export`` statements include ``interface``."""
        return interface in self.exports

    def interface_export(self, interface: str) -> str:
        """The export string wasmtime expects for invocation.

        Built from the world's own discovered namespace/package rather
        than any hardcoded constant, e.g. ``common:tasks/task-collections``.
        """
        return f"{self.namespace}:{self.package}/{interface}"

    def function_signature(self, interface: str, function: str) -> WitFunction | None:
        """Look up a function's declared signature on one of this world's
        package interfaces, or ``None`` if the interface or function is not
        declared in the WIT contract."""
        iface = self.interfaces.get(interface)
        if iface is None:
            return None
        return iface.functions.get(function)


@dataclass(frozen=True)
class TestCase:
    """A single declarative test case from a ``*.test.json`` suite."""

    description: str
    input: dict[str, Any]
    expected: Any


@dataclass(frozen=True)
class TestSuite:
    """A discovered ``*.test.json`` suite and its path-derived identity.

    ``targets`` mirrors the suite's optional ``targets`` array (execution
    metadata, e.g. ``("native",)``). ``None`` means the suite declares no
    restriction and runs against every target that can execute it; a tuple
    excluding ``"component"`` tells the WASM harness to announce an
    explicit skip for the suite (see ``harness.cli``). Unknown target
    values never get this far -- the suite-format schema's enum rejects
    them during contract validation.
    """

    path: Path
    interface: str
    function: str
    tests: list[TestCase] = field(default_factory=list)
    targets: tuple[str, ...] | None = None


def discover_test_suites(root: Path) -> list[TestSuite]:
    """Find ``*.test.json`` files; derive interface and function from path.

    Convention: parent directory name is the interface, file stem (before
    ``.test.json``) is the function name.
    """
    suites: list[TestSuite] = []
    functions_dir = root / "common" / "functions"
    if not functions_dir.is_dir():
        return suites
    for path in sorted(functions_dir.rglob("*.test.json")):
        with open(path) as fh:
            data = json.load(fh)
        interface = path.parent.name
        function = path.name.removesuffix(".test.json")
        tests = [
            TestCase(
                description=case["description"],
                input=case["input"],
                expected=case["expected"],
            )
            for case in data["tests"]
        ]
        raw_targets = data.get("targets")
        targets = tuple(raw_targets) if raw_targets is not None else None
        suites.append(
            TestSuite(path=path, interface=interface, function=function, tests=tests, targets=targets)
        )
    return suites
