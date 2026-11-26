"""Synthetic boundary inputs only; not experimental parameters."""

import random
import unittest
from types import SimpleNamespace

import test_projected_scheduler_integration as fixtures
from src import scheduler


class TestAdapterDegradationProjectedSafety(unittest.TestCase):
    def make_case(self, degraded):
        case = fixtures.TestProjectedSchedulerIntegration()
        scenario, config = case.make_case(
            horizon=10.0,
            duration=1.0,
            initial=0.778,
        )
        scenario.disturbance_events = []

        if degraded:
            scenario.disturbance_events.append(
                SimpleNamespace(
                    event_type="robot_degradation",
                    target_resource_id=1,
                    start_time_s=0.0,
                    duration_s=10.0,
                    severity=1.0,
                )
            )

        return scenario, config

    def select(self, scenario, config, veto=True):
        return scheduler.select_assignment(
            "synthetic_degradation_safety",
            scenario,
            0.0,
            config,
            random.Random(123),
            arm_config={
                "veto": veto,
                "objective": "productivity",
            },
        )

    def test_degradation_turns_safe_work_into_projected_rejection(self):
        baseline, baseline_config = self.make_case(degraded=False)
        degraded, degraded_config = self.make_case(degraded=True)

        # Baseline: 0.778 + 0.02 * 1.0 = 0.798, below 0.8.
        assignment, _ = self.select(baseline, baseline_config)
        self.assertEqual(assignment.operator_id, 2)
        self.assertEqual(assignment.robot_id, 1)
        self.assertAlmostEqual(assignment.duration_s, 1.0)
        self.assertFalse(assignment.safety_violation)

        # Degraded: 0.778 + 0.02 * 1.25 = 0.803, above 0.8.
        with self.assertRaises(
            scheduler.NoAssignmentAvailable
        ) as caught:
            self.select(degraded, degraded_config)

        self.assertEqual(
            caught.exception.reason,
            "no_safe_assignment",
        )

        # Without the veto, selection exposes the longer, flagged candidate.
        flagged, _ = self.select(
            degraded,
            degraded_config,
            veto=False,
        )
        self.assertAlmostEqual(flagged.duration_s, 1.25)
        self.assertTrue(flagged.safety_violation)

        # Selection and projection must not execute work or change fatigue.
        for scenario in (baseline, degraded):
            self.assertEqual(scenario.completed_job_ids, set())
            self.assertEqual(scenario.robots[0].base_speed, 1.0)
            self.assertAlmostEqual(
                scenario.robots[0].energy_used_kj,
                0.0,
            )
            for operator in scenario.operators:
                self.assertAlmostEqual(
                    operator.fatigue_level,
                    0.778,
                    places=12,
                )
                self.assertEqual(operator.completed_tasks, [])


if __name__ == "__main__":
    unittest.main()