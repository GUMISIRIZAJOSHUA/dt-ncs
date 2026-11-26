import unittest
from unittest.mock import patch

import test_scheduler_disturbances as fixtures
from src import scheduler


class TestAbsenceRecovery(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.TestSchedulerDisturbances()
        self.case.setUp()
        self.scenario = self.case.scenario
        for operator in self.scenario.operators:
            operator.fatigue_level = 1.0

    def absence(self, start, duration):
        event = self.case.event("operator_absence", 2)
        event.start_time_s = start
        event.duration_s = duration
        return event

    def recover(self, start=0.0, end=30.0, working=1):
        scheduler.apply_idle_recovery_interval(
            self.scenario,
            start,
            end,
            self.case.config,
            working_operator_id=working,
        )

    def test_full_absence_has_no_recovery(self):
        self.scenario.disturbance_events = [self.absence(0.0, 30.0)]
        self.recover()
        self.assertEqual(self.scenario.operators[0].fatigue_level, 1.0)
        self.assertEqual(self.scenario.operators[1].fatigue_level, 1.0)

    def test_only_present_parts_of_interval_recover(self):
        self.scenario.disturbance_events = [self.absence(10.0, 10.0)]
        with patch.object(
            scheduler, "apply_recovery", wraps=scheduler.apply_recovery
        ) as recovery:
            self.recover()

        intervals = [
            (call.args[0].operator_id, call.args[1])
            for call in recovery.call_args_list
        ]
        self.assertEqual(intervals, [(2, 10.0), (2, 10.0)])
        self.assertAlmostEqual(
            self.scenario.operators[1].fatigue_level, 0.7
        )
        self.assertEqual(self.scenario.operators[0].fatigue_level, 1.0)

    def test_overlapping_absences_count_union_not_sum(self):
        self.scenario.disturbance_events = [
            self.absence(5.0, 15.0),
            self.absence(10.0, 15.0),
        ]
        self.recover()
        # Absent from 5 through 25; present for 10 seconds total.
        self.assertAlmostEqual(
            self.scenario.operators[1].fatigue_level, 0.85
        )

    def test_absence_ending_at_interval_start_allows_recovery(self):
        self.scenario.disturbance_events = [self.absence(0.0, 10.0)]
        self.recover(start=10.0, end=30.0)
        self.assertAlmostEqual(
            self.scenario.operators[1].fatigue_level, 0.7
        )

    def test_present_waiting_operators_both_recover(self):
        self.recover(working=None)
        for operator in self.scenario.operators:
            self.assertAlmostEqual(operator.fatigue_level, 0.55)

    def test_zero_duration_does_not_apply_recovery(self):
        with patch.object(scheduler, "apply_recovery") as recovery:
            self.recover(start=10.0, end=10.0)
        recovery.assert_not_called()

    def test_invalid_interval_rejected_without_fatigue_change(self):
        for start, end in (
            (-1.0, 10.0),
            (20.0, 10.0),
            (0.0, 101.0),
            (0.0, float("nan")),
        ):
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    self.recover(start=start, end=end)
        self.assertEqual(
            [operator.fatigue_level for operator in self.scenario.operators],
            [1.0, 1.0],
        )


if __name__ == "__main__":
    unittest.main()