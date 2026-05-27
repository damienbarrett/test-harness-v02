use serde::Deserialize;

/// A unit of work to be completed.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
pub struct Task {
    /// The human-readable name of the task.
    pub name: String,
}

/// Returns the count of tasks in the provided list.
///
/// Returns `u32` to align with the WIT contract in `common/wit/tasks.wit`.
/// Panics if the count exceeds `u32::MAX` (~4.29 billion); a `Vec<Task>`
/// of that size is not realistically constructible on current hardware.
pub fn count_tasks(tasks: &[Task]) -> u32 {
    u32::try_from(tasks.len()).expect("task count exceeds u32::MAX")
}
