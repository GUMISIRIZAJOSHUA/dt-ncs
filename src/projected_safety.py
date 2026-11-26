"""Safety assessment of a deterministic discrete work projection."""

import math

from src.fatigue import calculate_ergonomic_risk
from src.safety import evaluate_safety


def assess_projected_work(operator, task, duration_s, config, collision_risk, safe_zone_risk, adapter):
    global_limit = float(config["fatigue_critical_threshold"])
    operator_limit = adapter.parameters.operators[operator.operator_id].fatigue_limit
    if not math.isfinite(global_limit):
        raise ValueError("fatigue_critical_threshold must be finite")
    if not math.isfinite(operator_limit):
        raise ValueError("operator fatigue_limit must be finite")
    projection = adapter.project_work(operator, task.task_id, duration_s)
    effective_config = dict(config)
    effective_config["fatigue_critical_threshold"] = min(global_limit, operator_limit)
    maximum = projection.maximum_fatigue
    ergonomic_risk = calculate_ergonomic_risk(maximum, task.cognitive_load)
    return evaluate_safety(maximum, ergonomic_risk, collision_risk, safe_zone_risk, effective_config)
