/// A unit of work to be completed.
#[derive(Debug, Clone)]
#[cfg_attr(test, derive(serde::Deserialize))]
pub struct Task {
    /// The human-readable name of the task.
    pub name: String,
}

/// A task in WIT-wire shape — mirrors the wit-bindgen-generated
/// `bindings::exports::common::tasks::task_collections::Task`.
///
/// The generated binding type is gated behind `#[cfg(target_arch = "wasm32")]`
/// and is therefore invisible to host-side `cargo llvm-cov`. Mirroring the
/// shape here keeps the wire→native conversion path host-testable so it does
/// not silently slip out of coverage measurement.
#[derive(Debug, Clone)]
pub struct WireTask {
    /// The human-readable name of the task.
    pub name: String,
}

impl From<WireTask> for Task {
    fn from(wire: WireTask) -> Self {
        Self { name: wire.name }
    }
}

/// Returns the count of tasks in the provided list.
///
/// Returns `u32` to align with the WIT contract in `common/wit/tasks.wit`.
/// Panics if the count exceeds `u32::MAX` (~4.29 billion); a `Vec<Task>`
/// of that size is not realistically constructible on current hardware.
pub fn count_tasks(tasks: &[Task]) -> u32 {
    u32::try_from(tasks.len()).expect("task count exceeds u32::MAX")
}

/// Convert a vector of WIT-wire tasks to native tasks and count them.
///
/// This is the host-testable equivalent of what the wasm `Guest::count_tasks`
/// impl does after CABI lifting. Keeping the conversion here (rather than
/// inlining it in the wasm-only module) means `cargo llvm-cov` can measure
/// it from host tests instead of letting it silently slip out of coverage.
pub fn count_wire_tasks(tasks: Vec<WireTask>) -> u32 {
    let native: Vec<Task> = tasks.into_iter().map(Task::from).collect();
    count_tasks(&native)
}

#[cfg(target_arch = "wasm32")]
mod bindings;

#[cfg(target_arch = "wasm32")]
mod wasm {
    use crate::bindings::exports::common::tasks::task_collections::{Guest, Task as WitTask};

    struct Component;

    impl Guest for Component {
        fn count_tasks(tasks: Vec<WitTask>) -> u32 {
            // Wasm-only glue: lift the wit-bindgen `WitTask` into the
            // host-visible `WireTask`, then delegate to `count_wire_tasks`
            // which carries all the logic and is covered by host tests.
            let wire: Vec<crate::WireTask> = tasks
                .into_iter()
                .map(|t| crate::WireTask { name: t.name })
                .collect();
            crate::count_wire_tasks(wire)
        }
    }

    crate::bindings::export!(Component with_types_in crate::bindings);
}
