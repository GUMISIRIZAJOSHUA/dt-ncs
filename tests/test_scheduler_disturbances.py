import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src import scheduler
from src.jobs import build_backlog
from src.scenario import Operator, Robot, Scenario, Task


class TestSchedulerDisturbances(unittest.TestCase):
    def setUp(self):
        self.config = {
            "weights": {
                "productivity": 0.25,
                "quality": 0.15,
                "wellbeing": 0.25,
                "sustainability": 0.20,
                "collaboration": 0.15,
            },
        }
        self.arm_config = {
            "veto": True,
            "objective": "weighted_sum",
        }
        self.scenario = Scenario(
            scenario_id=1,
            shift_duration_s=100.0,
            tasks=[
                Task(
                    task_id=1,
                    name="Verification task",
                    manual_time_s=10.0,
                    robot_time_s=20.0,
                    fatigue_coefficient=0.01,
                    cognitive_load=0.1,
                    robot_energy_kj=5.0,
                    defect_risk=0.01,
                )
            ],
            operators=[
                Operator(1, "Operator 1", 1.0, 1.0),
                Operator(2, "Operator 2", 1.0, 1.0),
            ],
            robots=[
                Robot(1, "Robot 1", 1.0, 100.0),
                Robot(2, "Robot 2", 0.5, 100.0),
            ],
            jobs=build_backlog([1], {1: 1}),
        )

    def event(self, kind, target, severity=1.0):
        return SimpleNamespace(
            event_type=kind,
            target_resource_id=target,
            start_time_s=0.0,
            duration_s=30.0,
            severity=severity,
        )

    def select(self, time=0.0):
        # Isolate disturbance integration from scoring and safety policy.
        with patch.object(
            scheduler, "get_score", return_value=1.0
        ), patch.object(
            scheduler,
            "evaluate_safety",
            return_value=SimpleNamespace(is_safe=True),
        ):
            return scheduler.select_assignment(
                "B3", self.scenario, time, self.config, random.Random(1),
                arm_config=self.arm_config,
            )[0]

    def test_absent_operator_excluded_and_returns_after_expiry(self):
        self.scenario.disturbance_events = [
            self.event("operator_absence", 1)
        ]
        self.assertEqual(self.select().operator_id, 2)
        self.assertEqual(self.select(30.0).operator_id, 1)
        self.assertEqual(self.scenario.operators[0].base_skill, 1.0)

    def test_all_operators_absent_produces_no_assignment(self):
        self.scenario.disturbance_events = [
            self.event("operator_absence", 1),
            self.event("operator_absence", 2),
        ]
        with self.assertRaises(RuntimeError):
            self.select()

    def test_degradation_changes_duration_without_compounding(self):
        self.scenario.disturbance_events = [
            self.event("robot_degradation", 1)
        ]
        first = self.select()
        second = self.select()

        self.assertEqual(first.robot_id, 1)
        self.assertAlmostEqual(first.duration_s, 25.0)
        self.assertAlmostEqual(first.completion_time_s, 25.0)
        self.assertEqual(first, second)
        self.assertEqual(
            [robot.base_speed for robot in self.scenario.robots],
            [1.0, 0.5],
        )
        self.assertAlmostEqual(self.select(30.0).duration_s, 20.0)

    def test_degraded_duration_used_for_horizon_filter(self):
        self.scenario.disturbance_events = [
            self.event("robot_degradation", 1)
        ]
        self.scenario.shift_duration_s = 24.0
        with self.assertRaises(RuntimeError):
            self.select()

        self.scenario.shift_duration_s = 25.0
        self.assertAlmostEqual(self.select().completion_time_s, 25.0)

    def test_objective_duration_matches_degraded_assignment(self):
        self.scenario.disturbance_events = [
            self.event("robot_degradation", 1)
        ]
        assignment = self.select()
        values = scheduler.get_objective_values(
            self.scenario.tasks[0],
            self.scenario.operators[0],
            self.scenario.robots[0],
            0.0,
            self.scenario,
            self.config,
        )
        self.assertAlmostEqual(
            values.productivity,
            1.0 - assignment.duration_s / self.scenario.shift_duration_s,
        )
        self.assertAlmostEqual(values.productivity, 0.75)


if __name__ == "__main__":
    unittest.main()