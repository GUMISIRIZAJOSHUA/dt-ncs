"""Temporary resource states derived from baselines and disturbance events."""

import math
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable

from src.disturbances import is_disturbance_active


@dataclass(frozen=True)
class ResourceState:
    unavailable_operator_ids: FrozenSet[int]
    effective_robot_speeds: Dict[int, float]


def calculate_resource_state(
    operators: Iterable,
    robots: Iterable,
    events: Iterable,
    current_time_s: float,
) -> ResourceState:
    operators = list(operators)
    robots = list(robots)

    operator_ids = [operator.operator_id for operator in operators]
    robot_ids = [robot.robot_id for robot in robots]

    if len(set(operator_ids)) != len(operator_ids):
        raise ValueError("Duplicate operator IDs")
    if len(set(robot_ids)) != len(robot_ids):
        raise ValueError("Duplicate robot IDs")
    if not math.isfinite(current_time_s) or current_time_s < 0:
        raise ValueError("Time must be finite and non-negative")

    speeds = {}
    for robot in robots:
        if not math.isfinite(robot.base_speed) or robot.base_speed <= 0:
            raise ValueError("Robot baseline speed must be finite and positive")
        speeds[robot.robot_id] = robot.base_speed

    unavailable = set()
    reductions = {}

    for event in events:
        if event.event_type not in {"operator_absence", "robot_degradation"}:
            raise ValueError(
                f"Unsupported disturbance type: {event.event_type}"
            )

        target = getattr(event, "target_resource_id", None)
        if isinstance(target, bool) or not isinstance(target, int):
            raise ValueError("Disturbance requires an integer target_resource_id")

        valid_ids = (
            operator_ids
            if event.event_type == "operator_absence"
            else robot_ids
        )
        if target not in valid_ids:
            raise ValueError("Disturbance targets an unknown resource")

        if (
            not math.isfinite(event.start_time_s)
            or event.start_time_s < 0
            or not math.isfinite(event.duration_s)
            or event.duration_s <= 0
            or not math.isfinite(event.severity)
            or not 0 <= event.severity <= 1
        ):
            raise ValueError("Invalid disturbance timing or severity")

        if not is_disturbance_active(event, current_time_s):
            continue

        if event.event_type == "operator_absence":
            unavailable.add(target)
        else:
            reductions[target] = max(
                reductions.get(target, 0.0),
                event.severity * 0.20,
            )

    for robot_id, reduction in reductions.items():
        baseline = speeds[robot_id]
        speeds[robot_id] = min(
            baseline,
            max(0.35, baseline - reduction),
        )

    return ResourceState(
        unavailable_operator_ids=frozenset(unavailable),
        effective_robot_speeds=speeds,
    )