import js from "@eslint/js";

// Minimal, modern-ESM ruleset (Phase 9 of docs/refactoring-plan.md):
// `@eslint/js` recommended rules plus the ambient globals this package's own
// isomorphic test suite actually references across its four runtimes (Node,
// Bun, Deno, and Playwright-driven browsers). No stylistic rules here -
// formatting is Prettier's job (see `npx prettier --check`), not ESLint's.
//
// Also covers ../test-support/*.js (javascript/test-support has no package
// or eslint config of its own - this repo's justfile/Taskfile.yml `lint`
// recipe passes it explicitly alongside this package's own src/tests). The
// sibling javascript/component/eslint.config.js does not re-cover it.
export default [
  {
    ignores: ["node_modules/**"],
  },
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        // Used by tests/browser.test.js (runs under Node, driving Playwright)
        // and by tests/deno.test.js / ../test-support/task-contract.js
        // (feature-detected there via `typeof Deno !== "undefined"`).
        process: "readonly",
        fetch: "readonly",
        URL: "readonly",
        Deno: "readonly",
      },
    },
  },
];
