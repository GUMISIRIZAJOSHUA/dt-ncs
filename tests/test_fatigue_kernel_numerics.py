import math
import unittest

from src.fatigue_kernel import advance_recovery, advance_work


class TestFatigueKernelNumerics(unittest.TestCase):
    def project(self, fatigue, duration, step, alpha=0.1, beta=1.0):
        return advance_work(
            fatigue,
            duration,
            alpha_per_s=alpha,
            beta=beta,
            demand=1.0,
            step_size_s=step,
        )

    def test_zero_beta_matches_unclipped_linear_solution(self):
        initial = 0.2
        duration = 2.7
        alpha = 0.03
        expected = initial + alpha * duration

        for step in (1.0, 0.5, 0.1):
            with self.subTest(step=step):
                result = self.project(
                    initial, duration, step, alpha=alpha, beta=0.0
                )
                self.assertAlmostEqual(result.final_fatigue, expected)
                self.assertAlmostEqual(result.maximum_fatigue, expected)

    def test_step_refinement_approaches_continuous_benchmark(self):
        initial = 0.2
        duration = 2.0
        alpha = 0.1
        beta = 1.0
        exact = (
            (initial + 1.0 / beta)
            * math.exp(alpha * beta * duration)
            - 1.0 / beta
        )

        results = [
            self.project(initial, duration, step, alpha, beta)
            for step in (1.0, 0.5, 0.1)
        ]
        errors = [
            abs(result.final_fatigue - exact)
            for result in results
        ]

        self.assertLess(errors[1], errors[0])
        self.assertLess(errors[2], errors[1])
        for result in results:
            self.assertLess(result.final_fatigue, exact)
            self.assertAlmostEqual(
                result.maximum_fatigue, result.final_fatigue
            )

    def test_safe_start_can_have_infeasible_work_trajectory(self):
        limit = 0.8
        initial = 0.79
        result = self.project(
            initial, 1.0, 1.0, alpha=0.02, beta=0.0
        )

        self.assertLess(initial, limit)
        self.assertAlmostEqual(result.final_fatigue, 0.81)
        self.assertGreater(result.maximum_fatigue, limit)

    def test_rest_can_make_same_assignment_feasible(self):
        limit = 0.8
        initial = 0.79
        rested = advance_recovery(
            initial, 10.0, rho_per_s=0.02
        )

        before = self.project(
            initial, 1.0, 1.0, alpha=0.02, beta=0.0
        )
        after = self.project(
            rested, 1.0, 1.0, alpha=0.02, beta=0.0
        )

        self.assertGreater(before.maximum_fatigue, limit)
        self.assertLess(after.maximum_fatigue, limit)
        self.assertAlmostEqual(
            after.final_fatigue,
            initial * math.exp(-0.02 * 10.0) + 0.02,
        )

    def test_splitting_at_existing_step_boundary_preserves_result(self):
        whole = self.project(0.2, 2.5, 1.0)
        first = self.project(0.2, 1.0, 1.0)
        second = self.project(first.final_fatigue, 1.5, 1.0)

        self.assertAlmostEqual(
            whole.final_fatigue, second.final_fatigue
        )
        self.assertAlmostEqual(
            whole.maximum_fatigue,
            max(first.maximum_fatigue, second.maximum_fatigue),
        )


if __name__ == "__main__":
    unittest.main()