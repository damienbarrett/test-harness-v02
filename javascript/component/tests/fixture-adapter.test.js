// Error-path conformance for the native fixture adapter, mirroring the
// canonical case names in test-harness/tests/fixture_conformance.py so the
// three languages' adapters cannot drift from the central resolver contract.

import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import { gzipSync } from "node:zlib";
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  rmSync,
  symlinkSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { resolveFixture, FixtureError } from "./fixture-adapter.js";

let root;
let fixturesDir;

before(() => {
  root = mkdtempSync(path.join(tmpdir(), "nw-fixture-"));
  fixturesDir = path.join(root, "common", "fixtures", "html-parser");
  mkdirSync(fixturesDir, { recursive: true });
  writeFileSync(path.join(fixturesDir, "plain.html"), "<p>plain</p>", "utf-8");
  writeFileSync(
    path.join(fixturesDir, "page.html.gz"),
    gzipSync(Buffer.from("<p>gzipped</p>", "utf-8")),
  );
  writeFileSync(
    path.join(fixturesDir, "not-gzip.html.gz"),
    Buffer.from("not gzip"),
  );
  writeFileSync(
    path.join(fixturesDir, "bad-utf8.html"),
    Buffer.from([0xff, 0xfe]),
  );
  writeFileSync(path.join(root, "outside.html"), "secret", "utf-8");
  symlinkSync(
    path.join(root, "outside.html"),
    path.join(fixturesDir, "escape.html"),
  );
});

after(() => {
  rmSync(root, { recursive: true, force: true });
});

const ref = (name) => `common/fixtures/html-parser/${name}`;

describe("resolveFixture", () => {
  it("reads plain text", () => {
    assert.equal(
      resolveFixture({ $fixture: ref("plain.html") }, root),
      "<p>plain</p>",
    );
  });

  it("decompresses gzip", () => {
    assert.equal(
      resolveFixture(
        { $fixture: ref("page.html.gz"), compression: "gzip" },
        root,
      ),
      "<p>gzipped</p>",
    );
  });

  it("rejects a missing file", () => {
    assert.throws(
      () => resolveFixture({ $fixture: ref("nope.html") }, root),
      FixtureError,
    );
  });

  it("rejects corrupt gzip", () => {
    assert.throws(
      () =>
        resolveFixture(
          { $fixture: ref("not-gzip.html.gz"), compression: "gzip" },
          root,
        ),
      FixtureError,
    );
  });

  it("rejects non-utf-8 content", () => {
    assert.throws(
      () => resolveFixture({ $fixture: ref("bad-utf8.html") }, root),
      FixtureError,
    );
  });

  it("rejects a traversal path", () => {
    assert.throws(
      () =>
        resolveFixture(
          { $fixture: "common/fixtures/../../outside.html" },
          root,
        ),
      FixtureError,
    );
  });

  it("rejects a symlink escape", () => {
    assert.throws(
      () => resolveFixture({ $fixture: ref("escape.html") }, root),
      FixtureError,
    );
  });

  it("rejects an absolute path", () => {
    assert.throws(
      () => resolveFixture({ $fixture: path.join(root, "outside.html") }, root),
      FixtureError,
    );
  });

  it("rejects an oversized fixture", () => {
    assert.throws(
      () => resolveFixture({ $fixture: ref("plain.html") }, root, 4),
      FixtureError,
    );
  });

  it("rejects unsupported compression and encoding", () => {
    assert.throws(
      () =>
        resolveFixture(
          { $fixture: ref("plain.html"), compression: "brotli" },
          root,
        ),
      FixtureError,
    );
    assert.throws(
      () =>
        resolveFixture(
          { $fixture: ref("plain.html"), encoding: "latin1" },
          root,
        ),
      FixtureError,
    );
  });

  it("rejects a non-string $fixture", () => {
    assert.throws(() => resolveFixture({ $fixture: 42 }, root), FixtureError);
  });
});
