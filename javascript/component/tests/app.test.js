import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  formatMismatch,
  loadTaskContractFixtures,
} from "../../test-support/task-contract.js";
import { taskCollections } from "../src/app.js";

const { testData } = await loadTaskContractFixtures();

describe("taskCollections from source", () => {
  for (const { description, input, expected } of testData.tests) {
    it(description, () => {
      const actual = taskCollections.countTasks(input.tasks);
      assert.equal(
        actual,
        expected,
        formatMismatch(description, actual, expected),
      );
    });
  }
});
