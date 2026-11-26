import math
import unittest

from src.fatigue_feasibility import (
    find_work_feasible_rest_delay,
    is_work_fatigue_feasible,
)
from src.fatigue_kernel import advance_recovery


class TestFatigueFeasibility(unittest.TestCase):
    def setUp(self):
        # Synthetic verification parameters, not experiment inputs.
        self.work = {
            "fatigue_limit": 0.8,
            "alpha_per_s": 0.02,
            "beta": 0.0,
            "demand": 1.0,
            "step_size_s": 1.0,
        }

    def feasible(self, fatigue, duration=1.0):
        return is_work_fatigue_feasible(
            fatigue, duration, **self.work
        )

    def rest_delay(self, fatigue=0.79, duration=1.0, **changes):
        parameters = {
            **self.work,
            "rho_per_s": 0.02,
            "max_delay_s": 10.0,
        }
        parameters.update(changes)
        return find_work_feasible_rest_delay(
            fatigue, duration, **parameters
        )

    def test_start_below_limit_can_still_be_infeasible(self):
        self.assertLess(0.79, self.work["fatigue_limit"])
        self.assertFalse(self.feasible(0.79))

    def test_exact_limit_allowed_but_exceedance_rejected(self):
        self.work["alpha_per_s"] = 0.0
        self.assertTrue(self.feasible(0.8))
        self.assertFalse(self.feasible(0.800001))

    def test_already_feasible_requires_no_rest(self):
        self.assertEqual(self.rest_delay(fatigue=0.7), 0.0)

    def test_rest_delay_matches_constant_accumulation_case(self):
        delay = self.rest_delay()
        self.assertIsNotNone(delay)

        # Work adds 0.02, so starting fatigue must be at most 0.78.
        expected = math.log(0.79 / 0.78) / 0.02
        self.assertAlmostEqual(delay, expected, places=9)

        rested = advance_recovery(
            0.79, delay, rho_per_s=0.02
        )
        self.assertTrue(self.feasible(rested))

        earlier = advance_recovery(
            0.79, delay - 0.0001, rho_per_s=0.02
        )
        self.assertFalse(self.feasible(earlier))

    def test_insufficient_recovery_window_returns_none(self):
        self.assertIsNone(self.rest_delay(max_delay_s=0.5))

    def test_zero_recovery_rate_cannot_fix_infeasible_work(self):
        self.assertIsNone(self.rest_delay(rho_per_s=0.0))

    def test_work_infeasible_even_from_zero_cannot_be_fixed(self):
        self.work["alpha_per_s"] = 0.2
        self.assertFalse(self.feasible(0.0, duration=5.0))
        self.assertIsNone(
            self.rest_delay(duration=5.0, max_delay_s=100.0)
        )

    def test_invalid_parameters_rejected_even_when_already_feasible(self):
        for changes in (
            {"fatigue_limit": 1.1},
            {"fatigue_limit": float("nan")},
            {"fatigue_limit": True},
            {"rho_per_s": -0.01},
            {"max_delay_s": -1.0},
            {"max_delay_s": float("inf")},
            {"step_size_s": 0.0},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self.rest_delay(fatigue=0.1, **changes)


if __name__ == "__main__":
    unittest.main()