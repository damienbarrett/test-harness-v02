# common/

Shared contract definitions. This directory has no awareness of the
implementations that depend on it.

## Structure

```
common/
  wit/                  WIT interface definitions
  entities/             JSON Schema for domain types
  functions/            Function schemas and test fixtures
```

## Naming convention

Test fixtures follow a convention that mirrors the WIT hierarchy:

```
functions/{interface}/{function}.test.json
functions/{interface}/{function}.schema.json
```

- **Directory name** = WIT interface name (kebab-case)
- **File stem** = WIT function name (kebab-case)

### Example

Given this WIT:

```wit
interface task-collections {
    count-tasks: func(tasks: list<task>) -> u32;
}
```

The corresponding files are:

```
functions/task-collections/count-tasks.test.json
functions/task-collections/count-tasks.schema.json
```

## Test fixture format

```json
{
  "function": "count-tasks",
  "tests": [
    {
      "description": "counts a list of tasks",
      "input": { "tasks": [{ "name": "Task 1" }] },
      "expected": 1
    }
  ]
}
```

- `function` names the function under test (kebab-case).
- Each test case has `description`, `input` (keyed by parameter name),
  and `expected` (the return value).
- No implementation-specific metadata belongs here.
