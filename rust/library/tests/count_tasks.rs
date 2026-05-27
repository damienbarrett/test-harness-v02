use std::{error::Error, fs, path::PathBuf};

use serde::Deserialize;
use serde_json::Value;
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

fn read_json(path: PathBuf) -> TestResult<Value> {
    let contents = fs::read_to_string(path)?;
    Ok(serde_json::from_str(&contents)?)
}

fn load_contract_suite() -> TestResult<(ContractSuite, Value, Value, Value)> {
    let common_dir = common_dir();
    let test_data = read_json(
        common_dir
            .join("functions")
            .join("task-collections")
            .join("count-tasks.test.json"),
    )?;
    let function_schema = read_json(common_dir.join("functions").join("task-collections").join("count-tasks.schema.json"))?;
    let task_schema = read_json(common_dir.join("entities").join("task-schema.json"))?;
    let suite = serde_json::from_value(test_data.clone())?;

    Ok((suite, test_data, function_schema, task_schema))
}

fn load_params_schema(function_schema: &Value, task_schema: Value) -> Value {
    let mut params_schema = function_schema["parameters"].clone();
    params_schema["properties"]["tasks"]["items"] = task_schema;
    params_schema
}

fn assert_object_schema(
    instance: &Value,
    schema: &Value,
    description: &str,
    context: &str,
) -> TestResult {
    let object = instance
        .as_object()
        .ok_or_else(|| format!("{description}: {context} should be an object"))?;
    let schema_properties = schema["properties"]
        .as_object()
        .ok_or_else(|| format!("{description}: {context} schema should define properties"))?;
    let required = schema["required"]
        .as_array()
        .ok_or_else(|| format!("{description}: {context} schema should define required fields"))?;
    let additional_properties = schema["additionalProperties"].as_bool().ok_or_else(|| {
        format!("{description}: {context} schema should define additionalProperties")
    })?;

    for key in required {
        let property_name = key
            .as_str()
            .ok_or_else(|| format!("{description}: required field names must be strings"))?;

        if !object.contains_key(property_name) {
            return Err(format!("{description}: missing required field `{property_name}`").into());
        }
    }

    if !additional_properties {
        for key in object.keys() {
            if !schema_properties.contains_key(key) {
                return Err(
                    format!("{description}: unexpected field `{key}` for {context}").into(),
                );
            }
        }
    }

    Ok(())
}

fn validate_task(task: &Value, task_schema: &Value, description: &str) -> TestResult {
    assert_object_schema(task, task_schema, description, "task")?;

    let name_schema = &task_schema["properties"]["name"];
    if name_schema["type"] != "string" {
        return Err(format!("{description}: task schema must declare `name` as a string").into());
    }

    if !task["name"].is_string() {
        return Err(format!("{description}: task name must be a string").into());
    }

    Ok(())
}

fn validate_input(input: &Value, params_schema: &Value, description: &str) -> TestResult {
    assert_object_schema(input, params_schema, description, "input")?;

    let tasks_schema = &params_schema["properties"]["tasks"];
    if tasks_schema["type"] != "array" {
        return Err(format!("{description}: tasks schema must declare an array").into());
    }

    let tasks = input["tasks"]
        .as_array()
        .ok_or_else(|| format!("{description}: tasks must be an array"))?;
    let task_schema = &tasks_schema["items"];

    for task in tasks {
        validate_task(task, task_schema, description)?;
    }

    Ok(())
}

fn validate_output(output: &Value, returns_schema: &Value, description: &str) -> TestResult {
    if returns_schema["type"] != "integer" {
        return Err(format!("{description}: return schema must declare an integer").into());
    }

    if !(output.is_i64() || output.is_u64()) {
        return Err(format!("{description}: expected output must be an integer").into());
    }

    Ok(())
}

#[test]
fn count_tasks_matches_contract_cases() -> TestResult {
    let (suite, _, _, _) = load_contract_suite()?;

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

#[test]
fn contract_test_data_conforms_to_schema() -> TestResult {
    let (_, test_data, function_schema, task_schema) = load_contract_suite()?;
    let params_schema = load_params_schema(&function_schema, task_schema);
    let output_schema = &function_schema["returns"];

    for case in test_data["tests"]
        .as_array()
        .expect("tests should be an array")
    {
        let description = case["description"]
            .as_str()
            .expect("description should be a string");
        validate_input(&case["input"], &params_schema, description)?;
        validate_output(&case["expected"], output_schema, description)?;
    }

    Ok(())
}
