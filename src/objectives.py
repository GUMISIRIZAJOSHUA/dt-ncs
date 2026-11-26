import math
from dataclasses import dataclass
from typing import Dict


@dataclass
class ObjectiveValues:
    productivity: float
    quality: float
    wellbeing: float
    sustainability: float
    collaboration: float


@dataclass
class ObjectiveResult:
    objective_name: str
    score: float
    component_scores: ObjectiveValues
    penalty: float


def normalize(value: float, minimum: float, maximum: float) -> float:
    if maximum <= minimum:
        return 0.0

    normalized = (value - minimum) / (maximum - minimum)
    return min(max(normalized, 0.0), 1.0)


def calculate_weighted_sum(
    values: ObjectiveValues,
    weights: Dict[str, float],
) -> ObjectiveResult:
    score = (
        weights["productivity"] * values.productivity
        + weights["quality"] * values.quality
        + weights["wellbeing"] * values.wellbeing
        + weights["sustainability"] * values.sustainability
        + weights["collaboration"] * values.collaboration
    )

    return ObjectiveResult(
        objective_name="weighted_sum",
        score=score,
        component_scores=values,
        penalty=0.0,
    )


def calculate_multiplicative_synergy(
    values: ObjectiveValues,
    weights: Dict[str, float],
) -> ObjectiveResult:
    epsilon = 1e-6

    weighted_product = (
        math.pow(max(values.productivity, epsilon), weights["productivity"])
        * math.pow(max(values.quality, epsilon), weights["quality"])
        * math.pow(max(values.wellbeing, epsilon), weights["wellbeing"])
        * math.pow(
            max(values.sustainability, epsilon),
            weights["sustainability"],
        )
        * math.pow(
            max(values.collaboration, epsilon),
            weights["collaboration"],
        )
    )

    score = math.pow(weighted_product, 1.0)

    return ObjectiveResult(
        objective_name="multiplicative_synergy",
        score=score,
        component_scores=values,
        penalty=0.0,
    )


def calculate_harrington_penalty(
    values: ObjectiveValues,
    soft_thresholds: Dict[str, float],
    k: float = 5.0,
    p: float = 2.0,
) -> float:
    penalty = 0.0

    metric_values = {
        "productivity": values.productivity,
        "quality": values.quality,
        "wellbeing": values.wellbeing,
        "sustainability": values.sustainability,
        "collaboration": values.collaboration,
    }

    for metric, value in metric_values.items():
        threshold = soft_thresholds[metric]

        if value < threshold:
            shortfall = threshold - value
            penalty += k * math.pow(shortfall, p)

    return penalty


def calculate_synergy_with_harrington(
    values: ObjectiveValues,
    weights: Dict[str, float],
    soft_thresholds: Dict[str, float],
    k: float = 5.0,
    p: float = 2.0,
) -> ObjectiveResult:
    synergy = calculate_multiplicative_synergy(
        values,
        weights,
    )

    penalty = calculate_harrington_penalty(
        values,
        soft_thresholds,
        k,
        p,
    )

    final_score = synergy.score - penalty

    return ObjectiveResult(
        objective_name="multiplicative_synergy_harrington",
        score=final_score,
        component_scores=values,
        penalty=penalty,
    )


def calculate_productivity_first(
    values: ObjectiveValues,
    weights: Dict[str, float],
) -> ObjectiveResult:
    return ObjectiveResult(
        objective_name="productivity",
        score=values.productivity,
        component_scores=values,
        penalty=0.0,
    )