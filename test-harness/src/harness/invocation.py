"""WASM component instantiation and function invocation.

The wasmtime interaction is kept thin and injectable: production callers use
the default factories (bound to the real wasmtime classes), while tests
substitute simple doubles to exercise instantiation- and invocation-failure
paths without loading real ``.wasm`` files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol

from wasmtime import Engine, Store, WasiConfig
from wasmtime import component as wt_component

ComponentFromFile = Callable[[Engine, str], Any]
LinkerFactory = Callable[[Engine], Any]
StoreFactory = Callable[[Engine], Any]
WasiConfigFactory = Callable[[], Any]


class SupportsExports(Protocol):
    """The subset of a wasmtime component ``instance`` the harness needs."""

    def get_export_index(self, store: Any, name: str, parent: Any = None) -> Any: ...

    def get_func(self, store: Any, index: Any) -> Any: ...


def instantiate_component(
    engine: Engine,
    wasm_path: Path,
    *,
    component_from_file: ComponentFromFile = wt_component.Component.from_file,
    linker_factory: LinkerFactory = wt_component.Linker,
    store_factory: StoreFactory = Store,
    wasi_config_factory: WasiConfigFactory = WasiConfig,
) -> tuple[Any, Any]:
    """Instantiate a WASM component with WASI support.

    Returns ``(store, instance)`` on success or raises unchanged on failure.

    A single plain WASIp2 linker (``linker.add_wasip2()``) is used -- no
    retry, no fallback. Earlier (Phase 2 of docs/refactoring-plan.md) this
    function retried a missing-import instantiation failure with unknown
    imports defined as traps, to tolerate a componentize-js output that
    imported ``wasi:http`` (which wasmtime-py's ``add_wasip2()`` does not
    provide). Phase 8 removed that fallback after minimizing the
    JavaScript component's componentize-js flags (``-d all`` with no
    ``--enable`` overrides in javascript/component/lifecycle.sh) and then
    confirming, by inspecting all three real built components with
    ``wasmtime.component.Component(...).type.imports(engine)``, that none
    of them import anything beyond what ``add_wasip2()`` supplies. A
    component that still needed an import the harness does not provide
    would be a contract violation -- constitution.md Sec 6.3 requires
    components to "avoid heavyweight host libraries that compromise WASM
    portability" -- so that case now fails loudly and immediately instead
    of being silently patched over.
    """
    store = store_factory(engine)
    store.set_wasi(wasi_config_factory())

    comp = component_from_file(engine, str(wasm_path))
    linker = linker_factory(engine)
    linker.add_wasip2()

    instance = linker.instantiate(store, comp)
    return store, instance


def call_function(
    store: Any,
    instance: SupportsExports,
    interface_export: str,
    function_name: str,
    args: list[Any],
) -> Any:
    """Resolve and call a single exported function on an instance."""
    iface_idx = instance.get_export_index(store, interface_export)
    if iface_idx is None:
        raise RuntimeError(f"export '{interface_export}' not found")

    func_idx = instance.get_export_index(store, function_name, iface_idx)
    if func_idx is None:
        raise RuntimeError(
            f"function '{function_name}' not found in '{interface_export}'"
        )

    func = instance.get_func(store, func_idx)
    if func is None:
        raise RuntimeError(f"could not load function '{function_name}'")

    result = func(store, *args)
    func.post_return(store)
    return result
