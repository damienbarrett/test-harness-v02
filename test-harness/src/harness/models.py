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
class WitWorld:
    """A WIT world discovered by name from a ``common/wit/*.wit`` file.

    Phase 1 preserves current behavior: only the world name is extracted.
    Namespace, package, and exported-interface information will be added in
    Phase 2 (see ``docs/refactoring-plan.md``).
    """

    name: str


@dataclass(frozen=True)
class TestCase:
    """A single declarative test case from a ``*.test.json`` suite."""

    description: str
    input: dict[str, Any]
    expected: Any


@dataclass(frozen=True)
class TestSuite:
    """A discovered ``*.test.json`` suite and its path-derived identity."""

    path: Path
    interface: str
    function: str
    tests: list[TestCase] = field(default_factory=list)


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
        suites.append(TestSuite(path=path, interface=interface, function=function, tests=tests))
    return suites
