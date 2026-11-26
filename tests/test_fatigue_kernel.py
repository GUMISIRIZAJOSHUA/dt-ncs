import math
import unittest

from src.fatigue_kernel import advance_recovery, advance_work


class TestFatigueKernel(unittest.TestCase):
    def work(self, **changes):
        values = {
            "fatigue": 0.2,
            "duration_s": 2.5,
            "alpha_per_s": 0.1,
            "beta": 0.0,
            "demand": 0.4,
            "step_size_s": 1.0,
        }
        values.update(changes)
        return advance_work(**values)

    def test_constant_accumulation_with_partial_step(self):
        result = self.work()
        expected = 0.2 + 0.1 * 0.4 * 2.5
        self.assertAlmostEqual(result.final_fatigue, expected)
        self.assertAlmostEqual(result.maximum_fatigue, expected)

    def test_fatigue_dependent_accumulation(self):
        result = self.work(
            duration_s=2.5,
            alpha_per_s=0.1,
            beta=1.0,
            demand=1.0,
        )
        first = 0.2 + 0.1 * (1.0 + 0.2)
        second = first + 0.1 * (1.0 + first)
        expected = second + 0.1 * (1.0 + second) * 0.5
        self.assertAlmostEqual(result.final_fatigue, expected)
        self.assertAlmostEqual(result.maximum_fatigue, expected)

    def test_work_saturates_at_one(self):
        result = self.work(
            fatigue=0.9,
            duration_s=10.0,
            alpha_per_s=1.0,
            demand=1.0,
        )
        self.assertEqual(result.final_fatigue, 1.0)
        self.assertEqual(result.maximum_fatigue, 1.0)

    def test_zero_duration_rate_or_demand_preserves_fatigue(self):
        for change in (
            {"duration_s": 0.0},
            {"alpha_per_s": 0.0},
            {"demand": 0.0},
        ):
            with self.subTest(change=change):
                result = self.work(**change)
                self.assertEqual(result.final_fatigue, 0.2)
                self.assertEqual(result.maximum_fatigue, 0.2)

    def test_exponential_recovery_and_interval_composition(self):
        expected = 0.8 * math.exp(-0.02 * 30.0)
        whole = advance_recovery(0.8, 30.0, rho_per_s=0.02)
        first = advance_recovery(0.8, 10.0, rho_per_s=0.02)
        split = advance_recovery(first, 20.0, rho_per_s=0.02)
        self.assertAlmostEqual(whole, expected)
        self.assertAlmostEqual(split, whole)
        self.assertGreater(whole, 0.0)

    def test_zero_recovery_duration_or_rate(self):
        self.assertEqual(
            advance_recovery(0.8, 0.0, rho_per_s=0.02), 0.8
        )
        self.assertEqual(
            advance_recovery(0.8, 30.0, rho_per_s=0.0), 0.8
        )

    def test_invalid_work_inputs_rejected(self):
        for change in (
            {"fatigue": -0.1},
            {"fatigue": 1.25},
            {"duration_s": -1.0},
            {"alpha_per_s": -0.1},
            {"beta": -1.0},
            {"demand": 1.1},
            {"step_size_s": 0.0},
            {"step_size_s": float("nan")},
            {"duration_s": float("inf")},
            {"alpha_per_s": True},
        ):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self.work(**change)

    def test_invalid_recovery_inputs_rejected(self):
        for fatigue, duration, rho in (
            (1.25, 10.0, 0.02),
            (-0.1, 10.0, 0.02),
            (0.8, -1.0, 0.02),
            (0.8, 10.0, -0.02),
            (0.8, float("nan"), 0.02),
            (0.8, 10.0, float("inf")),
        ):
            with self.subTest(
                fatigue=fatigue, duration=duration, rho=rho
            ):
                with self.assertRaises(ValueError):
                    advance_recovery(
                        fatigue, duration, rho_per_s=rho
                    )


if __name__ == "__main__":
    unittest.main()