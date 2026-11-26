import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.projected_safety import assess_projected_work


class TestProjectedSafetyFiniteInputs(unittest.TestCase):
    def setUp(self):
        # Synthetic verification inputs only; not experiment defaults.
        self.operator = SimpleNamespace(operator_id=10)
        self.task = SimpleNamespace(task_id=30, cognitive_load=0.0)
        self.config = dict(
            fatigue_critical_threshold=0.8,
            ergonomic_critical_threshold=0.8,
            collision_critical_threshold=0.8,
            safe_zone_critical_threshold=0.8,
        )
        self.parameters = SimpleNamespace(fatigue_limit=0.7)
        self.adapter = SimpleNamespace(
            parameters=SimpleNamespace(
                operators={10: self.parameters}
            ),
            project_work=Mock(
                return_value=SimpleNamespace(maximum_fatigue=0.2)
            ),
        )

    def assess(self):
        return assess_projected_work(
            self.operator,
            self.task,
            1.0,
            self.config,
            0.0,
            0.0,
            self.adapter,
        )

    def test_nonfinite_global_limits_rejected_before_projection(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                self.config["fatigue_critical_threshold"] = value
                with self.assertRaisesRegex(
                    ValueError,
                    "^fatigue_critical_threshold must be finite$",
                ):
                    self.assess()
                self.adapter.project_work.assert_not_called()

    def test_nonfinite_operator_limits_rejected_before_projection(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                self.parameters.fatigue_limit = value
                with self.assertRaisesRegex(
                    ValueError,
                    "^operator fatigue_limit must be finite$",
                ):
                    self.assess()
                self.adapter.project_work.assert_not_called()

    def test_finite_limits_allow_projection_without_config_mutation(self):
        before = dict(self.config)

        assessment = self.assess()

        self.assertTrue(assessment.is_safe)
        self.assertEqual(self.config, before)
        self.adapter.project_work.assert_called_once_with(
            self.operator,
            self.task.task_id,
            1.0,
        )


    def test_nonfinite_projected_fatigue_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                self.adapter.project_work.reset_mock()
                self.adapter.project_work.return_value.maximum_fatigue = value

                with self.assertRaisesRegex(
                    ValueError, "^fatigue_level must be finite$"
                ):
                    self.assess()

                self.adapter.project_work.assert_called_once_with(
                    self.operator, self.task.task_id, 1.0
                )

    def test_nonfinite_cognitive_load_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                self.adapter.project_work.reset_mock()
                self.task.cognitive_load = value

                with self.assertRaisesRegex(
                    ValueError, "^cognitive_load must be finite$"
                ):
                    self.assess()

                self.adapter.project_work.assert_called_once_with(
                    self.operator, self.task.task_id, 1.0
                )


if __name__ == "__main__":
    unittest.main()
