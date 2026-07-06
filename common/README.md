# common/

Shared contract definitions. This directory has no awareness of the
implementations that depend on it.

## Structure

```
common/
  wit/                  WIT interface definitions
  entities/             JSON Schema for domain types
  schemas/              Shared JSON Schemas for repo conventions (e.g. the suite format itself)
  functions/            Function schemas and test fixtures
```

## Naming convention

Test fixtures follow a convention that mirrors the WIT hierarchy:

```
functions/{interface}/{function}.test.json
functions/{interface}/{function}.schema.json
```

- **Directory name** = WIT interface name (kebab-case)
- **File stem** = WIT function name (kebab-case)

### Example

Given this WIT:

```wit
interface task-collections {
    count-tasks: func(tasks: list<task>) -> u32;
}
```

The corresponding files are:

```
functions/task-collections/count-tasks.test.json
functions/task-collections/count-tasks.schema.json
```

## Test fixture format

```json
{
  "function": "count-tasks",
  "tests": [
    {
      "description": "counts a list of tasks",
      "input": { "tasks": [{ "name": "Task 1" }] },
      "expected": 1
    }
  ]
}
```

- `function` names the function under test (kebab-case), and must equal
  the suite file's stem.
- Each test case has `description` (unique within the suite, non-empty),
  `input` (keyed by parameter name), and `expected` (the return value).
- An optional suite-level `targets` array (`["native", "component"]`)
  restricts which execution targets a suite applies to. This is reserved
  for the file-backed fixture work in a later phase; an unsupported target
  is a validation error, never a silent skip.
- No implementation-specific metadata belongs here.

The format itself is a JSON Schema at
[`schemas/test-suite.schema.json`](schemas/test-suite.schema.json)
(draft 2020-12). Every `*.test.json` suite is validated against it.

## Schema `$id` and registry convention

Every schema file under `common/` (`entities/*.json`, `schemas/*.json`,
`functions/*/*.schema.json`) declares an `$id` equal to its own
repo-root-relative POSIX path, e.g.:

```json
{ "$id": "common/entities/task-schema.json" }
```

`test-harness`'s `harness.contracts` module scans these files and builds a
single deterministic [`referencing`](https://pypi.org/project/referencing/)
registry keyed by both each schema's `$id` and that same repo-relative
path, with the path also serving as the schema's base URI. This is what
lets a function schema's existing relative `$ref` (e.g.
`"../../entities/task-schema.json"` in `count-tasks.schema.json`) resolve
deterministically without any manual inlining or a separate list of
schemas to register by hand -- add a new schema file with a correct `$id`
and it is picked up automatically.

## Contract validation and WIT-as-authority

`test-harness/check-contracts.py` (wired into both lifecycle runners as
`check-contracts` / `contracts:check`) validates every suite under
`common/functions/` before any component is built or invoked:

- the suite file against `schemas/test-suite.schema.json`;
- its `function` against the filename stem, and its interface (parent
  directory name) against a WIT world's exports;
- each case's `input`/`expected` against the function schema's
  `parameters`/`returns`;
- every `$fixture` reference (existence and confinement under
  `common/fixtures/`; full resolution is a later phase);
- WIT numeric bounds (e.g. a WIT `u32` return requires the function
  schema's `returns` to declare `minimum: 0` and `maximum: 4294967295` --
  never looser);
- WIT-vs-JSON-Schema record conformance.

For that last check, and in general: **WIT is authoritative.** A WIT
`record` (declared once under `common/wit/`) is the source of truth for a
domain entity's shape. A JSON Schema entity file under `common/entities/`
exists only to mirror that shape for JSON-Schema-based tooling; if the two
disagree, the WIT declaration wins and the entity schema is what must
change. `harness.contracts`'s record-conformance check exists to catch
that mirror drifting, not to introduce a second, independent source of
truth.
