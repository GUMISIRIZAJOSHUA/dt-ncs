import unittest

from src.fatigue import calculate_ergonomic_risk


class TestErgonomicFiniteInputs(unittest.TestCase):
    def test_nonfinite_fatigue_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError, "^fatigue_level must be finite$"
                ):
                    calculate_ergonomic_risk(value, 0.2)

    def test_nonfinite_cognitive_load_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError, "^cognitive_load must be finite$"
                ):
                    calculate_ergonomic_risk(0.2, value)

    def test_finite_weighted_formula_preserved(self):
        self.assertAlmostEqual(
            calculate_ergonomic_risk(0.4, 0.6),
            0.65 * 0.4 + 0.35 * 0.6,
        )

    def test_finite_clamping_preserved(self):
        for fatigue, cognitive, expected in (
            (-1.0, -1.0, 0.0),
            (0.0, 0.0, 0.0),
            (1.0, 1.0, 1.0),
            (2.0, 2.0, 1.0),
        ):
            with self.subTest(fatigue=fatigue, cognitive=cognitive):
                self.assertEqual(
                    calculate_ergonomic_risk(fatigue, cognitive),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
