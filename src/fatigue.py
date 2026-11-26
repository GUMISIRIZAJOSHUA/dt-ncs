import math
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class FatigueState:
    fatigue_level: float
    ergonomic_risk: float
    recovery_credit: float


@dataclass
class FatigueModelConfig:
    base_recovery_rate: float = 0.015
    noise_sigma: float = 0.10
    prior_mean: float = 0.90
    prior_strength: float = 5.0
    minimum_observations: int = 3


def apply_fatigue_update(
    operator,
    task,
    elapsed_time_s: float,
    config: Dict,
    rng: random.Random,
) -> FatigueState:
    fatigue_update_rate = float(config["fatigue_update_rate_hz"])
    noise_sigma = float(config["fatigue_noise_sigma"])

    workload = (
        task.fatigue_coefficient
        * (1.0 + task.cognitive_load)
    )

    fatigue_increment = (
        workload
        * elapsed_time_s
        * fatigue_update_rate
        / 100.0
    )

    fatigue_increment *= max(0.25, operator.base_skill)
    fatigue_increment = max(0.0, fatigue_increment)

    noise = rng.gauss(0.0, noise_sigma)
    fatigue_increment *= max(0.05, 1.0 + noise)

    operator.fatigue_level += fatigue_increment
    operator.fatigue_level = min(
        operator.fatigue_level,
        1.25,
    )

    ergonomic_risk = calculate_ergonomic_risk(
        operator.fatigue_level,
        task.cognitive_load,
    )

    return FatigueState(
        fatigue_level=operator.fatigue_level,
        ergonomic_risk=ergonomic_risk,
        recovery_credit=0.0,
    )


def apply_recovery(
    operator,
    idle_time_s: float,
    config: Dict,
) -> float:
    recovery_rate = 0.015
    recovery_amount = idle_time_s * recovery_rate

    operator.fatigue_level = max(
        0.0,
        operator.fatigue_level - recovery_amount,
    )

    return recovery_amount


def calculate_ergonomic_risk(
    fatigue_level: float,
    cognitive_load: float,
) -> float:
    if not math.isfinite(fatigue_level):
        raise ValueError("fatigue_level must be finite")
    if not math.isfinite(cognitive_load):
        raise ValueError("cognitive_load must be finite")

    risk = (
        0.65 * fatigue_level
        + 0.35 * cognitive_load
    )

    return min(max(risk, 0.0), 1.0)


def calculate_fatigue_uncertainty(
    observed_fatigue_samples: List[float],
    config: FatigueModelConfig,
) -> Tuple[float, float, float]:
    if len(observed_fatigue_samples) < config.minimum_observations:
        return (
            config.prior_mean,
            0.20,
            0.0,
        )

    observed_mean = sum(observed_fatigue_samples) / len(
        observed_fatigue_samples
    )

    variance = sum(
        (value - observed_mean) ** 2
        for value in observed_fatigue_samples
    ) / len(observed_fatigue_samples)

    observed_variance = max(variance, 0.0001)

    prior_strength = config.prior_strength
    prior_mean = config.prior_mean

    posterior_precision = (
        prior_strength
        + len(observed_fatigue_samples) / observed_variance
    )

    posterior_mean = (
        prior_strength * prior_mean
        + len(observed_fatigue_samples) * observed_mean / observed_variance
    ) / posterior_precision

    posterior_variance = 1.0 / posterior_precision

    return (
        posterior_mean,
        math.sqrt(posterior_variance),
        observed_mean,
    )


def calculate_uncertainty_inflated_fatigue(
    fatigue_level: float,
    uncertainty_sigma: float,
) -> float:
    return fatigue_level + 1.96 * uncertainty_sigma