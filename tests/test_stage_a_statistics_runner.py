import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import run_experiment as runner
from src.statistics import (
    calculate_paired_comparison,
    calculate_t_critical,
)


class TestStageAStatisticsRunner(unittest.TestCase):
    def test_critical_value_uses_requested_confidence(self):
        self.assertAlmostEqual(
            calculate_t_critical(10, 0.95),
            2.2281388519649385,
            places=8,
        )
        self.assertAlmostEqual(
            calculate_t_critical(10, 0.90),
            1.8124611228107335,
            places=8,
        )

    def test_negative_constant_differences_preserve_sign(self):
        result = calculate_paired_comparison(
            "A", "B", "synthetic",
            [1.0, 2.0, 3.0],
            [3.0, 4.0, 5.0],
        )
        self.assertEqual(result.mean_difference, -2.0)
        self.assertEqual(result.t_statistic, -math.inf)
        self.assertEqual(result.cohens_d, -math.inf)
        self.assertEqual(result.p_value, 0.0)

    def test_comparisons_align_by_scenario_id(self):
        metrics = [
            SimpleNamespace(
                arm="A", scenario_id=2, completed_tasks=20,
            ),
            SimpleNamespace(
                arm="B", scenario_id=1, completed_tasks=100,
            ),
            SimpleNamespace(
                arm="A", scenario_id=1, completed_tasks=10,
            ),
            SimpleNamespace(
                arm="B", scenario_id=2, completed_tasks=200,
            ),
        ]

        def compare(**kwargs):
            if kwargs["arm_a"] == "A":
                expected_a, expected_b = [10, 20], [100, 200]
            else:
                expected_a, expected_b = [100, 200], [10, 20]

            self.assertEqual(kwargs["values_a"], expected_a)
            self.assertEqual(kwargs["values_b"], expected_b)
            return calculate_paired_comparison(**kwargs)

        with patch.object(
            runner,
            "getattr",
            side_effect=lambda obj, name: obj.completed_tasks,
            create=True,
        ), patch.object(
            runner,
            "calculate_paired_comparison",
            side_effect=compare,
        ) as mocked:
            rows = runner.calculate_comparisons(metrics)

        self.assertEqual(mocked.call_count, 24)
        self.assertEqual(len(rows), 24)

    def test_duplicate_scenario_is_rejected(self):
        metrics = [
            SimpleNamespace(arm="A", scenario_id=1),
            SimpleNamespace(arm="A", scenario_id=1),
        ]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            runner.calculate_comparisons(metrics)

    def test_mismatched_scenarios_are_rejected(self):
        metrics = [
            SimpleNamespace(arm="A", scenario_id=1),
            SimpleNamespace(arm="B", scenario_id=2),
        ]
        with self.assertRaisesRegex(ValueError, "do not match"):
            runner.calculate_comparisons(metrics)

    def test_single_replicate_has_no_comparisons(self):
        metrics = [
            SimpleNamespace(arm="A", scenario_id=1),
            SimpleNamespace(arm="B", scenario_id=1),
        ]
        self.assertEqual(runner.calculate_comparisons(metrics), [])

    def seed_fixture(self):
        config = {
            "arms": ["A", "B"],
            "pilot_replicates_per_arm": 1,
            "replicates_per_arm": 2,
        }
        definitions = {"arms": {"A": {}, "B": {}}}
        seeds = [
            {
                "arm": arm,
                "replicate": replicate,
                "scenario_seed": 100 + replicate,
                "search_seed": 200 + index,
            }
            for index, (arm, replicate) in enumerate(
                [("B", 2), ("A", 1), ("B", 1), ("A", 2)]
            )
        ]
        return config, definitions, seeds

    def test_pilot_selects_one_matching_replicate_per_arm(self):
        config, definitions, seeds = self.seed_fixture()
        selected = runner.select_seed_rows(
            seeds, config, definitions, "pilot",
        )
        self.assertEqual(
            [(row["arm"], row["replicate"]) for row in selected],
            [("A", 1), ("B", 1)],
        )

    def test_inconsistent_scenario_seeds_are_rejected(self):
        config, definitions, seeds = self.seed_fixture()
        seeds[2]["scenario_seed"] = 999
        with self.assertRaisesRegex(
            ValueError, "Scenario seeds differ",
        ):
            runner.select_seed_rows(
                seeds, config, definitions, "pilot",
            )


if __name__ == "__main__":
    unittest.main()