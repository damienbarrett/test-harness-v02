use std::{error::Error, fs, path::PathBuf};

use serde::Deserialize;
use task_component::{count_tasks, count_wire_tasks, Task, WireTask};

type TestResult<T = ()> = Result<T, Box<dyn Error>>;

#[derive(Debug, Deserialize)]
struct ContractSuite {
    tests: Vec<ContractCase>,
}

#[derive(Debug, Deserialize)]
struct ContractCase {
    description: String,
    input: ContractInput,
    expected: u32,
}

#[derive(Debug, Deserialize)]
struct ContractInput {
    tasks: Vec<ContractTask>,
}

#[derive(Debug, Deserialize)]
struct ContractTask {
    name: String,
}

fn common_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("common")
}

fn load_contract_suite() -> TestResult<ContractSuite> {
    let path = common_dir()
        .join("functions")
        .join("task-collections")
        .join("count-tasks.test.json");
    let contents = fs::read_to_string(path)?;
    Ok(serde_json::from_str(&contents)?)
}

#[test]
fn count_tasks_matches_contract_cases() -> TestResult {
    let suite = load_contract_suite()?;

    for case in suite.tests {
        let tasks: Vec<Task> = case
            .input
            .tasks
            .into_iter()
            .map(|task| Task { name: task.name })
            .collect();
        let actual = count_tasks(&tasks);

        assert_eq!(
            actual, case.expected,
            "{}: expected {}, got {}",
            case.description, case.expected, actual
        );
    }

    Ok(())
}

/// Exercises the host-visible mirror of the wasm `Guest::count_tasks` path.
///
/// This is the same conversion the wasm `Guest` impl performs after CABI
/// lifting; running it from a host test ensures the conversion logic is
/// measured by `cargo llvm-cov` rather than silently slipping out of
/// coverage behind the `cfg(target_arch = "wasm32")` boundary.
#[test]
fn count_wire_tasks_matches_contract_cases() -> TestResult {
    let suite = load_contract_suite()?;

    for case in suite.tests {
        let wire: Vec<WireTask> = case
            .input
            .tasks
            .into_iter()
            .map(|task| WireTask { name: task.name })
            .collect();
        let actual = count_wire_tasks(wire);

        assert_eq!(
            actual, case.expected,
            "{}: expected {}, got {}",
            case.description, case.expected, actual
        );
    }

    Ok(())
}

#[test]
fn wire_task_converts_to_native_task() {
    let wire = WireTask {
        name: "alpha".to_string(),
    };
    let task: Task = wire.into();
    assert_eq!(task.name, "alpha");
}
