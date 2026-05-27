from dataclasses import dataclass


@dataclass
class Task:
    name: str


def count_tasks(tasks: list[Task]) -> int:
    return len(tasks)
