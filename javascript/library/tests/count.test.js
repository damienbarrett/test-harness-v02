import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  formatMismatch,
  loadTaskContractFixtures,
} from "../../test-support/task-contract.js";
import { countTasks } from "../src/count.js";

const { testData } = await loadTaskContractFixtures();

describe("countTasks in Node", () => {
  for (const { description, input, expected } of testData.tests) {
    it(description, () => {
      const actual = countTasks(input.tasks);
      assert.equal(
        actual,
        expected,
        formatMismatch(description, actual, expected),
      );
    });
  }
});
