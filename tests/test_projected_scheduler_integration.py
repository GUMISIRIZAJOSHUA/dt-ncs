import math
import random
import unittest
from unittest.mock import patch

from src.scenario import Scenario, Task, Operator, Robot
from src.jobs import JobInstance
from src.fatigue_adapter import FatigueAdapter
from src import scheduler


class TestProjectedSchedulerIntegration(unittest.TestCase):
    def make_case(self, *, horizon=10.0, duration=1.0, initial=0.79):
        # Synthetic verification inputs only; not experiment parameters.
        task = Task(task_id=30, name="Verification task", manual_time_s=duration, robot_time_s=duration, fatigue_coefficient=1.0, cognitive_load=0.0, robot_energy_kj=1.0, defect_risk=0.0)
        operators = [Operator(operator_id=i, name=str(i), base_skill=1.0, fatigue_capacity=1.0) for i in (1, 2)]
        robots = [Robot(robot_id=1, name="R1", base_speed=1.0, energy_capacity_kj=1000.0)]
        scenario = Scenario(scenario_id=1, shift_duration_s=horizon, tasks=[task], operators=operators, robots=robots, jobs=[JobInstance(job_id=1, task_type_id=30)])
        row = dict(initial_fatigue=initial, alpha_per_s=0.02, beta=0.0, rho_per_s=0.02, fatigue_limit=0.8)
        raw = dict(step_size_s=0.5, operators={i: dict(row) for i in (1, 2)}, task_demands={30: 1.0})
        adapter = FatigueAdapter(raw, operator_ids=[1, 2], task_ids=[30])
        adapter.initialize(operators)
        scenario._fatigue_adapter = adapter
        config = dict(fatigue_critical_threshold=0.8, ergonomic_critical_threshold=0.8, collision_critical_threshold=0.8, safe_zone_critical_threshold=0.8, weights=dict(productivity=0.25, quality=0.15, wellbeing=0.25, sustainability=0.20, collaboration=0.15))
        return scenario, config

    def run_case(self, scenario, config, veto=True):
        return scheduler.run_shift("verification", scenario, config, 123, arm_config=dict(veto=veto, objective="productivity"))

    def test_noncontiguous_resource_ids_with_real_adapter(self):
        scenario, config = self.make_case()
        raw = dict(
            step_size_s=0.5,
            operators={},
            task_demands={30: 1.0},
        )
        for operator, new_id in zip(scenario.operators, (10, 30)):
            previous = scenario._fatigue_adapter.parameters.operators[operator.operator_id]
            raw["operators"][new_id] = dict(vars(previous))
            operator.operator_id = new_id
        scenario.robots[0].robot_id = 20
        adapter = FatigueAdapter(
            raw, operator_ids=[10, 30], task_ids=[30]
        )
        adapter.initialize(scenario.operators)
        scenario._fatigue_adapter = adapter

        with patch("src.scheduler.calculate_collision_risk", return_value=0.0), patch(
            "src.scheduler.calculate_safe_zone_risk", return_value=0.0
        ), patch(
            "src.projected_waiting.calculate_collision_risk", return_value=0.0
        ), patch(
            "src.projected_waiting.calculate_safe_zone_risk", return_value=0.0
        ):
            result = self.run_case(scenario, config)

        self.assertEqual(result.completed_tasks, 1)
        self.assertEqual(len(result.assignments), 1)
        assignment = result.assignments[0]
        self.assertIn(assignment.operator_id, (10, 30))
        self.assertEqual(assignment.robot_id, 20)
        worker = next(
            o for o in scenario.operators
            if o.operator_id == assignment.operator_id
        )
        other = next(o for o in scenario.operators if o is not worker)
        expected_start = math.log(0.79 / 0.78) / 0.02
        self.assertAlmostEqual(assignment.start_time_s, expected_start, places=9)
        self.assertAlmostEqual(assignment.completion_time_s, expected_start + 1.0, places=9)
        self.assertAlmostEqual(worker.fatigue_level, 0.8, places=9)
        self.assertLessEqual(worker.fatigue_level, 0.8)
        self.assertIn(30, worker.completed_tasks)
        self.assertEqual(other.completed_tasks, [])
        self.assertIn(30, scenario.robots[0].completed_tasks)
        self.assertAlmostEqual(scenario.robots[0].energy_used_kj, 1.0)
        self.assertEqual(scenario.completed_job_ids, {1})
        self.assertEqual(result.safety_violations, 0)
        self.assertEqual(result.termination_reason, "backlog_exhausted")
        self.assertEqual(result.unfinished_jobs_by_type, {30: 0})

    def test_safe_start_unsafe_finish_is_rejected_at_selection(self):
        scenario, config = self.make_case()
        self.assertLess(scenario.operators[1].fatigue_level, 0.8)
        with self.assertRaises(scheduler.NoAssignmentAvailable) as caught:
            scheduler.select_assignment("verification", scenario, 0.0, config, random.Random(123), arm_config=dict(veto=True, objective="productivity"))
        self.assertEqual(caught.exception.reason, "no_safe_assignment")
        self.assertEqual(scenario.completed_job_ids, set())
        self.assertEqual(scenario.operators[1].fatigue_level, 0.79)

    def test_rest_then_execute_matches_projected_limit(self):
        scenario, config = self.make_case()
        result = self.run_case(scenario, config)
        expected_start = math.log(0.79 / 0.78) / 0.02
        self.assertEqual(result.completed_tasks, 1)
        assignment = result.assignments[0]
        self.assertEqual(assignment.operator_id, 2)
        self.assertEqual(assignment.robot_id, 1)
        self.assertAlmostEqual(assignment.start_time_s, expected_start, places=9)
        self.assertAlmostEqual(assignment.completion_time_s, expected_start + 1.0, places=9)
        self.assertLessEqual(scenario.operators[1].fatigue_level, 0.8)
        self.assertEqual(result.safety_violations, 0)
        self.assertEqual(result.termination_reason, "backlog_exhausted")
        self.assertEqual(result.unfinished_jobs_by_type, {30: 0})

    def test_insufficient_recovery_window_leaves_job_unfinished(self):
        scenario, config = self.make_case(horizon=1.1)
        result = self.run_case(scenario, config)
        self.assertEqual(result.completed_tasks, 0)
        self.assertEqual(result.dispatch_end_time_s, 0.0)
        self.assertEqual(result.termination_reason, "no_safe_assignment")
        self.assertEqual(result.unfinished_jobs_by_type, {30: 1})
        self.assertEqual(scenario.operators[1].fatigue_level, 0.79)

    def test_work_infeasible_from_zero_is_not_executed(self):
        scenario, config = self.make_case(horizon=200.0, duration=50.0, initial=0.0)
        result = self.run_case(scenario, config)
        self.assertEqual(result.completed_tasks, 0)
        self.assertEqual(result.termination_reason, "no_safe_assignment")
        self.assertEqual(result.unfinished_jobs_by_type, {30: 1})
        self.assertEqual(scenario.operators[1].fatigue_level, 0.0)

    def test_non_veto_executes_same_dynamics_and_flags_violation(self):
        scenario, config = self.make_case()
        result = self.run_case(scenario, config, veto=False)
        self.assertEqual(result.completed_tasks, 1)
        assignment = result.assignments[0]
        self.assertEqual(assignment.start_time_s, 0.0)
        self.assertTrue(assignment.safety_violation)
        self.assertEqual(result.safety_violations, 1)
        worker = next(o for o in scenario.operators if o.operator_id == assignment.operator_id)
        self.assertAlmostEqual(worker.fatigue_level, 0.81)
        self.assertEqual(result.termination_reason, "backlog_exhausted")


if __name__ == "__main__":
    unittest.main()
