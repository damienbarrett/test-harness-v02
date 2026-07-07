// javascript/test-support has no package.json/node_modules of its own (it is
// a shared, non-package directory - see the root README.md "Quality gates"
// section or lifecycle.sh comments). ESLint's flat config resolves the
// *nearest* eslint.config.js by
// walking up from each linted file's own directory, so this file must exist
// here for `npx eslint ... ../test-support` (run from javascript/library) to
// find a config at all; it deliberately does not define its own ruleset and
// re-exports javascript/library's config verbatim (the package chosen to
// cover test-support - see javascript/library/eslint.config.js).
export { default } from "../library/eslint.config.js";
