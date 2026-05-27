"""Make the component sources and the generated wit-bindgen bindings importable.

`src/app.py` lives outside any installed package and imports `wit_world`, the
package that `componentize-py bindings` writes into `../bindings/` at build
time. Neither path is on `sys.path` by default in a fresh pytest run, so we
prepend both here.

This is the host-side counterpart to the runtime layout that `componentize-py
componentize` assembles inside the WASM artifact (`-p src -p bindings`). The
test process therefore loads the same modules the WASM guest does, so the
host tests exercise the real WIT contract — `Task` is the generated dataclass
and `TaskCollections` is the generated abstract Protocol — instead of mocks.
"""

import sys
from pathlib import Path

_COMPONENT_ROOT = Path(__file__).resolve().parent.parent

for path in (_COMPONENT_ROOT / "bindings", _COMPONENT_ROOT / "src"):
    if path.is_dir():
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
