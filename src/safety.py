import math
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class SafetyViolation:
    violation_type: str
    value: float
    threshold: float
    margin: float


@dataclass
class SafetyAssessment:
    is_safe: bool
    violations: List[SafetyViolation]
    minimum_margin: float


def calculate_collision_risk(
    human_position: float,
    robot_position: float,
    safe_distance_m: float = 0.8,
) -> float:
    distance = abs(human_position - robot_position)

    if distance >= safe_distance_m:
        return 0.0

    return 1.0 - (distance / safe_distance_m)


def calculate_safe_zone_risk(
    human_position: float,
    zone_center: float,
    zone_half_width: float = 1.5,
) -> float:
    distance = abs(human_position - zone_center)

    if distance <= zone_half_width:
        return 0.0

    excess_distance = distance - zone_half_width
    return min(1.0, excess_distance / 1.0)


def evaluate_safety(
    fatigue_level: float,
    ergonomic_risk: float,
    collision_risk: float,
    safe_zone_risk: float,
    config: Dict,
) -> SafetyAssessment:
    fatigue_threshold = float(
        config["fatigue_critical_threshold"]
    )

    ergonomic_threshold = float(
        config["ergonomic_critical_threshold"]
    )

    collision_threshold = float(
        config["collision_critical_threshold"]
    )

    safe_zone_threshold = float(
        config["safe_zone_critical_threshold"]
    )

    finite_values = {
        "fatigue_level": fatigue_level,
        "ergonomic_risk": ergonomic_risk,
        "collision_risk": collision_risk,
        "safe_zone_risk": safe_zone_risk,
        "fatigue_critical_threshold": fatigue_threshold,
        "ergonomic_critical_threshold": ergonomic_threshold,
        "collision_critical_threshold": collision_threshold,
        "safe_zone_critical_threshold": safe_zone_threshold,
    }
    for name, value in finite_values.items():
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")

    violations = []

    if fatigue_level > fatigue_threshold:
        violations.append(
            SafetyViolation(
                violation_type="fatigue",
                value=fatigue_level,
                threshold=fatigue_threshold,
                margin=fatigue_level - fatigue_threshold,
            )
        )

    if ergonomic_risk > ergonomic_threshold:
        violations.append(
            SafetyViolation(
                violation_type="ergonomic",
                value=ergonomic_risk,
                threshold=ergonomic_threshold,
                margin=ergonomic_risk - ergonomic_threshold,
            )
        )

    if collision_risk > collision_threshold:
        violations.append(
            SafetyViolation(
                violation_type="collision",
                value=collision_risk,
                threshold=collision_threshold,
                margin=collision_risk - collision_threshold,
            )
        )

    if safe_zone_risk > safe_zone_threshold:
        violations.append(
            SafetyViolation(
                violation_type="safe_zone",
                value=safe_zone_risk,
                threshold=safe_zone_threshold,
                margin=safe_zone_risk - safe_zone_threshold,
            )
        )

    if violations:
        minimum_margin = min(
            violation.margin for violation in violations
        )
        return SafetyAssessment(
            is_safe=False,
            violations=violations,
            minimum_margin=minimum_margin,
        )

    return SafetyAssessment(
        is_safe=True,
        violations=[],
        minimum_margin=0.0,
    )


def apply_hard_veto(
    safety_assessment: SafetyAssessment,
) -> bool:
    return not safety_assessment.is_safe