import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import test_event_waiting as fixtures
from src.io_utils import save_csv
from src.metrics import calculate_shift_metrics
from run_experiment import metrics_to_rows


class TestTimeReporting(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.TestEventWaiting()
        self.case.setUp()

    def test_completed_backlog_reports_last_completion(self):
        result = self.case.run_case()
        self.assertEqual(result.makespan_s, 20.0)
        self.assertEqual(result.dispatch_end_time_s, 20.0)
        self.assertEqual(result.observation_time_s, 20.0)
        self.assertEqual(result.termination_reason, "backlog_exhausted")

    def test_waiting_without_completion_is_not_makespan(self):
        scenario = self.case.scenario
        scenario.tasks[0].robot_time_s = 200.0
        scenario.disturbance_events = [
            self.case.case.event("operator_absence", 1),
            self.case.case.event("operator_absence", 2),
        ]
        result = self.case.run_case()

        self.assertEqual(result.completed_tasks, 0)
        self.assertEqual(result.makespan_s, 0.0)
        self.assertEqual(result.dispatch_end_time_s, 30.0)
        self.assertEqual(result.observation_time_s, 30.0)
        self.assertEqual(
            result.termination_reason, "no_fitting_assignment"
        )

    def test_empty_backlog_reports_zero_times(self):
        self.case.scenario.jobs = []
        result = self.case.run_case()
        self.assertEqual(result.makespan_s, 0.0)
        self.assertEqual(result.dispatch_end_time_s, 0.0)
        self.assertEqual(result.observation_time_s, 0.0)
        self.assertEqual(result.termination_reason, "backlog_exhausted")

    def test_reporting_fields_reach_csv(self):
        result = self.case.run_case()
        metric = calculate_shift_metrics(result)
        rows = metrics_to_rows([metric])

        with TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.csv"
            save_csv(rows, str(path))
            with path.open(encoding="utf-8", newline="") as stream:
                saved = list(csv.DictReader(stream))

        self.assertEqual(len(saved), 1)
        row = saved[0]
        self.assertEqual(float(row["makespan_s"]), result.makespan_s)
        self.assertEqual(
            float(row["dispatch_end_time_s"]),
            result.dispatch_end_time_s,
        )
        self.assertEqual(
            float(row["observation_time_s"]),
            result.observation_time_s,
        )
        self.assertEqual(
            row["termination_reason"], result.termination_reason
        )


if __name__ == "__main__":
    unittest.main()