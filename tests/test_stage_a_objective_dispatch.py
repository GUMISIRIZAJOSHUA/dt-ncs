import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src import scheduler
from src.objectives import ObjectiveValues


class TestStageAObjectiveDispatch(unittest.TestCase):
    def setUp(self):
        self.values = ObjectiveValues(
            productivity=0.8,
            quality=0.9,
            wellbeing=0.4,
            sustainability=0.7,
            collaboration=0.6,
        )
        self.config = {
            "weights": {
                name: 0.2
                for name in vars(self.values)
            },
            "harrington_soft_thresholds": {
                name: 0.5
                for name in vars(self.values)
            },
            "harrington_k": 3.0,
            "harrington_p": 2.0,
        }

    def score(self, arm_config, arm="arbitrary_label"):
        with patch.object(
            scheduler,
            "get_objective_values",
            return_value=self.values,
        ):
            return scheduler.get_score(
                arm, None, None, None, 0.0,
                None, self.config,
                arm_config=arm_config,
            )

    def test_configured_objective_controls_dispatch(self):
        routes = {
            "productivity": "calculate_productivity_first",
            "weighted_sum": "calculate_weighted_sum",
            "multiplicative_synergy":
                "calculate_multiplicative_synergy",
            "multiplicative_synergy_harrington":
                "calculate_synergy_with_harrington",
        }
        for objective, function_name in routes.items():
            with self.subTest(objective=objective):
                with patch.object(
                    scheduler,
                    function_name,
                    return_value=SimpleNamespace(score=0.123),
                ) as selected:
                    actual = self.score({
                        "veto": True,
                        "objective": objective,
                    })
                self.assertEqual(actual, 0.123)
                if objective == "multiplicative_synergy_harrington":
                    selected.assert_called_once_with(
                        self.values,
                        self.config["weights"],
                        self.config["harrington_soft_thresholds"],
                        k=3.0,
                        p=2.0,
                    )
                else:
                    selected.assert_called_once_with(
                        self.values,
                        self.config["weights"],
                    )

    def test_arm_label_does_not_override_objective(self):
        actual = self.score(
            {"veto": True, "objective": "productivity"},
            arm="B3",
        )
        self.assertAlmostEqual(actual, 0.8)

    def test_real_objective_scores(self):
        weighted = sum(vars(self.values).values()) / 5.0
        synergy = 1.0
        for value in vars(self.values).values():
            synergy *= value ** 0.2

        expected = {
            "productivity": 0.8,
            "weighted_sum": weighted,
            "multiplicative_synergy": synergy,
            "multiplicative_synergy_harrington":
                synergy - 3.0 * (0.5 - 0.4) ** 2,
        }
        for objective, score in expected.items():
            with self.subTest(objective=objective):
                self.assertAlmostEqual(
                    self.score({
                        "veto": True,
                        "objective": objective,
                    }),
                    score,
                )

    def test_missing_arm_configuration_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError, "Missing arm configuration",
        ):
            self.score(None)

    def test_unknown_objective_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError, "Unknown objective",
        ):
            self.score({
                "veto": True,
                "objective": "unsupported_objective",
            })


if __name__ == "__main__":
    unittest.main()
