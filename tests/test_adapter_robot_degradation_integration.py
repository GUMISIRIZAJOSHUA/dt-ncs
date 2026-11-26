"""Synthetic integration inputs only; not experimental parameters."""

import math
import unittest
from types import SimpleNamespace

import test_projected_scheduler_integration as fixtures
from src import scheduler


class TestAdapterRobotDegradationIntegration(unittest.TestCase):
    def test_active_degradation_with_real_adapter(self):
        case = fixtures.TestProjectedSchedulerIntegration()
        scenario, config = case.make_case(
            horizon=10.0,
            duration=1.0,
            initial=0.2,
        )
        scenario.disturbance_events = [
            SimpleNamespace(
                event_type="robot_degradation",
                target_resource_id=1,
                start_time_s=0.0,
                duration_s=10.0,
                severity=1.0,
            )
        ]

        result = scheduler.run_shift(
            "synthetic_adapter_robot_degradation",
            scenario,
            config,
            123,
            arm_config={
                "veto": True,
                "objective": "productivity",
            },
        )

        # Baseline speed 1.0 minus severity * 0.20 gives 0.8.
        # Robot time therefore controls duration: 1.0 / 0.8 = 1.25.
        expected_duration = 1.25

        self.assertEqual(result.completed_tasks, 1)
        self.assertEqual(len(result.assignments), 1)
        assignment = result.assignments[0]
        self.assertEqual(assignment.operator_id, 2)
        self.assertEqual(assignment.robot_id, 1)
        self.assertAlmostEqual(assignment.start_time_s, 0.0)
        self.assertAlmostEqual(assignment.duration_s, expected_duration)
        self.assertAlmostEqual(
            assignment.completion_time_s,
            expected_duration,
        )

        worker = next(
            operator
            for operator in scenario.operators
            if operator.operator_id == assignment.operator_id
        )
        idle = next(
            operator
            for operator in scenario.operators
            if operator.operator_id != assignment.operator_id
        )

        self.assertAlmostEqual(
            worker.fatigue_level,
            0.2 + 0.02 * expected_duration,
            places=9,
        )
        self.assertAlmostEqual(
            idle.fatigue_level,
            0.2 * math.exp(-0.02 * expected_duration),
            places=9,
        )
        self.assertAlmostEqual(result.final_fatigue, 0.225, places=9)

        self.assertEqual(scenario.robots[0].base_speed, 1.0)
        self.assertAlmostEqual(scenario.robots[0].energy_used_kj, 1.0)
        self.assertEqual(worker.completed_tasks, [30])
        self.assertEqual(idle.completed_tasks, [])
        self.assertEqual(scenario.robots[0].completed_tasks, [30])
        self.assertEqual(scenario.completed_job_ids, {1})
        self.assertEqual(result.unfinished_jobs_by_type, {30: 0})
        self.assertEqual(result.safety_violations, 0)
        self.assertFalse(assignment.safety_violation)
        self.assertEqual(result.termination_reason, "backlog_exhausted")
        self.assertAlmostEqual(result.makespan_s, expected_duration)
        self.assertAlmostEqual(
            result.dispatch_end_time_s,
            expected_duration,
        )
        self.assertAlmostEqual(
            result.observation_time_s,
            expected_duration,
        )


if __name__ == "__main__":
    unittest.main()