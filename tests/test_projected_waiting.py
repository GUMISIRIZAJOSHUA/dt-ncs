import math
import unittest
from types import SimpleNamespace
from src.fatigue_adapter import FatigueAdapter
from src.projected_waiting import find_projected_recovery_delay

class TestProjectedWaiting(unittest.TestCase):
    def setUp(self):
        # Synthetic verification inputs only.
        raw = dict(step_size_s=0.5, operators={2: dict(initial_fatigue=0.0, alpha_per_s=0.02, beta=0.0, rho_per_s=0.02, fatigue_limit=0.8)}, task_demands={30: 1.0})
        self.adapter = FatigueAdapter(raw, operator_ids=[2], task_ids=[30])
        self.operator = SimpleNamespace(operator_id=2, fatigue_level=0.79)
        self.robot = SimpleNamespace(robot_id=1)
        self.task = SimpleNamespace(task_id=30, cognitive_load=0.0)
        self.config = dict(fatigue_critical_threshold=0.8, ergonomic_critical_threshold=0.8, collision_critical_threshold=0.8, safe_zone_critical_threshold=0.8)

    def delay(self, maximum=10.0, duration=1.0):
        return find_projected_recovery_delay(self.operator, self.task, self.robot, self.config, maximum, adapter=self.adapter, duration_s=duration)

    def test_safe_start_still_requires_rest_for_work(self):
        delay = self.delay()
        self.assertIsNotNone(delay)
        self.assertGreater(delay, 0.0)
        self.assertAlmostEqual(delay, math.log(0.79 / 0.78) / 0.02, places=9)
        self.assertEqual(self.operator.fatigue_level, 0.79)
        self.adapter.apply_recovery(self.operator, delay)
        self.assertTrue(self.adapter.is_work_feasible(self.operator, 30, 1.0))

    def test_ergonomic_constraint_can_require_additional_rest(self):
        self.config["ergonomic_critical_threshold"] = 0.5
        delay = self.delay()
        target_start = 0.5 / 0.65 - 0.02
        self.assertIsNotNone(delay)
        self.assertAlmostEqual(delay, math.log(0.79 / target_start) / 0.02, places=9)
        self.assertEqual(self.operator.fatigue_level, 0.79)

    def test_insufficient_window_and_impossible_work(self):
        self.assertIsNone(self.delay(maximum=0.1))
        self.operator.fatigue_level = 0.0
        self.assertIsNone(self.delay(maximum=100.0, duration=50.0))

    def test_geometry_failure_cannot_be_fixed_by_rest(self):
        self.robot.robot_id = 2
        self.assertIsNone(self.delay(maximum=100.0))
        self.assertEqual(self.operator.fatigue_level, 0.79)

if __name__ == "__main__":
    unittest.main()
