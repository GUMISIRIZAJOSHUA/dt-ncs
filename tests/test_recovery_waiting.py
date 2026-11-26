import unittest
from copy import deepcopy
from types import SimpleNamespace

from src.fatigue import apply_recovery, calculate_ergonomic_risk
from src.recovery_waiting import find_safe_recovery_delay
from src.safety import evaluate_safety


class TestRecoveryWaiting(unittest.TestCase):
    def setUp(self):
        # IDs 2 and 1 give zero collision and safe-zone risks
        # under the currently implemented geometry functions.
        self.operator = SimpleNamespace(
            operator_id=2,
            fatigue_level=0.9,
        )
        self.robot = SimpleNamespace(robot_id=1)
        self.task = SimpleNamespace(cognitive_load=0.1)
        self.config = {
            "fatigue_critical_threshold": 0.8,
            "ergonomic_critical_threshold": 0.8,
            "collision_critical_threshold": 0.8,
            "safe_zone_critical_threshold": 0.8,
        }

    def delay(self, limit=100.0):
        return find_safe_recovery_delay(
            self.operator,
            self.task,
            self.robot,
            self.config,
            limit,
        )

    def test_fatigue_threshold_recovery_and_no_mutation(self):
        before = deepcopy(self.operator.__dict__)
        delay = self.delay()
        self.assertIsNotNone(delay)
        self.assertAlmostEqual(delay, (0.9 - 0.8) / 0.015)
        self.assertEqual(self.operator.__dict__, before)

        probe = deepcopy(self.operator)
        apply_recovery(probe, delay, self.config)
        self.assertTrue(
            evaluate_safety(
                probe.fatigue_level,
                calculate_ergonomic_risk(
                    probe.fatigue_level, self.task.cognitive_load
                ),
                0.0,
                0.0,
                self.config,
            ).is_safe
        )

    def test_already_safe_returns_zero(self):
        self.operator.fatigue_level = 0.7
        self.assertEqual(self.delay(), 0.0)

    def test_insufficient_rest_returns_none(self):
        self.assertIsNone(self.delay(limit=1.0))

    def test_ergonomic_threshold_can_require_more_rest(self):
        self.task.cognitive_load = 0.5
        self.config["ergonomic_critical_threshold"] = 0.3
        target_fatigue = (0.3 - 0.35 * 0.5) / 0.65
        expected_delay = (0.9 - target_fatigue) / 0.015
        self.assertAlmostEqual(self.delay(), expected_delay)

    def test_collision_failure_is_not_cured_by_rest(self):
        self.robot.robot_id = 2
        self.assertIsNone(self.delay())

    def test_task_ergonomic_floor_is_not_cured_by_rest(self):
        self.task.cognitive_load = 1.0
        self.config["ergonomic_critical_threshold"] = 0.2
        self.assertIsNone(self.delay())

    def test_invalid_limits_rejected(self):
        for limit in (-1.0, float("nan"), float("inf")):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    self.delay(limit)


if __name__ == "__main__":
    unittest.main()