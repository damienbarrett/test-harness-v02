import { loadTaskContractFixtures, formatMismatch } from "../../test-support/task-contract.js";
import { countTasks } from "../src/count.js";

const { testData } = await loadTaskContractFixtures();

for (const { description, input, expected } of testData.tests) {
  Deno.test(`countTasks in Deno: ${description}`, () => {
    const actual = countTasks(input.tasks);

    if (actual !== expected) {
      throw new Error(formatMismatch(description, actual, expected));
    }
  });
}
