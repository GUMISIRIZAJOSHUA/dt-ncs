import unittest
from unittest.mock import patch
from types import SimpleNamespace

import test_scheduler_disturbances as fixtures
from src import scheduler


class TestEventWaiting(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.TestSchedulerDisturbances()
        self.case.setUp()
        self.scenario = self.case.scenario

    def run_case(self):
        # Isolate waiting/accounting from fatigue accumulation and ranking.
        with patch.object(
            scheduler, "get_score", return_value=1.0
        ), patch.object(
            scheduler,
            "evaluate_safety",
            return_value=SimpleNamespace(is_safe=True),
        ), patch.object(
            scheduler, "apply_fatigue_update"
        ):
            return scheduler.run_shift(
                "B3", self.scenario, self.case.config, 123,
                arm_config=self.case.arm_config,
            )

    def test_waits_until_absent_operators_return(self):
        self.scenario.disturbance_events = [
            self.case.event("operator_absence", 1),
            self.case.event("operator_absence", 2),
        ]
        for operator in self.scenario.operators:
            operator.fatigue_level = 0.6

        result = self.run_case()

        self.assertEqual(result.completed_tasks, 1)
        self.assertEqual(result.assignments[0].start_time_s, 30.0)
        self.assertEqual(result.assignments[0].completion_time_s, 50.0)
        self.assertEqual(result.unfinished_jobs_by_type, {1: 0})
        # Absence earns no recovery; only the present idle operator rests.
        self.assertAlmostEqual(
            self.scenario.operators[0].fatigue_level, 0.6
        )
        self.assertAlmostEqual(
            self.scenario.operators[1].fatigue_level, 0.3
        )

    def test_waits_for_slowdown_expiry_when_nothing_fits_now(self):
        self.scenario.shift_duration_s = 24.0
        event = self.case.event("robot_degradation", 1)
        event.duration_s = 3.0
        self.scenario.disturbance_events = [event]

        result = self.run_case()

        self.assertEqual(result.completed_tasks, 1)
        self.assertEqual(result.assignments[0].start_time_s, 3.0)
        self.assertEqual(result.assignments[0].completion_time_s, 23.0)
        self.assertEqual(self.scenario.robots[0].base_speed, 1.0)

    def test_does_not_wait_beyond_horizon(self):
        self.scenario.shift_duration_s = 10.0
        self.scenario.disturbance_events = [
            self.case.event("operator_absence", 1),
            self.case.event("operator_absence", 2),
        ]
        result = self.run_case()
        self.assertEqual(result.completed_tasks, 0)
        self.assertEqual(result.unfinished_jobs_by_type, {1: 1})
        self.assertLessEqual(
            result.makespan_s, self.scenario.shift_duration_s
        )

    def test_boundary_is_strictly_in_future_and_before_horizon(self):
        self.scenario.disturbance_events = [
            self.case.event("operator_absence", 1)
        ]
        self.assertEqual(
            scheduler.next_disturbance_boundary(self.scenario, 0.0),
            30.0,
        )
        self.assertIsNone(
            scheduler.next_disturbance_boundary(self.scenario, 30.0)
        )
        self.scenario.shift_duration_s = 30.0
        self.assertIsNone(
            scheduler.next_disturbance_boundary(self.scenario, 0.0)
        )


if __name__ == "__main__":
    unittest.main()