"""Central contract validation for ``common/*.test.json`` suites.

This module discovers every JSON Schema file under ``common/`` (domain
entities, the suite-format schema, and each function's parameter/return
schema) and builds a single deterministic ``referencing.Registry`` keyed by
both a schema's own ``$id`` and its repo-root-relative POSIX path (e.g.
``common/entities/task-schema.json``). Every schema in this repo declares
its own repo-relative path as its ``$id``, and that path is also each
schema's base URI, so an existing relative ``$ref`` (such as
``../../entities/task-schema.json`` inside a function schema) resolves
through the registry without any manual inlining.

``validate_contracts`` is the entry point: it checks every discovered
``*.test.json`` suite against its declared contract -- the suite-format
schema itself, the WIT world/interface/function it claims to exercise, its
function's parameter/return JSON Schemas, referenced fixture files, and two
forms of WIT/JSON-Schema conformance (numeric bounds and record shape). It
returns a list of human-readable error strings; an empty list means every
discovered suite is valid. It never instantiates or invokes a WASM
component -- ``harness.cli.main`` runs it after discovery and before any
component is touched, so a malformed contract fails before invocation
rather than during it (docs/refactoring-plan.md Phase 3).

**WIT is authoritative.** A WIT ``record`` (e.g. ``task`` in
``common/wit/tasks.wit``) is the source of truth for a domain entity's
shape. A JSON Schema entity file under ``common/entities/`` (e.g.
``task-schema.json``) exists only to give JSON-Schema-based tooling
(including this module's own case-input validation) a schema view of that
same shape -- it is a mirror, not an independent declaration. The
record-conformance check in this module exists to catch that mirror
drifting out of sync with the WIT record it mirrors, never the reverse:
if the two disagree, the WIT declaration wins and the entity schema is
what must change.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .models import WitFunction, WitInterface, WitRecord
from .wit import WitError, WitWorld, discover_worlds

# test-harness/src/harness/contracts.py -> repo root is four levels up.
ROOT = Path(__file__).resolve().parents[3]

# The suite-format schema's repo-relative path, which is also its `$id` and
# its registry key (see `build_registry`).
SUITE_SCHEMA_URI = "common/schemas/test-suite.schema.json"

# WIT unsigned integer types -> their exact maximum value (minimum is
# always 0). u32 max: 4294967295.
_WIT_UNSIGNED_MAX: dict[str, int] = {
    "u8": 2**8 - 1,
    "u16": 2**16 - 1,
    "u32": 2**32 - 1,
    "u64": 2**64 - 1,
}

# WIT signed integer types -> (minimum, maximum).
_WIT_SIGNED_BOUNDS: dict[str, tuple[int, int]] = {
    "s8": (-(2**7), 2**7 - 1),
    "s16": (-(2**15), 2**15 - 1),
    "s32": (-(2**31), 2**31 - 1),
    "s64": (-(2**63), 2**63 - 1),
}

_WIT_FLOAT_TYPES = frozenset({"float32", "float64"})

# WIT keywords/primitives that never name a user-declared type; any other
# bareword identifier found in a type expression is a candidate named type
# (a `record`, in the cases this module understands).
_WIT_TYPE_KEYWORDS = frozenset(
    {
        "bool",
        "s8", "s16", "s32", "s64",
        "u8", "u16", "u32", "u64",
        "f32", "f64", "float32", "float64",
        "char", "string",
        "list", "option", "result", "tuple", "borrow", "own", "stream", "future",
    }
)

_TYPE_IDENTIFIER_RE = re.compile(r"[A-Za-z][\w-]*")


def _discover_schema_files(root: Path) -> list[Path]:
    """Every schema file the registry should know about: domain entities,
    the suite-format schema(s), and each function's parameter/return
    schema -- never ``*.test.json`` suite files themselves."""
    common = root / "common"
    paths: list[Path] = []
    entities_dir = common / "entities"
    if entities_dir.is_dir():
        paths.extend(sorted(entities_dir.glob("*.json")))
    schemas_dir = common / "schemas"
    if schemas_dir.is_dir():
        paths.extend(sorted(schemas_dir.glob("*.json")))
    functions_dir = common / "functions"
    if functions_dir.is_dir():
        paths.extend(sorted(functions_dir.glob("*/*.schema.json")))
    return paths


def build_registry(root: Path) -> tuple[Registry, dict[str, dict[str, Any]]]:
    """Build a deterministic ``referencing`` registry from every schema
    discovered under ``common/`` (see ``_discover_schema_files``).

    Each schema is registered under both its own ``$id`` and its
    repo-root-relative POSIX path; by convention every schema in this repo
    declares the latter as the former, so this is normally registering the
    same resource twice under identical keys -- harmless, and it keeps
    lookup-by-path working even if a schema's ``$id`` were ever to diverge
    from its path.

    Returns ``(registry, schemas_by_path)``, where ``schemas_by_path`` maps
    each schema's repo-relative POSIX path to its already-parsed JSON
    contents, so callers do not need to re-read and re-parse a schema file
    they already know the path of.
    """
    schemas_by_path: dict[str, dict[str, Any]] = {}
    resources: list[tuple[str, Resource]] = []
    for path in _discover_schema_files(root):
        contents = json.loads(path.read_text())
        rel = path.relative_to(root).as_posix()
        schemas_by_path[rel] = contents
        resource = Resource.from_contents(contents, default_specification=DRAFT202012)
        resources.append((rel, resource))
        schema_id = contents.get("$id")
        if schema_id and schema_id != rel:
            resources.append((schema_id, resource))
    registry = Registry().with_resources(resources)
    return registry, schemas_by_path


def _validator_for_ref(registry: Registry, ref: str) -> Draft202012Validator:
    """A validator for the schema (or sub-schema, addressed by a JSON
    Pointer fragment such as ``"<path>#/parameters"``) named by ``ref``,
    resolved through ``registry`` so relative ``$ref``s inside the target
    schema keep resolving against its own base URI."""
    return Draft202012Validator({"$ref": ref}, registry=registry)


def _iter_fixture_descriptors(value: Any) -> Iterable[dict[str, Any]]:
    """Yield every ``{"$fixture": "<path>", ...}`` descriptor found
    anywhere inside ``value`` (a test case's ``input``), at any nesting
    depth (inside nested objects and inside lists)."""
    if isinstance(value, dict):
        if isinstance(value.get("$fixture"), str):
            yield value
        for nested in value.values():
            yield from _iter_fixture_descriptors(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_fixture_descriptors(item)


def _check_fixtures(root: Path, input_value: Any, rel: str, description: str) -> list[str]:
    """Every ``$fixture`` descriptor's referenced path must exist and must
    resolve under ``common/fixtures/``. Full fixture resolution (encoding,
    compression, size limits) is Phase 4; this is only an existence and
    confinement check."""
    errors: list[str] = []
    fixtures_root = (root / "common" / "fixtures").resolve()
    for descriptor in _iter_fixture_descriptors(input_value):
        fixture_ref = descriptor["$fixture"]
        candidate = (root / fixture_ref).resolve()
        try:
            candidate.relative_to(fixtures_root)
        except ValueError:
            errors.append(
                f"{rel}: case '{description}': fixture '{fixture_ref}' must resolve "
                "under common/fixtures/"
            )
            continue
        if not candidate.is_file():
            errors.append(f"{rel}: case '{description}': fixture '{fixture_ref}' does not exist")
    return errors


def _named_types_in(type_text: str) -> set[str]:
    """Bareword identifiers in a WIT type expression that aren't WIT
    keywords/primitives -- candidate named (record) types."""
    return {
        token for token in _TYPE_IDENTIFIER_RE.findall(type_text) if token not in _WIT_TYPE_KEYWORDS
    }


def _reachable_records(function: WitFunction, interface: WitInterface) -> dict[str, WitRecord]:
    """Every WIT record type reachable from ``function``'s declared
    parameter types, transitively through the fields of any record found
    along the way (e.g. ``tasks: list<task>`` reaches ``task``)."""
    found: dict[str, WitRecord] = {}
    frontier: set[str] = set()
    for type_text in function.param_types:
        frontier |= _named_types_in(type_text)
    while frontier:
        # Every name ever added to `frontier` is excluded from re-addition
        # once it lands in `found` (see the `- set(found)` below), so a
        # name popped here is never already in `found` -- no extra
        # already-seen guard is needed, and a self- or mutually-referencing
        # record cannot cause an infinite loop.
        name = frontier.pop()
        record = interface.records.get(name)
        if record is None:
            continue  # not a record in this interface (enum/variant/resource, or external)
        found[name] = record
        for record_field in record.fields:
            frontier |= _named_types_in(record_field.type) - set(found)
    return found


def _check_record_conformance(root: Path, records: dict[str, WitRecord], rel: str) -> list[str]:
    """WIT is authoritative (see module docstring): if
    ``common/entities/{record-name}-schema.json`` exists for a reachable
    WIT record, its declared ``properties`` keys must equal the record's
    field names exactly."""
    errors: list[str] = []
    for name, record in sorted(records.items()):
        schema_path = root / "common" / "entities" / f"{name}-schema.json"
        if not schema_path.is_file():
            continue
        schema = json.loads(schema_path.read_text())
        schema_props = set((schema.get("properties") or {}).keys())
        wit_fields = set(record.field_names)
        if schema_props != wit_fields:
            errors.append(
                f"{rel}: entity schema 'common/entities/{name}-schema.json' properties "
                f"{sorted(schema_props)} do not match WIT record '{name}' fields "
                f"{sorted(wit_fields)}"
            )
    return errors


def _check_numeric_conformance(
    returns_wit: str | None,
    returns_schema: dict[str, Any],
    rel: str,
    function: str,
) -> list[str]:
    """A WIT numeric return type implies exact bounds; the function
    schema's ``returns`` must declare bounds at least as tight as WIT
    requires -- missing or looser bounds are a validation error."""
    if returns_wit is None:
        return []

    errors: list[str] = []

    if returns_wit in _WIT_UNSIGNED_MAX:
        lo, hi = 0, _WIT_UNSIGNED_MAX[returns_wit]
    elif returns_wit in _WIT_SIGNED_BOUNDS:
        lo, hi = _WIT_SIGNED_BOUNDS[returns_wit]
    elif returns_wit in _WIT_FLOAT_TYPES:
        if returns_schema.get("type") != "number":
            errors.append(
                f"{rel}: '{function}' returns schema must declare type 'number' for WIT "
                f"type '{returns_wit}' (found {returns_schema.get('type')!r})"
            )
        return errors
    else:
        return errors  # not a recognized WIT numeric primitive; nothing to check

    schema_min = returns_schema.get("minimum")
    schema_max = returns_schema.get("maximum")
    if schema_min is None or schema_min < lo:
        errors.append(
            f"{rel}: '{function}' returns schema must declare minimum >= {lo} for WIT "
            f"type '{returns_wit}' (found {schema_min!r})"
        )
    if schema_max is None or schema_max > hi:
        errors.append(
            f"{rel}: '{function}' returns schema must declare maximum <= {hi} for WIT "
            f"type '{returns_wit}' (found {schema_max!r})"
        )
    return errors


def _validate_suite_file(
    root: Path,
    path: Path,
    worlds: list[WitWorld],
    registry: Registry,
    schemas_by_path: dict[str, dict[str, Any]],
) -> list[str]:
    rel = path.relative_to(root).as_posix()

    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [f"{rel}: invalid JSON: {exc}"]

    suite_validator = _validator_for_ref(registry, SUITE_SCHEMA_URI)
    schema_errors = sorted(suite_validator.iter_errors(raw), key=lambda e: str(e.path))
    if schema_errors:
        errors = []
        for err in schema_errors:
            loc = "/".join(str(p) for p in err.path)
            where = f" at '{loc}'" if loc else ""
            errors.append(f"{rel}: suite schema violation{where}: {err.message}")
        return errors

    function = raw["function"]
    expected_function = path.name.removesuffix(".test.json")
    if function != expected_function:
        return [f"{rel}: function '{function}' does not match filename stem '{expected_function}'"]

    interface = path.parent.name
    matching_worlds = [world for world in worlds if world.exports_interface(interface)]
    if not matching_worlds:
        return [f"{rel}: interface '{interface}' is not exported by any discovered world"]

    signature = None
    chosen_world = None
    for world in matching_worlds:
        candidate_signature = world.function_signature(interface, function)
        if candidate_signature is not None:
            signature = candidate_signature
            chosen_world = world
            break
    if signature is None:
        return [
            f"{rel}: function '{function}' is not declared on interface '{interface}' "
            "in the WIT contract"
        ]

    function_schema_path = path.parent / f"{function}.schema.json"
    if not function_schema_path.is_file():
        return [
            f"{rel}: missing function schema "
            f"'{function_schema_path.relative_to(root).as_posix()}'"
        ]

    function_schema_rel = function_schema_path.relative_to(root).as_posix()
    function_schema = schemas_by_path.get(function_schema_rel)
    if function_schema is None:  # pragma: no cover - defensive; scan always finds this file
        function_schema = json.loads(function_schema_path.read_text())

    errors: list[str] = []

    errors.extend(
        _check_numeric_conformance(signature.returns, function_schema.get("returns", {}), rel, function)
    )

    assert chosen_world is not None  # a signature was found, so its world was recorded too
    interface_obj = chosen_world.interfaces.get(interface)
    if interface_obj is not None:
        reachable = _reachable_records(signature, interface_obj)
        errors.extend(_check_record_conformance(root, reachable, rel))

    params_validator = _validator_for_ref(registry, f"{function_schema_rel}#/parameters")
    returns_validator = _validator_for_ref(registry, f"{function_schema_rel}#/returns")

    descriptions_seen: set[str] = set()
    duplicates: set[str] = set()

    for case in raw["tests"]:
        description = case["description"]
        if description in descriptions_seen:
            duplicates.add(description)
        descriptions_seen.add(description)

        for err in params_validator.iter_errors(case["input"]):
            errors.append(f"{rel}: case '{description}': input invalid: {err.message}")
        for err in returns_validator.iter_errors(case["expected"]):
            errors.append(f"{rel}: case '{description}': expected invalid: {err.message}")

        errors.extend(_check_fixtures(root, case["input"], rel, description))

    if duplicates:
        errors.append(f"{rel}: duplicate case description(s): {sorted(duplicates)}")

    return errors


def validate_contracts(root: Path) -> list[str]:
    """Validate every discovered ``*.test.json`` suite under
    ``common/functions/`` against its declared contract. See the module
    docstring for the full list of checks performed.

    Returns a list of human-readable error strings; an empty list means
    every discovered suite is valid. This function only reads files under
    ``root`` -- it never instantiates or invokes a WASM component.
    """
    try:
        worlds = discover_worlds(root)
    except WitError as exc:
        return [f"WIT discovery failed: {exc}"]

    functions_dir = root / "common" / "functions"
    if not functions_dir.is_dir():
        return []

    registry, schemas_by_path = build_registry(root)

    errors: list[str] = []
    for suite_path in sorted(functions_dir.rglob("*.test.json")):
        errors.extend(_validate_suite_file(root, suite_path, worlds, registry, schemas_by_path))
    return errors


def main(root: Path | None = None) -> int:
    root = ROOT if root is None else root
    errors = validate_contracts(root)
    if errors:
        print("FAIL: contract validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    print("OK: all contracts valid.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
