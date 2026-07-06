# html-parser fixtures

Captured pages used as regression fixtures for the future `html-parser`
capability (see docs/refactoring-plan.md). Referenced from test suites via
`$fixture` descriptors; the descriptor format, path-safety rules, and size
limits are documented in [`common/README.md`](../../README.md).

## newworld-search-eggs.html.gz

| | |
| --- | --- |
| Source URL | `www.newworld.co.nz` shop search, query "size 7 eggs", page 1 (`/shop/search?pg=1&q=size%207%20eggs&sf=products`) |
| Capture date | 2026-07-05 |
| Raw size | 592574 bytes (UTF-8 HTML) |
| Gzipped size | 139258 bytes (level 9, no filename/timestamp header -- `gzip -9 -n` equivalent) |

Declared in test suites as:

```json
{
  "$fixture": "common/fixtures/html-parser/newworld-search-eggs.html.gz",
  "compression": "gzip",
  "encoding": "utf-8"
}
```

Only the compressed file is committed; the harness decompresses and decodes
it at resolution time, and the component under test receives the decoded
HTML string -- never a file path.
