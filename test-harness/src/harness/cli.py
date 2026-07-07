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

Immediately after WIT world discovery -- before suite models are loaded,
before implementations are discovered, and before any component is
instantiated -- every suite is run through
``harness.contracts.validate_contracts`` (handing it the already-discovered
worlds, so WIT discovery happens once per run). A malformed suite, an
undeclared function, a ``$fixture`` descriptor that cannot be resolved, or
a WIT/JSON-Schema numeric or record mismatch fails the whole run
immediately with a clear validation error, rather than surfacing as a raw
traceback from suite-model loading or being masked by a
missing-implementations failure (docs/refactoring-plan.md Phase 3).

Each case's ``$fixture`` descriptors are materialized (via
``harness.fixtures``, the same resolver contract validation used) before
call arguments are built, so components receive decoded file contents --
never descriptors, and never filesystem paths. A suite whose ``targets``
metadata excludes ``"component"`` is announced with an explicit
``SKIP (declared native-only): ...`` line and counts as neither pass nor
fail (docs/refactoring-plan.md Phase 4).

Exit code 0 = all pass. Non-zero = at least one failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

from wasmtime import Engine

from .contracts import validate_contracts
from .conversion import normalize_return, prepare_args
from .fixtures import resolve_fixtures
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

    # Contracts are validated FIRST -- before suite models are loaded and
    # before implementations are discovered -- so a malformed suite fails
    # here as a clear validation error (never a raw json/KeyError traceback
    # out of discover_test_suites) and a missing implementation directory
    # can never mask a contract error.
    contract_errors = validate_contracts(root, worlds=worlds)
    if contract_errors:
        print(
            "FAIL: contract validation failed; no component was invoked:",
            file=sys.stderr,
        )
        for error in contract_errors:
            print(f"  {error}", file=sys.stderr)
        return 1

    # validate_contracts has already parsed every suite's JSON once; this
    # re-parse into models is accepted as cheap -- a shared suite-context
    # object was considered and rejected to keep contracts.py decoupled
    # from models.py.
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

    print(
        f"Discovered {len(worlds)} world(s): {', '.join(world.name for world in worlds)}"
    )
    print(f"Discovered {len(suites)} test suite(s)")
    print(f"Discovered {len(langs)} implementation(s): {', '.join(langs)}")
    print()

    engine = Engine()

    for suite in suites:
        interface = suite.interface
        function = suite.function
        tests = suite.tests
        suite_rel = suite.path.relative_to(root)

        # A suite whose declared targets exclude "component" is never run
        # against components. This is an explicit, announced declaration --
        # never a silent skip -- and it counts as neither pass nor fail.
        # (An unknown target value is a contract-validation ERROR, caught
        # by the suite-format schema's enum before this loop starts.)
        if suite.targets is not None and "component" not in suite.targets:
            print(f"SKIP (declared native-only): {suite_rel}")
            continue

        print(f"--- {suite_rel}")

        # Fixtures are materialized exactly once per case, here, before any
        # component work. Contract validation has already fully resolved
        # every descriptor in these same inputs, so a failure at this point
        # is practically impossible (the tree changed mid-run) and is
        # deliberately allowed to propagate with its own clear message.
        resolved_inputs = [resolve_fixtures(case.input, root) for case in tests]

        # validate_contracts has already confirmed, for every discovered
        # suite, that its interface is exported by at least one world and
        # that the function is declared there -- so neither is re-checked
        # (and re-reported) here; a violation would already have failed the
        # run before this loop ever started.
        matching_worlds = [
            world for world in worlds if world.exports_interface(interface)
        ]
        assert matching_worlds, (
            f"contract validation should have caught interface '{interface}' "
            "not being exported by any world"
        )

        for world in matching_worlds:
            signature = world.function_signature(interface, function)
            assert signature is not None, (
                f"contract validation should have caught function '{function}' "
                f"not being declared on interface '{interface}'"
            )

            print(f"    world={world.name}  interface={interface}  function={function}")

            interface_export = world.interface_export(interface)

            print(f"    {len(tests)} test case(s) x {len(langs)} implementation(s)")
            print()

            for lang in langs:
                wasm_path = root / lang / "component" / f"{world.name}.wasm"

                if not wasm_path.exists():
                    print(
                        f"  FAIL [{lang}] {wasm_path.relative_to(root)}: WASM file not found"
                    )
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

                for case, resolved_input in zip(tests, resolved_inputs):
                    total += 1
                    description = case.description
                    expected = case.expected

                    try:
                        args = prepare_args(resolved_input, signature.params)
                        raw_actual = call_function(
                            store,
                            instance,
                            interface_export,
                            function,
                            args,
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
        print(
            f"OK: {passed}/{total} tests passed across {len(langs)} implementation(s)."
        )
        return 0

    print(f"{failed}/{total} test(s) failed.")
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
