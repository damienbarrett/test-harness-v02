"""Integration tests against the real, actually-built ``.wasm`` artifacts
under ``<repo-root>/{lang}/component/`` (docs/refactoring-plan.md Phase 8).

Unlike every other test in this suite, these load real files from the real
repository tree instead of a fake ``tmp_path`` project. If a component has
not been built yet, that is a hard failure with a clear "run task build
first" message -- never a silent skip. This mirrors two existing
conventions in this repo: ``harness.cli``'s own "WASM file not found"
handling for artifacts discovered at runtime, and
``tests/test_runner_behavioral_parity.py``'s ``_require_binary``, which
treats a missing required tool as a hard failure rather than an
inapplicable check.

These tests assert two things a bare `task wasm:test` pass does not, on its
own, prove for every component:

* it instantiates against a *plain* WASIp2 linker with no extra
  capabilities and no retry -- i.e. it imports nothing beyond what
  wasmtime's ``add_wasip2()`` provides. (Phase 8 removed the narrower
  "define unknown imports as traps" fallback that Phase 2 introduced, after
  minimizing the JavaScript component's componentize-js flags and then
  confirming, by inspecting all three real components with wasmtime's own
  ``ComponentType.imports()``, that none of them need it any more -- see
  ``harness.invocation.instantiate_component``'s docstring.) Since no
  fallback exists any more, a clean ``instantiate_component`` call *is* the
  proof: there is no second code path left to fall back to.
* every world's declared exports -- the interface, and every function
  declared on it in the WIT contract -- are actually resolvable on the
  instantiated component. The export surface the contract promises is the
  export surface the built artifact actually has.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from wasmtime import Engine

from harness.implementations import discover_implementations
from harness.invocation import instantiate_component
from harness.wit import discover_worlds

# test-harness/tests/test_real_component_contracts.py -> repo root is two
# levels up (same convention as tests/conftest.py and tests/test_fixtures.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _real_cases() -> list[tuple[str, object, Path]]:
    """(lang, world, wasm_path) for every real implementation x world pair
    discovered in the actual repository tree."""
    worlds = discover_worlds(_REPO_ROOT)
    langs = discover_implementations(_REPO_ROOT)
    return [
        (lang, world, _REPO_ROOT / lang / "component" / f"{world.name}.wasm")
        for lang in langs
        for world in worlds
    ]


_CASES = _real_cases()
_CASE_IDS = [f"{lang}/{world.name}" for lang, world, _ in _CASES]


def test_real_repo_tree_has_at_least_one_world_and_implementation():
    """Guards against the parametrization below silently collecting zero
    cases (e.g. if common/wit/ or the */component/ convention moved) -- an
    empty parametrize list would make the test below vacuously pass
    nothing, exactly the kind of silent gap this integration test exists to
    prevent."""
    worlds = discover_worlds(_REPO_ROOT)
    langs = discover_implementations(_REPO_ROOT)
    assert worlds, "expected at least one world under common/wit/"
    assert langs, "expected at least one */component/ implementation directory"


@pytest.mark.parametrize("lang,world,wasm_path", _CASES, ids=_CASE_IDS)
def test_real_component_instantiates_and_exports_match_the_wit_contract(
    lang, world, wasm_path
):
    if not wasm_path.exists():
        pytest.fail(
            f"{wasm_path.relative_to(_REPO_ROOT)} does not exist -- run "
            "`task build` (or `just build`) first, then re-run this test"
        )

    engine = Engine()
    # No fallback exists any more (Phase 8 removed it) -- a plain
    # WASIp2-only linker either instantiates this component or it doesn't.
    # A clean result here *is* the proof that the component imports nothing
    # beyond what `add_wasip2()` provides.
    store, instance = instantiate_component(engine, wasm_path)

    for interface in world.exports:
        iface_export = world.interface_export(interface)
        iface_idx = instance.get_export_index(store, iface_export)
        assert iface_idx is not None, (
            f"{lang}/{world.name}.wasm does not export interface "
            f"'{iface_export}' declared by world '{world.name}'"
        )

        wit_interface = world.interfaces[interface]
        for function_name in wit_interface.functions:
            func_idx = instance.get_export_index(store, function_name, iface_idx)
            assert func_idx is not None, (
                f"{lang}/{world.name}.wasm's '{iface_export}' export does not "
                f"export function '{function_name}' declared in the WIT contract"
            )
