import unittest

from src.safety import evaluate_safety


class TestSafetyFiniteInputs(unittest.TestCase):
    def setUp(self):
        self.risks = (
            "fatigue_level", "ergonomic_risk",
            "collision_risk", "safe_zone_risk",
        )
        self.keys = (
            "fatigue_critical_threshold",
            "ergonomic_critical_threshold",
            "collision_critical_threshold",
            "safe_zone_critical_threshold",
        )
        self.config = dict.fromkeys(self.keys, 0.5)

    def test_nonfinite_risks_rejected(self):
        for index, name in enumerate(self.risks):
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(name=name, value=value):
                    values = [0.0] * 4
                    values[index] = value
                    with self.assertRaises(ValueError) as caught:
                        evaluate_safety(*values, self.config)
                    self.assertEqual(str(caught.exception), name + " must be finite")

    def test_nonfinite_thresholds_rejected(self):
        for name in self.keys:
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(name=name, value=value):
                    config = dict(self.config)
                    config[name] = value
                    with self.assertRaises(ValueError) as caught:
                        evaluate_safety(0.0, 0.0, 0.0, 0.0, config)
                    self.assertEqual(str(caught.exception), name + " must be finite")

    def test_equal_thresholds_remain_safe(self):
        result = evaluate_safety(0.5, 0.5, 0.5, 0.5, self.config)
        self.assertTrue(result.is_safe)
        self.assertEqual(result.violations, [])
        self.assertEqual(result.minimum_margin, 0.0)

    def test_finite_exceedances_preserve_details(self):
        result = evaluate_safety(0.75, 1.0, 0.5, 0.0, self.config)
        self.assertFalse(result.is_safe)
        self.assertEqual(
            [(v.violation_type, v.value, v.threshold, v.margin) for v in result.violations],
            [("fatigue", 0.75, 0.5, 0.25), ("ergonomic", 1.0, 0.5, 0.5)],
        )
        self.assertEqual(result.minimum_margin, 0.25)


if __name__ == "__main__":
    unittest.main()
