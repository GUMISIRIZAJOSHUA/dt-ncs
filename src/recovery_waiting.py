"""Recovery readiness under the existing monotone fatigue/safety model."""

import math
from copy import deepcopy

from src.fatigue import apply_recovery, calculate_ergonomic_risk
from src.safety import (
    calculate_collision_risk,
    calculate_safe_zone_risk,
    evaluate_safety,
)


def find_safe_recovery_delay(
    operator,
    task,
    robot,
    config,
    max_delay_s,
):
    """Return a safe delay within the limit, or None if none exists.

    Assumes availability, geometry, task, and robot state are fixed
    throughout the interval. The caller must bound the interval at
    relevant disturbance boundaries and the latest feasible start.
    """
    if not math.isfinite(max_delay_s) or max_delay_s < 0:
        raise ValueError("Recovery limit must be finite and non-negative")
    if (
        not math.isfinite(operator.fatigue_level)
        or operator.fatigue_level < 0
    ):
        raise ValueError("Fatigue must be finite and non-negative")

    collision_risk = calculate_collision_risk(
        operator.operator_id, robot.robot_id
    )
    safe_zone_risk = calculate_safe_zone_risk(
        operator.operator_id, 2.5
    )

    def safe_after(delay_s):
        probe = deepcopy(operator)
        if delay_s > 0:
            apply_recovery(probe, delay_s, config)
        ergonomic_risk = calculate_ergonomic_risk(
            probe.fatigue_level, task.cognitive_load
        )
        return evaluate_safety(
            probe.fatigue_level,
            ergonomic_risk,
            collision_risk,
            safe_zone_risk,
            config,
        ).is_safe

    if safe_after(0.0):
        return 0.0
    if max_delay_s == 0 or not safe_after(max_delay_s):
        return None

    # With the current model, safety improves monotonically during rest.
    # Keep the upper endpoint safe throughout the search.
    lower = 0.0
    upper = max_delay_s
    for _ in range(60):
        midpoint = lower + (upper - lower) / 2.0
        if midpoint == lower or midpoint == upper:
            break
        if safe_after(midpoint):
            upper = midpoint
        else:
            lower = midpoint

    return upper