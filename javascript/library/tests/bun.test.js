import { describe, expect, test } from "bun:test";

import { loadTaskContractFixtures, formatMismatch } from "../../test-support/task-contract.js";
import { countTasks } from "../src/count.js";

const { testData } = await loadTaskContractFixtures();

describe("countTasks in Bun", () => {
  for (const { description, input, expected } of testData.tests) {
    test(description, () => {
      const actual = countTasks(input.tasks);
      expect(actual).toBe(expected);
      if (actual !== expected) {
        throw new Error(formatMismatch(description, actual, expected));
      }
    });
  }
});
