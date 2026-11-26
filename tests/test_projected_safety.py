import unittest
from types import SimpleNamespace
from src.fatigue_adapter import FatigueAdapter
from src.projected_safety import assess_projected_work

class TestProjectedSafety(unittest.TestCase):
    def setUp(self):
        # Synthetic verification inputs only.
        self.raw = dict(step_size_s=0.5, operators={10: dict(initial_fatigue=0.0, alpha_per_s=0.02, beta=0.0, rho_per_s=0.02, fatigue_limit=0.8)}, task_demands={30: 1.0})
        self.operator = SimpleNamespace(operator_id=10, fatigue_level=0.79)
        self.task = SimpleNamespace(task_id=30, cognitive_load=0.0)
        self.config = dict(fatigue_critical_threshold=0.8, ergonomic_critical_threshold=0.8, collision_critical_threshold=0.8, safe_zone_critical_threshold=0.8)

    def assess(self):
        adapter = FatigueAdapter(self.raw, operator_ids=[10], task_ids=[30])
        return assess_projected_work(self.operator, self.task, 1.0, self.config, 0.0, 0.0, adapter)

    def test_safe_start_unsafe_finish_is_rejected_without_mutation(self):
        before = dict(self.config)
        assessment = self.assess()
        self.assertFalse(assessment.is_safe)
        self.assertIn("fatigue", [v.violation_type for v in assessment.violations])
        self.assertEqual(self.operator.fatigue_level, 0.79)
        self.assertEqual(self.config, before)

    def test_stricter_operator_and_global_limits_are_both_respected(self):
        self.operator.fatigue_level = 0.7
        self.raw["operators"][10]["fatigue_limit"] = 0.71
        self.assertFalse(self.assess().is_safe)
        self.raw["operators"][10]["fatigue_limit"] = 0.9
        self.config["fatigue_critical_threshold"] = 0.71
        self.assertFalse(self.assess().is_safe)
        self.config["fatigue_critical_threshold"] = 0.8
        self.assertTrue(self.assess().is_safe)

    def test_task_ergonomics_can_reject_fatigue_feasible_work(self):
        self.operator.fatigue_level = 0.7
        self.task.cognitive_load = 1.0
        assessment = self.assess()
        self.assertFalse(assessment.is_safe)
        kinds = [v.violation_type for v in assessment.violations]
        self.assertIn("ergonomic", kinds)
        self.assertNotIn("fatigue", kinds)

if __name__ == "__main__":
    unittest.main()
