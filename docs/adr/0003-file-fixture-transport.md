# 0003. File Fixture Transport via `$fixture` Descriptors

Date: 2026-07-07

Status: accepted

## Context

The refactoring plan's stated invariant is that "components receive pure
data and do not read fixture files themselves," and constitution.md §7
(Universal) requires I/O and side effects to be pushed to the edges. HTML
parsing test cases need large, realistic captured pages -- for example
`common/fixtures/html-parser/newworld-search-eggs.html.gz` (139,258 bytes
gzipped, from a 592,574-byte raw capture) -- that are impractical to inline
in a `*.test.json` suite's `input`. There needed to be a declarative way for
a test case to reference such a file without teaching the component itself
about the filesystem, and without letting fixture resolution happen at an
uncontrolled point (e.g. after schema validation, or only inside one
consumer).

## Decision

`test-harness/src/harness/fixtures.py` is the single owner of `$fixture`
descriptor resolution. A descriptor
`{"$fixture": "<repo-relative path>", "compression"?: "gzip", "encoding"?: "utf-8"}`
may appear anywhere inside a case's `input`, at any nesting depth, and is
replaced with the decoded file contents before anything consumes it. Only
gzip compression (applied solely when declared, never inferred from the file
extension) and UTF-8 decoding are supported; any other key in the descriptor
is an error. Resolved paths are checked by realpath, must remain contained
under `common/fixtures/`, and both on-disk and decompressed size are capped
by `HARNESS_FIXTURE_MAX_BYTES` (default 8 MiB) with incremental, bomb-safe
gzip decompression. Both `harness.contracts` (which validates the
materialized input against the function's parameter schema before any
component runs) and `harness.cli` (which builds the actual call arguments)
resolve through this same module, so a component always receives a decoded
string -- never a path, and never the descriptor object itself.

## Consequences

- A capability ships one committed compressed fixture and can reference it
  from any number of test cases, without ever checking in the raw HTML.
- Any resolution failure (missing file, corrupt gzip, non-UTF-8 bytes,
  traversal or symlink escape, oversized payload, unknown descriptor key,
  unsupported compression/encoding value) is a `contracts:check`-time
  failure with a message naming the fixture, not a runtime surprise inside
  a component or a silently-wrong test result.
- Native (non-WASM) language test runners get no fixture support for free; a
  thin native adapter is only justified once a natively-run suite actually
  contains `$fixture` descriptors (none does yet), and any adapter added
  later must be tested against the same reusable conformance cases in
  `test-harness/tests/fixture_conformance.py`.
- Small, focused HTML fragments stay inline in a suite's `input`; only
  realistic captured pages belong under `common/fixtures/` as external
  gzipped regression fixtures -- an uncompressed copy is never committed
  alongside the archive.
