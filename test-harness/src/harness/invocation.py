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


# wasmtime 43's component linker raises an error whose message contains
# exactly this phrase when a component imports something the linker has no
# definition for -- verified empirically against wasmtime==43.0.0 by
# instantiating a componentize-py-built component with an unresolved import,
# for both shapes it can take:
#   "component imports instance `ns:pkg/iface`, but a matching
#    implementation was not found in the linker"
#   "component imports function `name`, but a matching implementation was
#    not found in the linker"
# Matching on this substring keeps the fallback narrowly scoped to the
# unknown/missing-import case it exists to handle (e.g. a componentize-js
# output importing wasi:http, which wasmtime-py does not provide), instead
# of also swallowing unrelated instantiation failures such as a malformed
# module or a trapping start function.
_MISSING_IMPORT_MARKER = "matching implementation was not found in the linker"


def _is_missing_import_error(exc: Exception) -> bool:
    return _MISSING_IMPORT_MARKER in str(exc)


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

    If instantiation fails with the specific "unknown import" error shape
    wasmtime raises (see ``_MISSING_IMPORT_MARKER`` above), retry once with
    unknown imports defined as traps -- this only works if the tested
    function doesn't actually call into those imports at runtime. Any other
    failure is re-raised unchanged: this fallback is not meant to mask it.
    If the fallback instantiation also fails, the original exception is
    preserved as the cause of a new exception describing both failures.
    """
    store = store_factory(engine)
    store.set_wasi(wasi_config_factory())

    comp = component_from_file(engine, str(wasm_path))
    linker = linker_factory(engine)
    linker.add_wasip2()

    try:
        instance = linker.instantiate(store, comp)
        return store, instance
    except Exception as original_exc:
        if not _is_missing_import_error(original_exc):
            raise

        store = store_factory(engine)
        store.set_wasi(wasi_config_factory())
        linker = linker_factory(engine)
        linker.define_unknown_imports_as_traps(comp)
        linker.allow_shadowing = True
        linker.add_wasip2()
        try:
            instance = linker.instantiate(store, comp)
            return store, instance
        except Exception as fallback_exc:
            raise RuntimeError(
                "component instantiation failed even after falling back to "
                f"trapping unknown imports; original error: {original_exc}; "
                f"fallback error: {fallback_exc}"
            ) from original_exc


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
