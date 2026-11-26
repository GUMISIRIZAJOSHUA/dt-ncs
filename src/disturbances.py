"""Targeted disturbance generation.

Timing and severity distributions are legacy simulation assumptions,
not calibrated estimates.
"""

import math
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List


SUPPORTED_EVENT_TYPES = frozenset({
    "operator_absence",
    "robot_degradation",
})


@dataclass(frozen=True)
class DisturbanceEvent:
    event_id: int
    event_type: str
    start_time_s: float
    duration_s: float
    severity: float
    target_resource_id: int


def _validated_ids(values: Iterable[int], label: str) -> List[int]:
    ids = list(values)
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
        for value in ids
    ):
        raise ValueError(f"{label} must contain positive integer IDs")
    if len(set(ids)) != len(ids):
        raise ValueError(f"Duplicate {label}")
    return sorted(ids)


def generate_disturbance_events(
    config: Dict,
    scenario_seed: int,
    *,
    operator_ids: Iterable[int],
    robot_ids: Iterable[int],
) -> List[DisturbanceEvent]:
    count = config["disturbances_per_shift"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("disturbances_per_shift must be a non-negative integer")

    horizon = float(config["shift_duration_s"])
    if not math.isfinite(horizon) or horizon <= 0:
        raise ValueError("shift_duration_s must be finite and positive")

    operators = _validated_ids(operator_ids, "operator IDs")
    robots = _validated_ids(robot_ids, "robot IDs")

    if count == 0:
        return []

    event_types = config.get("disturbance_types")
    if not isinstance(event_types, list) or not event_types:
        raise ValueError(
            "Positive disturbance count requires an explicit "
            "non-empty disturbance_types list"
        )
    if any(not isinstance(kind, str) for kind in event_types):
        raise ValueError("disturbance_types must contain strings")
    if len(set(event_types)) != len(event_types):
        raise ValueError("Duplicate disturbance types")
    if not set(event_types) <= SUPPORTED_EVENT_TYPES:
        raise ValueError("Unsupported disturbance type")
    if "operator_absence" in event_types and not operators:
        raise ValueError("Operator absence requires operator IDs")
    if "robot_degradation" in event_types and not robots:
        raise ValueError("Robot degradation requires robot IDs")

    rng = random.Random(scenario_seed + 5000)
    events = []

    for event_id in range(1, count + 1):
        event_type = rng.choice(event_types)
        target_ids = operators if event_type == "operator_absence" else robots
        target = rng.choice(target_ids)

        events.append(
            DisturbanceEvent(
                event_id=event_id,
                event_type=event_type,
                start_time_s=rng.uniform(horizon * 0.15, horizon * 0.85),
                duration_s=rng.uniform(300.0, 900.0),
                severity=rng.uniform(0.3, 0.8),
                target_resource_id=target,
            )
        )

    events.sort(key=lambda event: (event.start_time_s, event.event_id))
    return events


def is_disturbance_active(
    event: DisturbanceEvent,
    current_time_s: float,
) -> bool:
    return (
        event.start_time_s
        <= current_time_s
        < event.start_time_s + event.duration_s
    )


def apply_active_disturbances(*args, **kwargs):
    raise RuntimeError(
        "Baseline-mutating disturbance application has been removed. "
        "Use calculate_resource_state instead."
    )