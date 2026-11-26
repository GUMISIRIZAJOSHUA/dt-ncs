import random
import time

from src.safety import (
    calculate_collision_risk,
    calculate_safe_zone_risk,
    evaluate_safety,
)
from src.fatigue import calculate_ergonomic_risk
from src.objectives import (
    calculate_productivity_first,
    calculate_weighted_sum,
)
from src.scheduler import (    Assignment,
    execute_assignment,
    get_objective_values,
)
from src.solvers.base import BaseSolver, SolverResult


class ConstructiveSolver(BaseSolver):
    def solve(self, scenario, config, seed):
        start_time = time.perf_counter()
        rng = random.Random(seed)

        current_time_s = 0.0
        assignments = []
        safety_violations = 0
        veto_events = 0
        common_objective = 0.0

        last_active = {
            operator.operator_id: 0.0
            for operator in scenario.operators
        }

        while current_time_s < scenario.shift_duration_s:
            for operator in scenario.operators:
                idle_time = current_time_s - last_active[
                    operator.operator_id
                ]

                if idle_time > 0:
                    from src.fatigue import apply_recovery

                    apply_recovery(operator, idle_time, config)

            best_safe = None
            best_safe_score = -1e12
            unsafe_candidate_count = 0

            for task in scenario.tasks:
                if not config.get("allow_task_repetition", False) and task.task_id in scenario.completed_task_ids:
                    continue
                for operator in scenario.operators:
                    for robot in scenario.robots:
                        collision_risk = calculate_collision_risk(
                            operator.operator_id,
                            robot.robot_id,
                        )
                        safe_zone_risk = calculate_safe_zone_risk(
                            operator.operator_id,
                            2.5,
                        )
                        ergonomic_risk = calculate_ergonomic_risk(
                            operator.fatigue_level,
                            task.cognitive_load,
                        )

                        safety = evaluate_safety(
                            operator.fatigue_level,
                            ergonomic_risk,
                            collision_risk,
                            safe_zone_risk,
                            config,
                        )

                        values = get_objective_values(
                            task,
                            operator,
                            robot,
                            current_time_s,
                            scenario,
                            config,
                        )

                        score = calculate_productivity_first(
                            values,
                            config["weights"],
                        ).score

                        duration = max(
                            task.manual_time_s / operator.base_skill,
                            task.robot_time_s / robot.base_speed,
                        )

                        candidate = Assignment(
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
                            if score > best_safe_score:
                                best_safe = candidate
                                best_safe_score = score
                        else:
                            unsafe_candidate_count += 1

            if best_safe is None:
                break

            veto_events += unsafe_candidate_count

            common_values = get_objective_values(
                next(t for t in scenario.tasks if t.task_id == best_safe.task_id),
                next(o for o in scenario.operators if o.operator_id == best_safe.operator_id),
                next(r for r in scenario.robots if r.robot_id == best_safe.robot_id),
                best_safe.start_time_s,
                scenario,
                config,
            )

            common_objective += calculate_weighted_sum(
                common_values,
                config["weights"],
            ).score

            execute_assignment(best_safe, scenario, config, rng)
            assignments.append(best_safe)

            if best_safe.safety_violation:
                safety_violations += 1

            last_active[best_safe.operator_id] = (
                best_safe.completion_time_s
            )
            current_time_s = best_safe.completion_time_s

        runtime = time.perf_counter() - start_time
        objective = sum(
            assignment.objective_score for assignment in assignments
        )

        mean_final_fatigue = sum(
            operator.fatigue_level for operator in scenario.operators
        ) / len(scenario.operators)

        wellbeing = 1.0 - min(1.0, mean_final_fatigue)
        productivity = len(assignments) / (scenario.shift_duration_s / 3600.0)
        return SolverResult(
            solver="CH",
            layout=getattr(scenario, "layout", "2H2R"),
            tasks=len(assignments),
            seed=seed,
            objective=objective,
            runtime_s=runtime,
            feasible=safety_violations == 0,
            timeout=runtime > self.time_budget_s,
            safety_violations=safety_violations,
            veto_events=veto_events,
            completed_tasks=len(assignments),
            common_objective=common_objective,
            wellbeing=wellbeing,
            productivity=productivity,
            assignments={
                "assignments": [
                    {
                        "task_id": assignment.task_id,
                        "operator_id": assignment.operator_id,
                        "robot_id": assignment.robot_id,
                        "objective_score": assignment.objective_score,
                    }
                    for assignment in assignments
                ]
            },
        )