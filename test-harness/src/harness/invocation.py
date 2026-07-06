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

    Returns ``(store, instance)`` on success or raises on failure.
    """
    store = store_factory(engine)
    store.set_wasi(wasi_config_factory())

    comp = component_from_file(engine, str(wasm_path))
    linker = linker_factory(engine)
    linker.add_wasip2()

    try:
        instance = linker.instantiate(store, comp)
        return store, instance
    except Exception:
        # Some components (e.g. componentize-js) import wasi:http which
        # wasmtime-py does not provide. Fall back to trapping unknown
        # imports -- this works only if the tested function doesn't
        # actually call into those imports at runtime.
        store = store_factory(engine)
        store.set_wasi(wasi_config_factory())
        linker = linker_factory(engine)
        linker.define_unknown_imports_as_traps(comp)
        linker.allow_shadowing = True
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
        raise RuntimeError(f"function '{function_name}' not found in '{interface_export}'")

    func = instance.get_func(store, func_idx)
    if func is None:
        raise RuntimeError(f"could not load function '{function_name}'")

    result = func(store, *args)
    func.post_return(store)
    return result
