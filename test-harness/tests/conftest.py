"""Shared fixture-tree builders for harness unit tests.

All tests build fake repo trees under ``tmp_path`` -- none of these helpers
touch the real repository, the network, or built ``.wasm`` artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path


def write_wit_file(root: Path, filename: str, text: str) -> Path:
    wit_dir = root / "common" / "wit"
    wit_dir.mkdir(parents=True, exist_ok=True)
    path = wit_dir / filename
    path.write_text(text)
    return path


def write_world(root: Path, world_name: str, exported_interface: str = "task-collections") -> Path:
    return write_wit_file(
        root,
        "tasks.wit",
        f"package common:tasks;\n\nworld {world_name} {{\n  export {exported_interface};\n}}\n",
    )


def write_suite(root: Path, interface: str, function: str, tests: list[dict]) -> Path:
    d = root / "common" / "functions" / interface
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{function}.test.json"
    path.write_text(json.dumps({"function": function, "tests": tests}))
    return path


def write_component(root: Path, lang: str, world_name: str, content: bytes = b"fake-wasm") -> Path:
    d = root / lang / "component"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{world_name}.wasm"
    path.write_bytes(content)
    return path
