import unittest
from unittest.mock import patch

import test_scheduler_disturbances as fixtures
from src import scheduler


class TestFatigueWaitingIntegration(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.TestSchedulerDisturbances()
        self.case.setUp()
        self.scenario = self.case.scenario
        self.config = self.case.config
        self.config.update({
            "fatigue_critical_threshold": 0.8,
            "ergonomic_critical_threshold": 0.8,
            "collision_critical_threshold": 0.8,
            "safe_zone_critical_threshold": 0.8,
        })
        self.scenario.operators[0].fatigue_level = 1.0
        self.scenario.operators[1].fatigue_level = 0.9

    def run_case(self):
        # Use real safety and recovery; isolate ranking and work accumulation.
        with patch.object(
            scheduler, "get_score", return_value=1.0
        ), patch.object(
            scheduler, "apply_fatigue_update"
        ):
            return scheduler.run_shift(
                "B3", self.scenario, self.config, 123,
                arm_config=self.case.arm_config,
            )

    def test_recovers_then_completes_without_disturbance(self):
        result = self.run_case()
        expected_start = (0.9 - 0.8) / 0.015

        self.assertEqual(result.completed_tasks, 1)
        assignment = result.assignments[0]
        self.assertEqual(assignment.operator_id, 2)
        self.assertEqual(assignment.robot_id, 1)
        self.assertAlmostEqual(assignment.start_time_s, expected_start)
        self.assertAlmostEqual(
            assignment.completion_time_s, expected_start + 20.0
        )
        self.assertEqual(result.termination_reason, "backlog_exhausted")
        self.assertEqual(result.unfinished_jobs_by_type, {1: 0})

    def test_does_not_rest_if_recovery_leaves_no_time_to_finish(self):
        self.scenario.shift_duration_s = 25.0
        result = self.run_case()
        self.assertEqual(result.completed_tasks, 0)
        self.assertEqual(result.dispatch_end_time_s, 0.0)
        self.assertEqual(result.termination_reason, "no_safe_assignment")
        self.assertEqual(result.unfinished_jobs_by_type, {1: 1})

    def test_disturbance_boundary_precedes_recovery(self):
        # Keep operator 1 from becoming safe before operator 2 returns and rests.
        self.scenario.operators[0].fatigue_level = 1.25
        event = self.case.event("operator_absence", 2)
        event.start_time_s = 2.0
        event.duration_s = 10.0
        self.scenario.disturbance_events = [event]

        self.assertEqual(
            scheduler.next_recovery_time(
                self.scenario, 0.0, self.config
            ),
            None,
        )
        result = self.run_case()

        self.assertEqual(result.completed_tasks, 1)
        assignment = result.assignments[0]
        # Operator 2 rests for 2 s, is absent for 10 s,
        # then needs the remainder of its recovery time.
        expected_start = 10.0 + (0.9 - 0.8) / 0.015
        self.assertEqual(assignment.operator_id, 2)
        self.assertAlmostEqual(assignment.start_time_s, expected_start)

    def test_permanent_geometry_failure_does_not_trigger_rest(self):
        # With only IDs 1 and 1, collision risk is always 1.0.
        self.scenario.operators = self.scenario.operators[:1]
        self.scenario.robots = self.scenario.robots[:1]
        result = self.run_case()
        self.assertEqual(result.completed_tasks, 0)
        self.assertEqual(result.dispatch_end_time_s, 0.0)
        self.assertEqual(result.termination_reason, "no_safe_assignment")


if __name__ == "__main__":
    unittest.main()