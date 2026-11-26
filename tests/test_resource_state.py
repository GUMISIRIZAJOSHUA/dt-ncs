import unittest
from types import SimpleNamespace

from src.resource_state import calculate_resource_state


class TestResourceState(unittest.TestCase):
    def setUp(self):
        self.operators = [
            SimpleNamespace(operator_id=1, base_skill=0.9),
            SimpleNamespace(operator_id=2, base_skill=1.0),
        ]
        self.robots = [
            SimpleNamespace(robot_id=1, base_speed=1.0),
            SimpleNamespace(robot_id=2, base_speed=0.9),
        ]

    def event(self, kind, target, severity=0.5):
        return SimpleNamespace(
            event_type=kind,
            target_resource_id=target,
            start_time_s=10.0,
            duration_s=20.0,
            severity=severity,
        )

    def state(self, events, time=10.0):
        return calculate_resource_state(
            self.operators, self.robots, events, time
        )

    def test_absence_targets_only_one_operator(self):
        state = self.state([self.event("operator_absence", 2)])
        self.assertEqual(state.unavailable_operator_ids, frozenset({2}))
        self.assertEqual(state.effective_robot_speeds, {1: 1.0, 2: 0.9})

    def test_degradation_is_targeted_repeatable_and_preserves_baselines(self):
        events = [self.event("robot_degradation", 1)]
        first = self.state(events)
        second = self.state(events)
        self.assertEqual(first, second)
        self.assertAlmostEqual(first.effective_robot_speeds[1], 0.9)
        self.assertEqual(first.effective_robot_speeds[2], 0.9)
        self.assertEqual([r.base_speed for r in self.robots], [1.0, 0.9])
        self.assertEqual([o.base_skill for o in self.operators], [0.9, 1.0])

    def test_event_boundaries_and_expiry(self):
        events = [
            self.event("operator_absence", 1),
            self.event("robot_degradation", 2),
        ]
        for time in (9.0, 30.0, 31.0):
            with self.subTest(time=time):
                state = self.state(events, time)
                self.assertFalse(state.unavailable_operator_ids)
                self.assertEqual(
                    state.effective_robot_speeds, {1: 1.0, 2: 0.9}
                )
        self.assertEqual(
            self.state(events, 10.0).unavailable_operator_ids,
            frozenset({1}),
        )
        self.assertAlmostEqual(
            self.state(events, 29.0).effective_robot_speeds[2], 0.8
        )

    def test_overlapping_degradation_uses_largest_reduction(self):
        events = [
            self.event("robot_degradation", 1, 0.3),
            self.event("robot_degradation", 1, 0.8),
        ]
        self.assertAlmostEqual(
            self.state(events).effective_robot_speeds[1], 0.84
        )
        self.assertEqual(self.state(events), self.state(list(reversed(events))))

    def test_unknown_or_missing_target_rejected(self):
        for target in (None, 99, True):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    self.state([self.event("operator_absence", target)])

    def test_unsupported_event_rejected_even_before_start(self):
        with self.assertRaises(ValueError):
            self.state([self.event("material_shortage", 1)], time=0.0)

    def test_invalid_severity_rejected(self):
        for severity in (-0.1, 1.1, float("nan")):
            with self.subTest(severity=severity):
                with self.assertRaises(ValueError):
                    self.state([
                        self.event("robot_degradation", 1, severity)
                    ])

    def test_speed_floor_never_increases_baseline(self):
        self.robots[0].base_speed = 0.2
        state = self.state([self.event("robot_degradation", 1)])
        self.assertEqual(state.effective_robot_speeds[1], 0.2)


if __name__ == "__main__":
    unittest.main()