// Thin native fixture adapter: gzip + utf-8 + containment under
// common/fixtures/ only.
//
// Mirrors the harness's `$fixture` descriptor contract
// (test-harness/src/harness/fixtures.py) for the subset a native suite
// needs, so this language's tests can drive the same declarative cases the
// central WASM harness runs. The error paths are pinned by
// fixture-adapter.test.js against the canonical conformance case names in
// test-harness/tests/fixture_conformance.py.

import { gunzipSync } from "node:zlib";
import { readFileSync, realpathSync, statSync } from "node:fs";
import path from "node:path";

const DEFAULT_MAX_BYTES = 8 * 1024 * 1024;

export class FixtureError extends Error {}

export function resolveFixture(descriptor, root, maxBytes = DEFAULT_MAX_BYTES) {
  const ref = descriptor["$fixture"];
  if (typeof ref !== "string") {
    throw new FixtureError(
      "'$fixture' must be a string repo-root-relative path",
    );
  }

  const compression = descriptor.compression;
  if (compression !== undefined && compression !== "gzip") {
    throw new FixtureError(
      `unsupported compression ${JSON.stringify(compression)}`,
    );
  }
  const encoding = descriptor.encoding ?? "utf-8";
  if (encoding !== "utf-8") {
    throw new FixtureError(`unsupported encoding ${JSON.stringify(encoding)}`);
  }

  if (path.isAbsolute(ref)) {
    throw new FixtureError(
      `fixture '${ref}' must be a repo-root-relative path, not an absolute path`,
    );
  }

  // realpathSync follows symlinks and collapses `..`, so the containment
  // check rejects both traversal and symlink escapes on real paths.
  const fixturesRoot = realpathSync(path.join(root, "common", "fixtures"));
  let real;
  try {
    real = realpathSync(path.join(root, ref));
  } catch {
    throw new FixtureError(
      `fixture '${ref}' does not exist (or is not a regular file)`,
    );
  }
  if (real !== fixturesRoot && !real.startsWith(fixturesRoot + path.sep)) {
    throw new FixtureError(
      `fixture '${ref}' must resolve under common/fixtures/`,
    );
  }
  if (!statSync(real).isFile()) {
    throw new FixtureError(
      `fixture '${ref}' does not exist (or is not a regular file)`,
    );
  }

  let data = readFileSync(real);
  if (data.length > maxBytes) {
    throw new FixtureError(
      `fixture '${ref}' is ${data.length} bytes on disk, ` +
        `which exceeds the ${maxBytes}-byte limit`,
    );
  }

  if (compression === "gzip") {
    try {
      data = gunzipSync(data);
    } catch (cause) {
      throw new FixtureError(
        `fixture '${ref}' is not valid gzip data: ${cause}`,
      );
    }
    if (data.length > maxBytes) {
      throw new FixtureError(
        `fixture '${ref}' decompresses to more than ${maxBytes} bytes`,
      );
    }
  }

  const decoder = new TextDecoder("utf-8", { fatal: true });
  try {
    return decoder.decode(data);
  } catch (cause) {
    throw new FixtureError(`fixture '${ref}' is not valid utf-8: ${cause}`);
  }
}
