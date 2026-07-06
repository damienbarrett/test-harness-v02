// Schema-validation of these same fixtures against their JSON Schema
// contracts is now owned centrally by test-harness (harness.contracts /
// check-contracts.py), not duplicated per language -- this module only
// loads the declarative test data itself for language-level execution
// tests to run against a real implementation.
const TEST_DATA_URL = new URL("../../common/functions/task-collections/count-tasks.test.json", import.meta.url);

async function readText(url) {
  if (typeof Deno !== "undefined") {
    return Deno.readTextFile(url);
  }

  const { readFile } = await import("node:fs/promises");
  return readFile(url, "utf8");
}

async function readJson(url) {
  return JSON.parse(await readText(url));
}

export async function loadTaskContractFixtures() {
  const testData = await readJson(TEST_DATA_URL);
  return { testData };
}

export function formatMismatch(description, actual, expected) {
  return `${description}: expected ${expected}, got ${actual}`;
}
