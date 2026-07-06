import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { formatMismatch, loadTaskContractFixtures } from "../../test-support/task-contract.js";

const { taskCollections } = await import("../transpiled/task-component.js");
const { testData } = await loadTaskContractFixtures();

describe("countTasks (WASM component)", () => {
  for (const { description, input, expected } of testData.tests) {
    it(description, () => {
      const actual = taskCollections.countTasks(input.tasks);
      assert.equal(actual, expected, formatMismatch(description, actual, expected));
    });
  }
});
