import math
from dataclasses import dataclass
from typing import Dict, List

from src.scheduler import ShiftResult


@dataclass
class ShiftMetrics:
    arm: str
    scenario_id: int
    completed_tasks: int
    throughput_tasks_per_hour: float
    makespan_s: float
    total_energy_kj: float
    energy_per_task_kj: float
    expected_defects: float
    defect_rate: float
    final_fatigue: float
    final_ergonomic_risk: float
    safety_violations: int
    veto_events: int
    well_being_score: float
    sustainability_score: float
    overall_score: float
    unfinished_jobs_by_type: Dict[int, int]
    dispatch_end_time_s: float
    observation_time_s: float
    termination_reason: str


def calculate_well_being_score(
    final_fatigue: float,
    final_ergonomic_risk: float,
) -> float:
    score = 1.0 - (
        0.6 * final_fatigue
        + 0.4 * final_ergonomic_risk
    )

    return min(max(score, 0.0), 1.0)


def calculate_sustainability_score(
    total_energy_kj: float,
    completed_tasks: int,
    reference_energy_per_task_kj: float = 75.0,
) -> float:
    if completed_tasks <= 0:
        return 0.0

    energy_per_task = total_energy_kj / completed_tasks

    score = 1.0 - min(
        1.0,
        energy_per_task / reference_energy_per_task_kj,
    )

    return min(max(score, 0.0), 1.0)


def calculate_overall_score(
    throughput: float,
    well_being_score: float,
    sustainability_score: float,
    defect_rate: float,
) -> float:
    normalized_throughput = min(
        1.0,
        throughput / 120.0,
    )

    quality_score = 1.0 - min(
        1.0,
        defect_rate * 20.0,
    )

    score = (
        0.35 * normalized_throughput
        + 0.25 * well_being_score
        + 0.20 * sustainability_score
        + 0.20 * quality_score
    )

    return min(max(score, 0.0), 1.0)


def calculate_shift_metrics(
    result: ShiftResult,
) -> ShiftMetrics:
    completed_tasks = result.completed_tasks

    if completed_tasks > 0:
        energy_per_task = (
            result.total_energy_kj / completed_tasks
        )

        defect_rate = (
            result.expected_defects / completed_tasks
        )

    else:
        energy_per_task = 0.0
        defect_rate = 0.0

    well_being_score = calculate_well_being_score(
        result.final_fatigue,
        result.final_ergonomic_risk,
    )

    sustainability_score = calculate_sustainability_score(
        result.total_energy_kj,
        completed_tasks,
    )

    overall_score = calculate_overall_score(
        result.throughput_tasks_per_hour,
        well_being_score,
        sustainability_score,
        defect_rate,
    )

    return ShiftMetrics(
        arm=result.arm,
        scenario_id=result.scenario_id,
        completed_tasks=completed_tasks,
        throughput_tasks_per_hour=result.throughput_tasks_per_hour,
        makespan_s=result.makespan_s,
        dispatch_end_time_s=result.dispatch_end_time_s,
        observation_time_s=result.observation_time_s,
        termination_reason=result.termination_reason,
        total_energy_kj=result.total_energy_kj,
        energy_per_task_kj=energy_per_task,
        expected_defects=result.expected_defects,
        defect_rate=defect_rate,
        final_fatigue=result.final_fatigue,
        final_ergonomic_risk=result.final_ergonomic_risk,
        safety_violations=result.safety_violations,
        veto_events=result.veto_events,
        well_being_score=well_being_score,
        sustainability_score=sustainability_score,
        overall_score=overall_score,
        unfinished_jobs_by_type=dict(result.unfinished_jobs_by_type),
    )


def calculate_arm_summary(
    metrics: List[ShiftMetrics],
) -> Dict[str, float]:
    if not metrics:
        raise ValueError("No metrics provided")

    arms = sorted(set(metric.arm for metric in metrics))

    summary = {}

    for arm in arms:
        arm_metrics = [
            metric for metric in metrics if metric.arm == arm
        ]

        summary[arm] = {
            "completed_tasks_mean": calculate_mean(
                [metric.completed_tasks for metric in arm_metrics]
            ),
            "throughput_mean": calculate_mean(
                [
                    metric.throughput_tasks_per_hour
                    for metric in arm_metrics
                ]
            ),
            "energy_mean": calculate_mean(
                [metric.total_energy_kj for metric in arm_metrics]
            ),
            "energy_per_task_mean": calculate_mean(
                [
                    metric.energy_per_task_kj
                    for metric in arm_metrics
                ]
            ),
            "defect_rate_mean": calculate_mean(
                [metric.defect_rate for metric in arm_metrics]
            ),
            "fatigue_mean": calculate_mean(
                [metric.final_fatigue for metric in arm_metrics]
            ),
            "ergonomic_risk_mean": calculate_mean(
                [
                    metric.final_ergonomic_risk
                    for metric in arm_metrics
                ]
            ),
            "well_being_mean": calculate_mean(
                [
                    metric.well_being_score
                    for metric in arm_metrics
                ]
            ),
            "sustainability_mean": calculate_mean(
                [
                    metric.sustainability_score
                    for metric in arm_metrics
                ]
            ),
            "overall_score_mean": calculate_mean(
                [
                    metric.overall_score
                    for metric in arm_metrics
                ]
            ),
            "safety_violations_mean": calculate_mean(
                [
                    metric.safety_violations
                    for metric in arm_metrics
                ]
            ),
            "veto_events_mean": calculate_mean(
                [metric.veto_events for metric in arm_metrics]
            ),
        }

    return summary


def calculate_mean(values: List[float]) -> float:
    if not values:
        return 0.0

    return sum(values) / len(values)


def calculate_standard_deviation(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0

    mean_value = calculate_mean(values)

    variance = sum(
        (value - mean_value) ** 2 for value in values
    ) / (len(values) - 1)

    return math.sqrt(variance)