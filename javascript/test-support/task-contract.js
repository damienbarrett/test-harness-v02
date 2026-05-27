const TEST_DATA_URL = new URL("../../common/functions/task-collections/count-tasks.test.json", import.meta.url);
const FUNCTION_SCHEMA_URL = new URL("../../common/functions/task-collections/count-tasks.schema.json", import.meta.url);
const TASK_SCHEMA_URL = new URL("../../common/entities/task-schema.json", import.meta.url);

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
  const [testData, functionSchema, taskSchema] = await Promise.all([
    readJson(TEST_DATA_URL),
    readJson(FUNCTION_SCHEMA_URL),
    readJson(TASK_SCHEMA_URL),
  ]);

  return { testData, functionSchema, taskSchema };
}

export function loadParamsSchema(functionSchema, taskSchema) {
  const params = JSON.parse(JSON.stringify(functionSchema.parameters));
  params.properties.tasks.items = taskSchema;
  return params;
}

export function formatMismatch(description, actual, expected) {
  return `${description}: expected ${expected}, got ${actual}`;
}
