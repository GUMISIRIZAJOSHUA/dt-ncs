import random
import math
from dataclasses import dataclass
from typing import Dict, List

from src.scenario import Scenario, Task, Operator, Robot
from src.fatigue import apply_fatigue_update, apply_recovery, calculate_ergonomic_risk
from src.safety import calculate_collision_risk, calculate_safe_zone_risk, evaluate_safety
from src.objectives import (
    ObjectiveValues,
    calculate_productivity_first,
    calculate_weighted_sum,
    calculate_multiplicative_synergy,
    calculate_synergy_with_harrington,
)
from src.disturbances import apply_active_disturbances
from src.resource_state import calculate_resource_state
from src.recovery_waiting import find_safe_recovery_delay
from src.projected_safety import assess_projected_work
from src.projected_waiting import find_projected_recovery_delay
from functools import partial


class NoAssignmentAvailable(RuntimeError):
    """Expected selection failure, distinct from programming errors."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


@dataclass
class Assignment:
    job_id: int
    task_id: int
    operator_id: int
    robot_id: int
    start_time_s: float
    completion_time_s: float
    duration_s: float
    energy_kj: float
    defect_probability: float
    objective_score: float
    vetoed: bool
    safety_violation: bool


@dataclass
class ShiftResult:
    arm: str
    scenario_id: int
    completed_tasks: int
    makespan_s: float
    throughput_tasks_per_hour: float
    total_energy_kj: float
    expected_defects: float
    final_fatigue: float
    final_ergonomic_risk: float
    safety_violations: int
    veto_events: int
    common_objective: float
    wellbeing: float
    productivity: float
    assignments: List[Assignment]
    unfinished_jobs_by_type: Dict[int, int]
    dispatch_end_time_s: float
    observation_time_s: float
    termination_reason: str

def get_objective_values(task, operator, robot, current_time_s, scenario, config):
    remaining_time = max(1.0, scenario.shift_duration_s - current_time_s)
    resource_state = calculate_resource_state(
        scenario.operators, scenario.robots,
        scenario.disturbance_events, current_time_s,
    )
    effective_speed = resource_state.effective_robot_speeds[robot.robot_id]
    duration = max(
        task.manual_time_s / operator.base_skill,
        task.robot_time_s / effective_speed,
    )

    return ObjectiveValues(
        productivity=1.0 - min(1.0, duration / remaining_time),
        quality=1.0 - task.defect_risk,
        wellbeing=1.0 - min(1.0, operator.fatigue_level),
        sustainability=1.0 - min(1.0, task.robot_energy_kj / robot.energy_capacity_kj),
        collaboration=1.0 - task.cognitive_load,
    )


def get_score(
    arm, task, operator, robot, current_time_s,
    scenario, config, arm_config=None,
):
    if arm_config is None:
        raise ValueError(f"Missing arm configuration for {arm}")

    objective = arm_config["objective"]

    values = get_objective_values(
        task, operator, robot, current_time_s, scenario, config
    )

    if objective == "productivity":
        return calculate_productivity_first(
            values, config["weights"]
        ).score

    if objective == "weighted_sum":
        return calculate_weighted_sum(
            values, config["weights"]
        ).score

    if objective == "multiplicative_synergy":
        return calculate_multiplicative_synergy(
            values, config["weights"]
        ).score

    if objective == "multiplicative_synergy_harrington":
        return calculate_synergy_with_harrington(
            values,
            config["weights"],
            config["harrington_soft_thresholds"],
            k=config["harrington_k"],
            p=config["harrington_p"],
        ).score

    raise ValueError(
        f"Unknown objective for {arm}: {objective}"
    )


def is_better_b3_candidate(
    candidate_wellbeing,
    candidate_synergy,
    best_wellbeing,
    best_synergy,
):
    if candidate_wellbeing > best_wellbeing:
        return True

    if candidate_wellbeing < best_wellbeing:
        return False

    return candidate_synergy > best_synergy


def select_assignment(arm, scenario, current_time_s, config, rng, arm_config=None, candidate_trace=None):
    if arm_config is None:
        raise ValueError(f"Missing arm configuration for {arm}")
    if not isinstance(arm_config.get("veto"), bool):
        raise ValueError(f"Missing or invalid veto setting for {arm}")
    if "objective" not in arm_config:
        raise ValueError(f"Missing objective setting for {arm}")

    resource_state = calculate_resource_state(
        scenario.operators, scenario.robots,
        scenario.disturbance_events, current_time_s,
    )
    if not any(
        job.job_id not in scenario.completed_job_ids
        for job in scenario.jobs
    ):
        raise NoAssignmentAvailable("backlog_exhausted")

    if not scenario.robots or not any(
        operator.operator_id not in resource_state.unavailable_operator_ids
        for operator in scenario.operators
    ):
        raise NoAssignmentAvailable("no_available_resources")

    fitting_candidate_count = 0
    best_safe = None
    best_safe_score = -1e12

    best_unsafe = None
    best_unsafe_score = -1e12

    unsafe_candidate_count = 0

    for job in scenario.jobs:
        if job.job_id in scenario.completed_job_ids:
            continue
        task = get_task(scenario, job.task_type_id)
        for operator in scenario.operators:
            if operator.operator_id in resource_state.unavailable_operator_ids:
                continue
            for robot in scenario.robots:
                effective_speed = resource_state.effective_robot_speeds[
                    robot.robot_id
                ]
                duration = max(
                    task.manual_time_s / operator.base_skill,
                    task.robot_time_s / effective_speed,
                )
                if current_time_s + duration > scenario.shift_duration_s:
                    continue
                fitting_candidate_count += 1
                collision_risk = calculate_collision_risk(
                    operator.operator_id, robot.robot_id
                )
                safe_zone_risk = calculate_safe_zone_risk(
                    operator.operator_id, 2.5
                )
                ergonomic_risk = calculate_ergonomic_risk(
                    operator.fatigue_level, task.cognitive_load
                )

                fatigue_adapter = getattr(scenario, "_fatigue_adapter", None)
                if fatigue_adapter is None:
                    safety = evaluate_safety(
                        operator.fatigue_level,
                        ergonomic_risk,
                        collision_risk,
                        safe_zone_risk,
                        config,
                    )
                else:
                    safety = assess_projected_work(
                        operator, task, duration, config,
                        collision_risk, safe_zone_risk,
                        fatigue_adapter,
                    )

                trace_values = get_objective_values(
                    task,
                    operator,
                    robot,
                    current_time_s,
                    scenario,
                    config,
                )
                candidate_wellbeing = trace_values.wellbeing
                candidate_synergy = calculate_multiplicative_synergy(
                    trace_values,
                    config["weights"],
                ).score

                score = get_score(
                    arm,
                    task,
                    operator,
                    robot,
                    current_time_s,
                    scenario,
                    config,
                    arm_config=arm_config,
                )

                candidate = Assignment(
                    job_id=job.job_id,
                    task_id=task.task_id,
                    operator_id=operator.operator_id,
                    robot_id=robot.robot_id,
                    start_time_s=current_time_s,
                    completion_time_s=current_time_s + duration,
                    duration_s=duration,
                    energy_kj=task.robot_energy_kj,
                    defect_probability=task.defect_risk,
                    objective_score=score,
                    vetoed=False,
                    safety_violation=not safety.is_safe,
                )

                if safety.is_safe:
                    if candidate_trace is not None:
                        candidate_trace.append(
                            {
                                "current_time_s": current_time_s,
                                "job_id": job.job_id,
                                "task_id": task.task_id,
                                "operator_id": operator.operator_id,
                                "robot_id": robot.robot_id,
                                "wellbeing": candidate_wellbeing,
                                "synergy_score": candidate_synergy,
                                "safe": True,
                            }
                        )
                    if best_safe is None or score > best_safe_score:
                        best_safe = candidate
                        best_safe_score = score

                else:
                    unsafe_candidate_count += 1

                    if best_unsafe is None or score > best_unsafe_score:
                        best_unsafe = candidate
                        best_unsafe_score = score

    veto_events = 0

    if fitting_candidate_count == 0:
        raise NoAssignmentAvailable("no_fitting_assignment")

    if arm_config["veto"]:
        if best_safe is None:
            raise NoAssignmentAvailable("no_safe_assignment")

        veto_events = unsafe_candidate_count

        return best_safe, veto_events

    if best_safe is not None and best_unsafe is not None:
        if best_unsafe_score > best_safe_score:
            return best_unsafe, veto_events

        return best_safe, veto_events

    if best_unsafe is not None:
        return best_unsafe, veto_events

    if best_safe is not None:
        return best_safe, veto_events

    raise NoAssignmentAvailable("no_feasible_assignment")
def get_task(scenario, task_id):
    for task in scenario.tasks:
        if task.task_id == task_id:
            return task

    raise ValueError(f"Task {task_id} not found")


def execute_assignment(assignment, scenario, config, rng):
    if assignment.job_id in scenario.completed_job_ids:
        raise ValueError('Job already completed')
    matches = [j for j in scenario.jobs if j.job_id == assignment.job_id]
    if len(matches) != 1 or matches[0].task_type_id != assignment.task_id:
        raise ValueError('Assignment does not match a unique backlog job')
    task = get_task(scenario, assignment.task_id)
    operator_matches = [
        item for item in scenario.operators
        if item.operator_id == assignment.operator_id
    ]
    robot_matches = [
        item for item in scenario.robots
        if item.robot_id == assignment.robot_id
    ]
    if len(operator_matches) != 1:
        raise ValueError("Assignment must identify exactly one operator")
    if len(robot_matches) != 1:
        raise ValueError("Assignment must identify exactly one robot")
    operator = operator_matches[0]
    robot = robot_matches[0]

    fatigue_adapter = getattr(scenario, "_fatigue_adapter", None)
    if fatigue_adapter is None:
        apply_fatigue_update(
            operator, task, assignment.duration_s, config, rng
        )
    else:
        fatigue_adapter.apply_work(
            operator, task.task_id, assignment.duration_s
        )

    robot.energy_used_kj += task.robot_energy_kj
    operator.completed_tasks.append(task.task_id)
    robot.completed_tasks.append(task.task_id)
    scenario.completed_task_ids.add(task.task_id)
    scenario.completed_job_ids.add(assignment.job_id)


def apply_idle_recovery_interval(
    scenario,
    start_time_s,
    end_time_s,
    config,
    working_operator_id=None,
):
    """Recover present, non-working operators; freeze fatigue during absence."""
    if (
        not math.isfinite(start_time_s)
        or not math.isfinite(end_time_s)
        or start_time_s < 0
        or end_time_s < start_time_s
        or end_time_s > scenario.shift_duration_s
    ):
        raise ValueError("Invalid recovery interval")

    # Validate events even when the requested interval has zero duration.
    calculate_resource_state(
        scenario.operators,
        scenario.robots,
        scenario.disturbance_events,
        start_time_s,
    )

    boundaries = {start_time_s, end_time_s}
    for event in scenario.disturbance_events:
        if event.event_type != "operator_absence":
            continue
        for boundary in (
            event.start_time_s,
            event.start_time_s + event.duration_s,
        ):
            if start_time_s < boundary < end_time_s:
                boundaries.add(boundary)

    boundaries = sorted(boundaries)
    for left, right in zip(boundaries, boundaries[1:]):
        state = calculate_resource_state(
            scenario.operators,
            scenario.robots,
            scenario.disturbance_events,
            left,
        )
        for operator in scenario.operators:
            if (
                operator.operator_id != working_operator_id
                and operator.operator_id
                not in state.unavailable_operator_ids
            ):
                fatigue_adapter = getattr(scenario, "_fatigue_adapter", None)
                if fatigue_adapter is None:
                    apply_recovery(operator, right - left, config)
                else:
                    fatigue_adapter.apply_recovery(operator, right - left)


def next_disturbance_boundary(scenario, current_time_s):
    boundaries = [
        boundary
        for event in scenario.disturbance_events
        for boundary in (
            event.start_time_s,
            event.start_time_s + event.duration_s,
        )
        if current_time_s < boundary < scenario.shift_duration_s
    ]
    return min(boundaries) if boundaries else None


def next_recovery_time(scenario, current_time_s, config):
    """Find a safe recovery reassessment within the current event interval."""
    state = calculate_resource_state(
        scenario.operators,
        scenario.robots,
        scenario.disturbance_events,
        current_time_s,
    )
    boundary = next_disturbance_boundary(scenario, current_time_s)
    interval_end = (
        scenario.shift_duration_s if boundary is None else boundary
    )
    times = []
    remaining_types = {
        job.task_type_id
        for job in scenario.jobs
        if job.job_id not in scenario.completed_job_ids
    }

    for task_id in sorted(remaining_types):
        task = get_task(scenario, task_id)
        for operator in scenario.operators:
            if operator.operator_id in state.unavailable_operator_ids:
                continue
            for robot in scenario.robots:
                duration = max(
                    task.manual_time_s / operator.base_skill,
                    task.robot_time_s
                    / state.effective_robot_speeds[robot.robot_id],
                )
                latest_start = min(
                    interval_end,
                    scenario.shift_duration_s - duration,
                )
                max_delay = latest_start - current_time_s
                if max_delay <= 0:
                    continue

                fatigue_adapter = getattr(scenario, "_fatigue_adapter", None)
                if fatigue_adapter is None:
                    recovery_finder = find_safe_recovery_delay
                else:
                    recovery_finder = partial(
                        find_projected_recovery_delay,
                        adapter=fatigue_adapter,
                        duration_s=duration,
                    )
                delay = recovery_finder(
                    operator, task, robot, config, max_delay
                )
                if delay is None or delay <= 0:
                    continue

                candidate = current_time_s + delay

                # Absolute-time rounding must not produce an unsafe retry
                # or a zero-time loop. Fall back to the known upper bound.
                attempts = []
                for _ in range(4):
                    if candidate > current_time_s:
                        attempts.append(candidate)
                    candidate = math.nextafter(candidate, math.inf)
                attempts.append(latest_start)

                for candidate in attempts:
                    if not current_time_s < candidate <= latest_start:
                        continue
                    if candidate + duration > scenario.shift_duration_s:
                        continue
                    if recovery_finder(
                        operator,
                        task,
                        robot,
                        config,
                        candidate - current_time_s,
                    ) is not None:
                        times.append(candidate)
                        break

    return min(times) if times else None


def run_shift(arm, scenario, config, search_seed, arm_config=None, candidate_trace=None):
    rng = random.Random(search_seed)
    current_time_s = 0.0
    assignments = []
    safety_violations = 0
    veto_events = 0
    common_objective = 0.0
    termination_reason = "horizon_reached"


    while current_time_s < scenario.shift_duration_s:
        # Resource state is derived during selection; baselines are not mutated.


        try:
            assignment, new_vetoes = select_assignment(
                arm,
                scenario,
                current_time_s,
                config,
                rng,
                arm_config=arm_config,
                candidate_trace=candidate_trace,
            )
        except NoAssignmentAvailable as failure:
            if failure.reason not in {
                "no_available_resources",
                "no_fitting_assignment",
                "no_safe_assignment",
            }:
                termination_reason = failure.reason
                break
            next_time_s = next_disturbance_boundary(
                scenario, current_time_s
            )
            if failure.reason == "no_safe_assignment":
                recovery_time_s = next_recovery_time(
                    scenario, current_time_s, config
                )
                if recovery_time_s is not None:
                    next_time_s = (
                        recovery_time_s
                        if next_time_s is None
                        else min(next_time_s, recovery_time_s)
                    )
            if next_time_s is None:
                termination_reason = failure.reason
                break
            apply_idle_recovery_interval(
                scenario, current_time_s, next_time_s, config
            )
            current_time_s = next_time_s
            continue

        task = get_task(scenario, assignment.task_id)
        operator_matches = [
            item for item in scenario.operators
            if item.operator_id == assignment.operator_id
        ]
        robot_matches = [
            item for item in scenario.robots
            if item.robot_id == assignment.robot_id
        ]
        if len(operator_matches) != 1:
            raise ValueError("Assignment must identify exactly one operator")
        if len(robot_matches) != 1:
            raise ValueError("Assignment must identify exactly one robot")
        operator = operator_matches[0]
        robot = robot_matches[0]

        common_values = get_objective_values(
            task,
            operator,
            robot,
            assignment.start_time_s,
            scenario,
            config,
        )

        common_objective += calculate_weighted_sum(
            common_values,
            config["weights"],
        ).score

        execute_assignment(assignment, scenario, config, rng)
        apply_idle_recovery_interval(
            scenario,
            assignment.start_time_s,
            assignment.completion_time_s,
            config,
            working_operator_id=assignment.operator_id,
        )
        assignments.append(assignment)

        veto_events += new_vetoes

        if assignment.safety_violation:
            safety_violations += 1

        current_time_s = assignment.completion_time_s

    if all(
        job.job_id in scenario.completed_job_ids
        for job in scenario.jobs
    ):
        termination_reason = "backlog_exhausted"

    completed_tasks = len(assignments)
    throughput = completed_tasks / (scenario.shift_duration_s / 3600.0)
    total_energy_kj = sum(robot.energy_used_kj for robot in scenario.robots)
    expected_defects = sum(
        assignment.defect_probability for assignment in assignments
    )

    final_fatigue = max(
        operator.fatigue_level for operator in scenario.operators
    )

    final_ergonomic_risk = max(
        calculate_ergonomic_risk(operator.fatigue_level, 0.0)
        for operator in scenario.operators
    )
    mean_final_fatigue = sum(
        operator.fatigue_level for operator in scenario.operators
    ) / len(scenario.operators)

    wellbeing = 1.0 - min(1.0, mean_final_fatigue)
    productivity = throughput
    return ShiftResult(
        arm=arm,
        scenario_id=scenario.scenario_id,
        completed_tasks=completed_tasks,
        makespan_s=max(
            (assignment.completion_time_s for assignment in assignments),
            default=0.0,
        ),
        dispatch_end_time_s=current_time_s,
        observation_time_s=current_time_s,
        termination_reason=termination_reason,
        throughput_tasks_per_hour=throughput,
        total_energy_kj=total_energy_kj,
        expected_defects=expected_defects,
        final_fatigue=final_fatigue,
        final_ergonomic_risk=final_ergonomic_risk,
        safety_violations=safety_violations,
        veto_events=veto_events,
        common_objective=common_objective,
        wellbeing=wellbeing,
        productivity=productivity,
        assignments=assignments,
        unfinished_jobs_by_type={
            task.task_id: sum(
                1 for job in scenario.jobs
                if job.task_type_id == task.task_id
                and job.job_id not in scenario.completed_job_ids
            )
            for task in scenario.tasks
        },
    )
