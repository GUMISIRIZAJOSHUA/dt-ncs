import unittest
from types import SimpleNamespace

from src.fatigue_adapter import FatigueAdapter


class TestFatigueAdapterFiniteInputs(unittest.TestCase):
    def setUp(self):
        # Synthetic verification values only; not experiment parameters.
        raw = dict(
            step_size_s=0.5,
            operators={
                10: dict(
                    initial_fatigue=0.2,
                    alpha_per_s=0.02,
                    beta=0.0,
                    rho_per_s=0.02,
                    fatigue_limit=0.8,
                )
            },
            task_demands={30: 1.0},
        )
        self.adapter = FatigueAdapter(
            raw, operator_ids=[10], task_ids=[30]
        )
        self.operator = SimpleNamespace(
            operator_id=10, fatigue_level=0.2
        )

    def invoke(self, method, duration=1.0, max_delay=10.0):
        operation = getattr(self.adapter, method)
        if method == "apply_recovery":
            return operation(self.operator, duration)
        if method == "find_rest_delay":
            return operation(self.operator, 30, duration, max_delay)
        return operation(self.operator, 30, duration)

    def test_nonfinite_durations_rejected_without_mutation(self):
        for method in (
            "project_work",
            "is_work_feasible",
            "apply_work",
            "apply_recovery",
            "find_rest_delay",
        ):
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(method=method, value=value):
                    self.operator.fatigue_level = 0.2
                    with self.assertRaisesRegex(
                        ValueError,
                        "^duration_s must be finite and non-negative$",
                    ):
                        self.invoke(method, duration=value)
                    self.assertEqual(self.operator.fatigue_level, 0.2)

    def test_nonfinite_fatigue_rejected_without_replacement(self):
        for method in (
            "project_work",
            "is_work_feasible",
            "apply_work",
            "apply_recovery",
            "find_rest_delay",
        ):
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(method=method, value=value):
                    self.operator.fatigue_level = value
                    with self.assertRaisesRegex(
                        ValueError,
                        "^fatigue must be finite and non-negative$",
                    ):
                        self.invoke(method)
                    self.assertIs(self.operator.fatigue_level, value)

    def test_nonfinite_rest_bounds_rejected_when_already_feasible(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                self.operator.fatigue_level = 0.2
                self.assertTrue(
                    self.adapter.is_work_feasible(self.operator, 30, 1.0)
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "^duration_s must be finite and non-negative$",
                ):
                    self.invoke("find_rest_delay", max_delay=value)
                self.assertEqual(self.operator.fatigue_level, 0.2)


if __name__ == "__main__":
    unittest.main()
