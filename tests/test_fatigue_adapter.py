import math
import unittest
from copy import deepcopy
from types import SimpleNamespace
from src.fatigue_adapter import FatigueAdapter

class TestFatigueAdapter(unittest.TestCase):
    def setUp(self):
        # Synthetic verification values only; not experiment parameters.
        self.raw = dict(step_size_s=0.5, operators={10: dict(initial_fatigue=0.2, alpha_per_s=0.02, beta=0.0, rho_per_s=0.02, fatigue_limit=0.8)}, task_demands={30: 1.0})
        self.operator = SimpleNamespace(operator_id=10, fatigue_level=0.79)
        self.adapter = FatigueAdapter(self.raw, operator_ids=[10], task_ids=[30])

    def test_binding_does_not_mutate_or_initialize(self):
        before = deepcopy(self.raw)
        FatigueAdapter(self.raw, operator_ids=[10], task_ids=[30])
        self.assertEqual(self.raw, before)
        self.assertEqual(self.operator.fatigue_level, 0.79)

    def test_initialization_is_explicit_and_id_based(self):
        self.adapter.initialize([self.operator])
        self.assertEqual(self.operator.fatigue_level, 0.2)

    def test_invalid_initialization_does_not_mutate(self):
        unknown = SimpleNamespace(operator_id=20, fatigue_level=0.4)
        with self.assertRaises(ValueError):
            self.adapter.initialize([self.operator, unknown])
        self.assertEqual(self.operator.fatigue_level, 0.79)
        self.assertEqual(unknown.fatigue_level, 0.4)
        with self.assertRaises(ValueError):
            self.adapter.initialize([self.operator, self.operator])
        self.assertEqual(self.operator.fatigue_level, 0.79)

    def test_projection_and_feasibility_do_not_mutate(self):
        projection = self.adapter.project_work(self.operator, 30, 1.0)
        self.assertAlmostEqual(projection.final_fatigue, 0.81)
        self.assertFalse(self.adapter.is_work_feasible(self.operator, 30, 1.0))
        self.assertEqual(self.operator.fatigue_level, 0.79)

    def test_execution_matches_projection_even_without_veto(self):
        predicted = self.adapter.project_work(self.operator, 30, 1.0)
        executed = self.adapter.apply_work(self.operator, 30, 1.0)
        self.assertEqual(executed, predicted)
        self.assertEqual(self.operator.fatigue_level, predicted.final_fatigue)

    def test_recovery_uses_bound_exponential_rate(self):
        final = self.adapter.apply_recovery(self.operator, 10.0)
        self.assertAlmostEqual(final, 0.79 * math.exp(-0.02 * 10.0))
        self.assertEqual(self.operator.fatigue_level, final)

    def test_rest_delay_accounts_for_subsequent_work(self):
        delay = self.adapter.find_rest_delay(self.operator, 30, 1.0, 10.0)
        self.assertIsNotNone(delay)
        self.assertAlmostEqual(delay, math.log(0.79 / 0.78) / 0.02, places=9)
        self.assertEqual(self.operator.fatigue_level, 0.79)
        self.adapter.apply_recovery(self.operator, delay)
        self.assertTrue(self.adapter.is_work_feasible(self.operator, 30, 1.0))

    def test_invalid_execution_leaves_state_unchanged(self):
        with self.assertRaises(ValueError):
            self.adapter.apply_work(self.operator, 30, -1.0)
        self.assertEqual(self.operator.fatigue_level, 0.79)
        with self.assertRaises(ValueError):
            self.adapter.apply_recovery(self.operator, -1.0)
        self.assertEqual(self.operator.fatigue_level, 0.79)

    def test_unknown_task_leaves_state_unchanged(self):
        with self.assertRaises(KeyError):
            self.adapter.apply_work(self.operator, 999, 1.0)
        self.assertEqual(self.operator.fatigue_level, 0.79)

if __name__ == "__main__":
    unittest.main()
