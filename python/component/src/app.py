from typing import TypeAlias

from wit_world import exports
from wit_world.exports.task_collections import Task

TaskEntity: TypeAlias = Task
TaskEntities: TypeAlias = list[TaskEntity]


class TaskCollections(exports.TaskCollections):
    def count_tasks(self, tasks: TaskEntities) -> int:
        return len(tasks)
