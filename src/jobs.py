from dataclasses import dataclass
from typing import Iterable, List, Mapping


@dataclass(frozen=True)
class JobInstance:
    job_id: int
    task_type_id: int


def build_backlog(
    task_type_ids: Iterable[int],
    quantities: Mapping[int, int],
) -> List[JobInstance]:
    type_ids = list(task_type_ids)

    if any(type(value) is not int or value <= 0 for value in type_ids):
        raise ValueError("Task-type IDs must be positive integers")

    if len(type_ids) != len(set(type_ids)):
        raise ValueError("Task-type IDs must be unique")

    if any(type(key) is not int for key in quantities):
        raise ValueError("Quantity keys must be integer task-type IDs")

    if set(quantities) != set(type_ids):
        raise ValueError(
            "Provide an explicit quantity for every task type, "
            "with no unknown task types"
        )

    if any(
        type(quantity) is not int or quantity < 0
        for quantity in quantities.values()
    ):
        raise ValueError("Job quantities must be non-negative integers")

    jobs = []

    for task_type_id in sorted(type_ids):
        for _ in range(quantities[task_type_id]):
            jobs.append(
                JobInstance(
                    job_id=len(jobs) + 1,
                    task_type_id=task_type_id,
                )
            )

    return jobs