import math
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class DescriptiveStatistics:
    mean: float
    standard_deviation: float
    standard_error: float
    ci_lower: float
    ci_upper: float
    n: int


@dataclass
class PairedComparison:
    arm_a: str
    arm_b: str
    metric: str
    mean_difference: float
    standard_deviation_difference: float
    standard_error_difference: float
    ci_lower: float
    ci_upper: float
    t_statistic: float
    degrees_of_freedom: int
    p_value: float
    cohens_d: float


def calculate_descriptive_statistics(values, confidence_level=0.95):
    if not values:
        raise ValueError("No values provided")

    n = len(values)
    mean_value = sum(values) / n

    if n < 2:
        standard_deviation = 0.0
    else:
        variance = sum(
            (value - mean_value) ** 2 for value in values
        ) / (n - 1)
        standard_deviation = math.sqrt(variance)

    standard_error = standard_deviation / math.sqrt(n)
    t_critical = calculate_t_critical(n - 1, confidence_level)
    margin = t_critical * standard_error

    return DescriptiveStatistics(
        mean=mean_value,
        standard_deviation=standard_deviation,
        standard_error=standard_error,
        ci_lower=mean_value - margin,
        ci_upper=mean_value + margin,
        n=n,
    )


def calculate_t_critical(degrees_of_freedom, confidence_level):
    from scipy.stats import t as t_distribution

    if not 0.0 < confidence_level < 1.0:
        raise ValueError("Confidence level must be between zero and one")

    if degrees_of_freedom <= 0:
        return 0.0

    return float(
        t_distribution.ppf(
            0.5 + confidence_level / 2.0,
            degrees_of_freedom,
        )
    )


def calculate_paired_comparison(
    arm_a, arm_b, metric, values_a, values_b, confidence_level=0.95
):
    if len(values_a) != len(values_b):
        raise ValueError("Paired samples must have equal length")

    if len(values_a) < 2:
        raise ValueError("At least two paired observations required")

    differences = [
        value_a - value_b
        for value_a, value_b in zip(values_a, values_b)
    ]

    n = len(differences)
    mean_difference = sum(differences) / n

    variance = sum(
        (difference - mean_difference) ** 2 for difference in differences
    ) / (n - 1)

    standard_deviation_difference = math.sqrt(variance)
    standard_error_difference = standard_deviation_difference / math.sqrt(n)

    if standard_error_difference == 0:
        if mean_difference == 0:
            t_statistic = 0.0
        else:
            t_statistic = math.copysign(float("inf"), mean_difference)
    else:
        t_statistic = mean_difference / standard_error_difference

    degrees_of_freedom = n - 1
    p_value = calculate_two_sided_p_value(
        abs(t_statistic), degrees_of_freedom
    )

    t_critical = calculate_t_critical(
        degrees_of_freedom, confidence_level
    )
    margin = t_critical * standard_error_difference

    if standard_deviation_difference == 0:
        if mean_difference == 0:
            cohens_d = 0.0
        else:
            cohens_d = math.copysign(float("inf"), mean_difference)
    else:
        cohens_d = mean_difference / standard_deviation_difference

    return PairedComparison(
        arm_a=arm_a,
        arm_b=arm_b,
        metric=metric,
        mean_difference=mean_difference,
        standard_deviation_difference=standard_deviation_difference,
        standard_error_difference=standard_error_difference,
        ci_lower=mean_difference - margin,
        ci_upper=mean_difference + margin,
        t_statistic=t_statistic,
        degrees_of_freedom=degrees_of_freedom,
        p_value=p_value,
        cohens_d=cohens_d,
    )


def calculate_two_sided_p_value(absolute_t_statistic, degrees_of_freedom):
    from scipy.stats import t as t_distribution

    if degrees_of_freedom <= 0:
        return 1.0

    if absolute_t_statistic == float("inf"):
        return 0.0

    return 2.0 * t_distribution.sf(
        absolute_t_statistic,
        degrees_of_freedom,
    )

def summarize_by_arm(results):
    summary = {}

    for arm, values in results.items():
        summary[arm] = calculate_descriptive_statistics(values)

    return summary