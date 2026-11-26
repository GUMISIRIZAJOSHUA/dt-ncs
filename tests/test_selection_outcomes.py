import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_scheduler_disturbances as fixtures
from src import scheduler


class TestSelectionOutcomes(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.TestSchedulerDisturbances()
        self.case.setUp()

    def assert_reason(self, expected):
        with self.assertRaises(scheduler.NoAssignmentAvailable) as caught:
            self.case.select()
        self.assertEqual(caught.exception.reason, expected)

    def test_backlog_exhausted(self):
        self.case.scenario.completed_job_ids.update(
            job.job_id for job in self.case.scenario.jobs
        )
        self.assert_reason("backlog_exhausted")

    def test_no_available_resources(self):
        self.case.scenario.disturbance_events = [
            self.case.event("operator_absence", 1),
            self.case.event("operator_absence", 2),
        ]
        self.assert_reason("no_available_resources")

    def test_no_fitting_assignment(self):
        self.case.scenario.shift_duration_s = 1.0
        self.assert_reason("no_fitting_assignment")

    def test_no_safe_assignment(self):
        with patch.object(
            scheduler, "get_score", return_value=1.0
        ), patch.object(
            scheduler,
            "evaluate_safety",
            return_value=SimpleNamespace(is_safe=False),
        ):
            with self.assertRaises(
                scheduler.NoAssignmentAvailable
            ) as caught:
                scheduler.select_assignment(
                    "B3",
                    self.case.scenario,
                    0.0,
                    self.case.config,
                    None,
                    arm_config=self.case.arm_config,
                )
        self.assertEqual(caught.exception.reason, "no_safe_assignment")

    def test_unexpected_runtime_error_propagates_from_shift(self):
        with patch.object(
            scheduler,
            "select_assignment",
            side_effect=RuntimeError("unexpected internal failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "unexpected internal failure"
            ):
                scheduler.run_shift(
                    "B3",
                    self.case.scenario,
                    self.case.config,
                    123,
                )


if __name__ == "__main__":
    unittest.main()