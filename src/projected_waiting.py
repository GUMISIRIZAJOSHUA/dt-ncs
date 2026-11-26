"""Rest readiness for deterministic projected assignment safety."""

import math
from copy import deepcopy
from src.projected_safety import assess_projected_work
from src.safety import calculate_collision_risk, calculate_safe_zone_risk


def find_projected_recovery_delay(operator, task, robot, config, max_delay_s, *, adapter, duration_s):
    if isinstance(max_delay_s, bool):
        raise ValueError("Recovery limit must not be boolean")
    upper = float(max_delay_s)
    if not math.isfinite(upper) or upper < 0:
        raise ValueError("Recovery limit must be finite and non-negative")
    collision = calculate_collision_risk(operator.operator_id, robot.robot_id)
    zone = calculate_safe_zone_risk(operator.operator_id, 2.5)

    def safe_after(delay):
        probe = deepcopy(operator)
        adapter.apply_recovery(probe, delay)
        return assess_projected_work(probe, task, duration_s, config, collision, zone, adapter).is_safe

    # Validate the recovery endpoint even when no rest is needed.
    upper_safe = safe_after(upper)
    if safe_after(0.0):
        return 0.0
    if not upper_safe:
        return None
    lower = 0.0
    for _ in range(64):
        midpoint = lower + (upper - lower) / 2.0
        if midpoint == lower or midpoint == upper:
            break
        if safe_after(midpoint):
            upper = midpoint
        else:
            lower = midpoint
    return upper
