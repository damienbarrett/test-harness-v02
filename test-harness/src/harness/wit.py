"""WIT world discovery.

Hand-rolled (no external WIT-parsing dependency) extraction of the
information the harness needs from each ``common/wit/*.wit`` file:

* the package's namespace and name (from ``package ns:name;``, tolerating
  an ``@version`` suffix),
* every world declared in the file, and the interfaces each world exports,
* every interface declared in the file, and each of its functions'
  parameter names in declared order (the contract-authoritative order used
  to build positional call arguments -- see ``harness.conversion``), each
  parameter's declared type text, and the function's declared return type
  text (used by ``harness.contracts`` for WIT/JSON-Schema conformance
  checks) -- further parsed into ``(ok, err)`` type-text slots when the
  return type is a ``result<...>`` (see ``_parse_result_return`` and
  ``harness.models.WitFunction``),
* every ``record`` type declared inside an interface, and its field names
  in declared order (also used by ``harness.contracts``).

``//`` and ``///`` doc comments are stripped before parsing (both share the
same ``//`` prefix). Whitespace, including newlines inside a multi-line
function signature, is insignificant.

A file with no ``package`` declaration is a hard failure (``WitParseError``):
there is no reasonable namespace/package to fall back to. Two worlds
sharing a name -- even across different packages/files -- is also a hard
failure (``DuplicateWorldError``): both would be discovered as needing the
same ``{world}.wasm`` artifact path, which is unresolvable.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import WitFunction, WitInterface, WitRecord, WitRecordField, WitWorld


class WitError(Exception):
    """Base class for WIT discovery/parsing failures."""


class WitParseError(WitError):
    """A WIT file could not be parsed (e.g. missing ``package`` declaration)."""


class DuplicateWorldError(WitError):
    """Two discovered worlds (from different packages) share a name."""


_COMMENT_RE = re.compile(r"//[^\n]*")
_PACKAGE_RE = re.compile(
    r"\bpackage\s+([A-Za-z][\w-]*)\s*:\s*([A-Za-z][\w-]*)(?:@[\w.\-]+)?\s*;"
)
_EXPORT_RE = re.compile(r"\bexport\s+([A-Za-z][\w:./-]*)\s*;")
_FUNC_STMT_RE = re.compile(
    r"^\s*([A-Za-z][\w-]*)\s*:\s*func\s*\(([^)]*)\)\s*(?:->\s*(.+))?\s*$",
    re.DOTALL,
)

# Matches a return-type expression that is a WIT `result<...>` type in any
# of its forms: bare `result`, single-arg `result<T>`, or two-arg
# `result<T, E>` (either slot may be the `_` placeholder). Anchored to the
# whole (already-stripped) return text, since a WIT return type is always a
# single type expression -- there is nothing else it could be trailing.
_RESULT_RETURN_RE = re.compile(r"^result(?:<(.*)>)?$", re.DOTALL)


def _strip_comments(text: str) -> str:
    """Remove ``//`` and ``///`` line comments (doc comments use the same
    prefix as plain comments)."""
    return _COMMENT_RE.sub("", text)


def _find_blocks(text: str, keyword: str) -> list[tuple[str, str]]:
    """Find every ``keyword name { ... }`` block, returning ``(name, body)``
    pairs. Brace depth is tracked so nested blocks (e.g. a ``record``
    declared inside an ``interface``) do not truncate the outer block."""
    header_re = re.compile(rf"\b{keyword}\s+([A-Za-z][\w-]*)\s*\{{")
    blocks: list[tuple[str, str]] = []
    for match in header_re.finditer(text):
        name = match.group(1)
        depth = 1
        i = match.end()
        while i < len(text) and depth > 0:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        blocks.append((name, text[match.end() : i - 1]))
    return blocks


def _split_top_level(text: str) -> list[str]:
    """Split ``text`` on commas that are not nested inside ``<...>`` or
    ``(...)``, so a param list like
    ``pairs: list<tuple<u32, u32>>, label: string`` splits into exactly two
    parameter fragments instead of being cut apart by the comma inside
    ``tuple<u32, u32>``."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch in "<(":
            depth += 1
            current.append(ch)
        elif ch in ">)":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _split_statements(body: str) -> list[str]:
    """Split an interface body into top-level statements.

    A ``;``-terminated simple statement (function signature, ``use``, type
    alias) is returned without its trailing ``;``. A ``{ ... }``-terminated
    block (``record``/``variant``/``enum``/``flags``/``resource``) is
    returned whole, braces included, so callers can recognize and skip it
    (it always contains a literal ``{``, which a function signature never
    does).
    """
    statements: list[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(body):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                statements.append(body[start : i + 1])
                start = i + 1
        elif ch == ";" and depth == 0:
            statements.append(body[start:i])
            start = i + 1
    return statements


def _parse_result_return(returns_text: str) -> tuple[str | None, str | None] | None:
    """Parse a WIT return-type expression that may be a ``result<...>``
    type into its ``(ok, err)`` type-text slots.

    Returns ``None`` if ``returns_text`` is not a ``result`` type at all
    (e.g. ``"u32"`` or ``"list<task>"``) -- distinguishing "not a result"
    from "a result with both slots omitted" (bare ``result``), which would
    otherwise both look like ``(None, None)``.

    Handles every WIT ``result`` form: bare ``result`` (``(None, None)``),
    single-arg ``result<T>`` (``(T, None)`` -- no error type at all, not an
    omitted slot), and two-arg ``result<T, E>`` (either slot may itself be
    the ``_`` placeholder, normalized to ``None``).

    Nested generics are handled correctly: the outer ``<...>`` is matched
    by ``_RESULT_RETURN_RE`` greedily up to the *last* ``>`` in the text
    (correct because the whole string is a single type expression with
    nothing trailing it), and its content is split on top-level commas
    with ``_split_top_level`` -- the same helper already used for function
    parameter lists -- so an inner generic's own comma is not mistaken for
    the ok/err separator, e.g. ``result<list<record-x>, parse-error>``
    splits into ``"list<record-x>"`` and ``"parse-error"``, not three
    pieces.
    """
    match = _RESULT_RETURN_RE.match(returns_text)
    if match is None:
        return None
    content = match.group(1)
    if content is None:
        return (None, None)
    parts = [part.strip() for part in _split_top_level(content)]
    ok = parts[0] if len(parts) >= 1 and parts[0] not in ("", "_") else None
    err = parts[1] if len(parts) >= 2 and parts[1] not in ("", "_") else None
    return (ok, err)


def _parse_functions(body: str) -> dict[str, WitFunction]:
    functions: dict[str, WitFunction] = {}
    for stmt in _split_statements(body):
        if "{" in stmt:
            continue  # a nested type definition, not a function signature
        match = _FUNC_STMT_RE.match(stmt)
        if match is None:
            continue  # not a function signature (e.g. a `use` statement)
        name = match.group(1)
        params_str = match.group(2)
        returns_str = match.group(3)
        param_names: list[str] = []
        param_types: list[str] = []
        for fragment in _split_top_level(params_str):
            frag = fragment.strip()
            if not frag:
                continue
            pname, _, ptype = frag.partition(":")
            param_names.append(pname.strip())
            param_types.append(ptype.strip())
        returns = returns_str.strip() if returns_str is not None else None
        result_slots = _parse_result_return(returns) if returns is not None else None
        returns_ok, returns_err = (
            result_slots if result_slots is not None else (None, None)
        )
        functions[name] = WitFunction(
            name=name,
            params=tuple(param_names),
            param_types=tuple(param_types),
            returns=returns,
            returns_is_result=result_slots is not None,
            returns_ok=returns_ok,
            returns_err=returns_err,
        )
    return functions


def _parse_record_fields(body: str) -> tuple[WitRecordField, ...]:
    """Parse a ``record { ... }`` block's comma-separated ``name: type``
    fields, in declared order."""
    fields: list[WitRecordField] = []
    for fragment in _split_top_level(body):
        frag = fragment.strip()
        if not frag:
            continue
        fname, _, ftype = frag.partition(":")
        fields.append(WitRecordField(name=fname.strip(), type=ftype.strip()))
    return tuple(fields)


def _parse_records(body: str) -> dict[str, WitRecord]:
    """Find every ``record NAME { ... }`` block declared anywhere in an
    interface body (brace depth tracked, so this does not confuse a record
    nested inside another block)."""
    return {
        name: WitRecord(name=name, fields=_parse_record_fields(record_body))
        for name, record_body in _find_blocks(body, "record")
    }


def _parse_wit_file(path: Path) -> list[WitWorld]:
    text = _strip_comments(path.read_text())

    pkg_match = _PACKAGE_RE.search(text)
    if pkg_match is None:
        raise WitParseError(
            f"{path}: no 'package <namespace>:<name>;' declaration found"
        )
    namespace, package = pkg_match.group(1), pkg_match.group(2)

    interfaces = {
        name: WitInterface(
            name=name,
            functions=_parse_functions(body),
            records=_parse_records(body),
        )
        for name, body in _find_blocks(text, "interface")
    }

    worlds: list[WitWorld] = []
    for name, body in _find_blocks(text, "world"):
        exports = tuple(_EXPORT_RE.findall(body))
        worlds.append(
            WitWorld(
                namespace=namespace,
                package=package,
                name=name,
                exports=exports,
                interfaces=interfaces,
            )
        )
    return worlds


def discover_worlds(root: Path) -> list[WitWorld]:
    """Discover every world declared under ``common/wit/*.wit``.

    Raises ``WitParseError`` if a file lacks a package declaration, and
    ``DuplicateWorldError`` if two worlds (from different packages) share a
    name -- both would be discovered as needing the same ``{world}.wasm``
    artifact path.
    """
    wit_dir = root / "common" / "wit"
    if not wit_dir.is_dir():
        return []

    worlds: list[WitWorld] = []
    origin: dict[str, str] = {}

    for wit_file in sorted(wit_dir.glob("*.wit")):
        for world in _parse_wit_file(wit_file):
            label = f"{world.namespace}:{world.package} ({wit_file.name})"
            if world.name in origin:
                raise DuplicateWorldError(
                    f"world '{world.name}' is defined by both {origin[world.name]} "
                    f"and {label}; both would produce the artifact "
                    f"'{world.name}.wasm'"
                )
            origin[world.name] = label
            worlds.append(world)
    return worlds
