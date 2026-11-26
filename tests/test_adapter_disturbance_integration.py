"""Synthetic integration inputs only; not experimental parameters."""

import math
import unittest
from types import SimpleNamespace

import test_projected_scheduler_integration as fixtures
from src import scheduler


class TestAdapterDisturbanceIntegration(unittest.TestCase):
    def test_absence_wait_then_real_adapter_work_and_idle_recovery(self):
        case = fixtures.TestProjectedSchedulerIntegration()
        scenario, config = case.make_case(
            horizon=10.0,
            duration=1.0,
            initial=0.2,
        )
        scenario.disturbance_events = [
            SimpleNamespace(
                event_type="operator_absence",
                target_resource_id=operator.operator_id,
                start_time_s=0.0,
                duration_s=2.0,
                severity=1.0,
            )
            for operator in scenario.operators
        ]

        result = scheduler.run_shift(
            "synthetic_adapter_absence",
            scenario,
            config,
            123,
            arm_config={
                "veto": True,
                "objective": "productivity",
            },
        )

        self.assertEqual(result.completed_tasks, 1)
        self.assertEqual(len(result.assignments), 1)

        assignment = result.assignments[0]
        self.assertEqual(assignment.operator_id, 2)
        self.assertEqual(assignment.robot_id, 1)
        self.assertAlmostEqual(assignment.start_time_s, 2.0)
        self.assertAlmostEqual(assignment.duration_s, 1.0)
        self.assertAlmostEqual(assignment.completion_time_s, 3.0)

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

        # Neither operator recovers during the initial two-second absence.
        # The worker then gains 0.02 fatigue over one second of work.
        self.assertAlmostEqual(worker.fatigue_level, 0.22, places=9)

        # The idle operator recovers only during the one-second assignment.
        self.assertAlmostEqual(
            idle.fatigue_level,
            0.2 * math.exp(-0.02),
            places=9,
        )
        self.assertAlmostEqual(result.final_fatigue, 0.22, places=9)

        self.assertEqual(worker.completed_tasks, [30])
        self.assertEqual(idle.completed_tasks, [])
        self.assertEqual(scenario.robots[0].completed_tasks, [30])
        self.assertAlmostEqual(scenario.robots[0].energy_used_kj, 1.0)
        self.assertEqual(scenario.completed_job_ids, {1})
        self.assertEqual(result.unfinished_jobs_by_type, {30: 0})
        self.assertEqual(result.safety_violations, 0)
        self.assertFalse(assignment.safety_violation)
        self.assertEqual(result.termination_reason, "backlog_exhausted")
        self.assertAlmostEqual(result.makespan_s, 3.0)
        self.assertAlmostEqual(result.dispatch_end_time_s, 3.0)
        self.assertAlmostEqual(result.observation_time_s, 3.0)


if __name__ == "__main__":
    unittest.main()