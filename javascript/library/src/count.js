/**
 * @typedef {{ name: string }} Task
 */

/**
 * Returns the count of tasks in the provided list.
 * @param {Task[]} tasks
 * @returns {number}
 */
export function countTasks(tasks) {
  return tasks.length;
}
