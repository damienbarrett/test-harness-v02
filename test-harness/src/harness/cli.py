"""Reporting and CLI entry point for the unified WASM contract test harness.

Convention-based discovery (no metadata required in test files)::

    common/functions/{interface}/{function}.test.json
    {lang}/component/{world}.wasm

Namespace, package, world names, and each world's exported interfaces are
all discovered from the WIT file(s) in ``common/wit/`` (see ``harness.wit``).
The interface name is the directory name under ``common/functions/``. The
function name is the file stem (before ``.test.json``).

A suite runs only against the world(s) that export its interface -- never
the full Cartesian product of every suite and every world. A suite whose
interface is exported by no discovered world is a hard failure, not a
silent skip.

Implementations are discovered by scanning for ``*/component/`` directories.
Any directory matching that pattern is expected to contain a
``{world}.wasm`` file for every world defined in the WIT.

Exit code 0 = all pass. Non-zero = at least one failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

from wasmtime import Engine

from .conversion import normalize_return, prepare_args
from .implementations import discover_implementations
from .invocation import call_function, instantiate_component
from .models import discover_test_suites
from .wit import WitError, discover_worlds

# test-harness/src/harness/cli.py -> repo root is four levels up.
ROOT = Path(__file__).resolve().parents[3]


def main(root: Path | None = None) -> int:
    root = ROOT if root is None else root

    try:
        worlds = discover_worlds(root)
    except WitError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if not worlds:
        print("FAIL: no worlds found in common/wit/", file=sys.stderr)
        return 1

    suites = discover_test_suites(root)
    if not suites:
        print("FAIL: no test suites found under common/functions/", file=sys.stderr)
        return 1

    langs = discover_implementations(root)
    if not langs:
        print("FAIL: no implementation directories found", file=sys.stderr)
        return 1

    total = 0
    passed = 0
    failed = 0

    print(f"Discovered {len(worlds)} world(s): {', '.join(world.name for world in worlds)}")
    print(f"Discovered {len(suites)} test suite(s)")
    print(f"Discovered {len(langs)} implementation(s): {', '.join(langs)}")
    print()

    engine = Engine()

    for suite in suites:
        interface = suite.interface
        function = suite.function
        tests = suite.tests
        suite_rel = suite.path.relative_to(root)

        print(f"--- {suite_rel}")

        matching_worlds = [world for world in worlds if world.exports_interface(interface)]
        if not matching_worlds:
            available = ", ".join(sorted({world.name for world in worlds})) or "(none)"
            print(
                f"    FAIL: interface '{interface}' is not exported by any "
                f"discovered world (worlds: {available})"
            )
            print()
            failed += len(tests)
            total += len(tests)
            continue

        for world in matching_worlds:
            signature = world.function_signature(interface, function)

            print(f"    world={world.name}  interface={interface}  function={function}")

            if signature is None:
                print(
                    f"    FAIL: function '{function}' is not declared on "
                    f"interface '{interface}' in the WIT contract for world "
                    f"'{world.name}'"
                )
                print()
                failed += len(tests)
                total += len(tests)
                continue

            interface_export = world.interface_export(interface)

            print(f"    {len(tests)} test case(s) x {len(langs)} implementation(s)")
            print()

            for lang in langs:
                wasm_path = root / lang / "component" / f"{world.name}.wasm"

                if not wasm_path.exists():
                    print(f"  FAIL [{lang}] {wasm_path.relative_to(root)}: WASM file not found")
                    failed += len(tests)
                    total += len(tests)
                    continue

                # Try to instantiate
                try:
                    store, instance = instantiate_component(engine, wasm_path)
                except Exception as exc:
                    first_line = str(exc).splitlines()[0]
                    print(f"  FAIL [{lang}] could not instantiate: {first_line}")
                    failed += len(tests)
                    total += len(tests)
                    continue

                lang_passed = 0
                lang_failed = 0

                for case in tests:
                    total += 1
                    description = case.description
                    expected = case.expected

                    try:
                        args = prepare_args(case.input, signature.params)
                        raw_actual = call_function(
                            store, instance, interface_export, function, args,
                        )
                        actual = normalize_return(raw_actual)
                        if actual == expected:
                            lang_passed += 1
                            passed += 1
                        else:
                            lang_failed += 1
                            failed += 1
                            print(
                                f"  FAIL [{lang}] {description}: "
                                f"expected {expected}, got {actual}"
                            )
                    except Exception as exc:
                        lang_failed += 1
                        failed += 1
                        first_line = str(exc).splitlines()[0]
                        print(f"  FAIL [{lang}] {description}: {first_line}")

                if lang_failed == 0:
                    print(f"  OK   [{lang}] {lang_passed}/{lang_passed} passed")
                else:
                    print(
                        f"  FAIL [{lang}] {lang_failed}/{lang_passed + lang_failed} failed"
                    )

            print()

    # Summary
    print("=" * 60)
    if failed == 0:
        print(f"OK: {passed}/{total} tests passed across {len(langs)} implementation(s).")
        return 0

    print(f"{failed}/{total} test(s) failed.")
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
