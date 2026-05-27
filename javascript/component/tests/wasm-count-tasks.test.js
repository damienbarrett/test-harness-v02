import { describe, it } from "node:test";
import assert from "node:assert/strict";
import Ajv2020 from "ajv/dist/2020.js";

import {
  formatMismatch,
  loadParamsSchema,
  loadTaskContractFixtures,
} from "../../test-support/task-contract.js";

const { taskCollections } = await import("../transpiled/task-component.js");
const { testData, functionSchema, taskSchema } = await loadTaskContractFixtures();

describe("countTasks (WASM component)", () => {
  for (const { description, input, expected } of testData.tests) {
    it(description, () => {
      const actual = taskCollections.countTasks(input.tasks);
      assert.equal(actual, expected, formatMismatch(description, actual, expected));
    });
  }
});

describe("WASM test data conforms to schema", () => {
  const ajv = new Ajv2020();
  const validateInput = ajv.compile(loadParamsSchema(functionSchema, taskSchema));
  const validateOutput = ajv.compile(functionSchema.returns);

  for (const { description, input, expected } of testData.tests) {
    it(description, () => {
      assert.equal(validateInput(input), true, JSON.stringify(validateInput.errors));
      assert.equal(validateOutput(expected), true, JSON.stringify(validateOutput.errors));
    });
  }
});
