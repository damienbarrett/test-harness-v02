from pathlib import Path

import pytest

from harness.invocation import call_function, instantiate_component


class FakeStore:
    def __init__(self, engine):
        self.engine = engine
        self.wasi = None

    def set_wasi(self, config):
        self.wasi = config


class FakeLinker:
    """A wasmtime.component.Linker double.

    ``raises`` simulates ``linker.instantiate`` failing (e.g. an unresolved
    import); ``returns`` is the sentinel returned on success.
    """

    def __init__(self, *, raises: Exception | None = None, returns=None):
        self.raises = raises
        self.returns = returns if returns is not None else object()
        self.add_wasip2_called = False

    def add_wasip2(self):
        self.add_wasip2_called = True

    def instantiate(self, store, comp):
        if self.raises is not None:
            raise self.raises
        return self.returns


class FakeInstance:
    """A wasmtime component instance double keyed by (name, parent)."""

    def __init__(self, exports: dict, funcs: dict):
        self._exports = exports
        self._funcs = funcs

    def get_export_index(self, store, name, parent=None):
        return self._exports.get((name, parent))

    def get_func(self, store, index):
        return self._funcs.get(index)


class FakeFunc:
    def __init__(self, result):
        self.result = result
        self.post_return_called = False
        self.call_args = None

    def __call__(self, store, *args):
        self.call_args = args
        return self.result

    def post_return(self, store):
        self.post_return_called = True


# --- instantiate_component -------------------------------------------------


def test_instantiate_component_succeeds_on_first_try():
    sentinel_instance = object()
    linker = FakeLinker(returns=sentinel_instance)

    store, instance = instantiate_component(
        engine=object(),
        wasm_path=Path("fake.wasm"),
        component_from_file=lambda engine, path: "component",
        linker_factory=lambda engine: linker,
        store_factory=FakeStore,
        wasi_config_factory=lambda: "wasi-config",
    )

    assert instance is sentinel_instance
    assert isinstance(store, FakeStore)
    assert store.wasi == "wasi-config"
    assert linker.add_wasip2_called


def test_instantiate_component_propagates_instantiation_failure_unchanged():
    """No fallback exists (removed once
    all three real components were confirmed to instantiate cleanly against
    a plain WASIp2-only linker -- see tests/test_real_component_contracts.py).
    Any instantiation failure -- including the exact "matching
    implementation was not found in the linker" shape wasmtime==43.0.0 used
    to trigger a retry for -- now propagates unchanged, with exactly one
    linker ever constructed."""
    original = RuntimeError(
        "component imports instance `test:comp/custom-import`, but a "
        "matching implementation was not found in the linker"
    )
    first_linker = FakeLinker(raises=original)
    linker_calls: list[FakeLinker] = []

    def linker_factory(engine):
        linker = first_linker if not linker_calls else FakeLinker()
        linker_calls.append(linker)
        return linker

    with pytest.raises(RuntimeError) as excinfo:
        instantiate_component(
            engine=object(),
            wasm_path=Path("fake.wasm"),
            component_from_file=lambda engine, path: "component",
            linker_factory=linker_factory,
            store_factory=FakeStore,
            wasi_config_factory=lambda: "wasi-config",
        )

    assert excinfo.value is original
    assert len(linker_calls) == 1  # no fallback linker was ever constructed


# --- call_function -----------------------------------------------------


def test_call_function_success_calls_and_post_returns():
    func = FakeFunc(result=42)
    instance = FakeInstance(
        exports={
            ("common:tasks/task-collections", None): "iface-idx",
            ("count-tasks", "iface-idx"): "func-idx",
        },
        funcs={"func-idx": func},
    )

    result = call_function(
        store="store",
        instance=instance,
        interface_export="common:tasks/task-collections",
        function_name="count-tasks",
        args=[1, 2],
    )

    assert result == 42
    assert func.call_args == (1, 2)
    assert func.post_return_called


def test_call_function_missing_interface_export_raises():
    instance = FakeInstance(exports={}, funcs={})
    with pytest.raises(RuntimeError, match="export 'missing-iface' not found"):
        call_function("store", instance, "missing-iface", "fn", [])


def test_call_function_missing_function_export_raises():
    instance = FakeInstance(exports={("iface", None): "iface-idx"}, funcs={})
    with pytest.raises(
        RuntimeError, match="function 'missing-fn' not found in 'iface'"
    ):
        call_function("store", instance, "iface", "missing-fn", [])


def test_call_function_unresolvable_func_index_raises():
    instance = FakeInstance(
        exports={("iface", None): "iface-idx", ("fn", "iface-idx"): "func-idx"},
        funcs={},
    )
    with pytest.raises(RuntimeError, match="could not load function 'fn'"):
        call_function("store", instance, "iface", "fn", [])
