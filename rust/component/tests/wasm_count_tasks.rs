use std::{error::Error, fs, path::PathBuf};

use serde::Deserialize;
use wasmtime::component::*;
use wasmtime::{Engine, Store};
use wasmtime_wasi::{WasiCtx, WasiCtxBuilder, WasiView, ResourceTable};

type TestResult<T = ()> = Result<T, Box<dyn Error>>;

wasmtime::component::bindgen!({
    path: "../../common/wit",
    world: "task-component",
});

struct State {
    ctx: WasiCtx,
    table: ResourceTable,
}

impl WasiView for State {
    fn ctx(&mut self) -> &mut WasiCtx {
        &mut self.ctx
    }
    fn table(&mut self) -> &mut ResourceTable {
        &mut self.table
    }
}

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

fn wasm_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("task-component.wasm")
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
fn wasm_count_tasks_matches_contract() -> TestResult {
    let engine = Engine::default();
    let component = Component::from_file(&engine, wasm_path())?;
    let mut linker = Linker::new(&engine);
    wasmtime_wasi::add_to_linker_sync(&mut linker)?;
    let state = State {
        ctx: WasiCtxBuilder::new().build(),
        table: ResourceTable::new(),
    };
    let mut store = Store::new(&engine, state);

    let instance = TaskComponent::instantiate(&mut store, &component, &linker)?;

    let suite = load_contract_suite()?;

    for case in suite.tests {
        let tasks: Vec<exports::common::tasks::task_collections::Task> = case
            .input
            .tasks
            .into_iter()
            .map(|t| exports::common::tasks::task_collections::Task { name: t.name })
            .collect();

        let result = instance
            .common_tasks_task_collections()
            .call_count_tasks(&mut store, &tasks)?;

        assert_eq!(
            result, case.expected,
            "{}: expected {}, got {}",
            case.description, case.expected, result
        );
    }

    Ok(())
}
