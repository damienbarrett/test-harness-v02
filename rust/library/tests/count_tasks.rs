use std::{error::Error, fs, path::PathBuf};

use serde::Deserialize;
use tasks::{count_tasks, Task};

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
    tasks: Vec<Task>,
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
        let actual = count_tasks(&case.input.tasks);
        assert_eq!(
            actual, case.expected,
            "{}: expected {}, got {}",
            case.description, case.expected, actual
        );
    }

    Ok(())
}
