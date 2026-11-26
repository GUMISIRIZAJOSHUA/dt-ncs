import unittest
from dataclasses import asdict

from src.disturbances import generate_disturbance_events
from src.resource_state import calculate_resource_state
from src.scenario import Operator, Robot


class TestDisturbanceGeneration(unittest.TestCase):
    def setUp(self):
        self.config = {
            "shift_duration_s": 28800,
            "disturbances_per_shift": 12,
            "disturbance_types": [
                "operator_absence",
                "robot_degradation",
            ],
        }

    def generate(self, config=None, operators=(3, 7), robots=(4, 9)):
        return generate_disturbance_events(
            self.config if config is None else config,
            123,
            operator_ids=operators,
            robot_ids=robots,
        )

    def test_fixed_inputs_reproduce_events(self):
        self.assertEqual(self.generate(), self.generate())

    def test_resource_input_order_does_not_change_events(self):
        self.assertEqual(
            self.generate(),
            self.generate(operators=(7, 3), robots=(9, 4)),
        )

    def test_count_unique_ids_order_and_targets(self):
        events = self.generate()
        self.assertEqual(len(events), 12)
        self.assertEqual(
            {event.event_id for event in events},
            set(range(1, 13)),
        )
        self.assertEqual(
            events,
            sorted(events, key=lambda event: (
                event.start_time_s, event.event_id
            )),
        )
        for event in events:
            with self.subTest(event_id=event.event_id):
                valid = (
                    {3, 7}
                    if event.event_type == "operator_absence"
                    else {4, 9}
                )
                self.assertIn(event.target_resource_id, valid)
                self.assertGreaterEqual(event.start_time_s, 28800 * 0.15)
                self.assertLessEqual(event.start_time_s, 28800 * 0.85)
                self.assertGreaterEqual(event.duration_s, 300.0)
                self.assertLessEqual(event.duration_s, 900.0)
                self.assertGreaterEqual(event.severity, 0.3)
                self.assertLessEqual(event.severity, 0.8)
                self.assertIn("target_resource_id", asdict(event))

    def test_missing_or_unsupported_types_rejected(self):
        for kinds in (None, [], ["material_shortage"], ["quality_alert"]):
            with self.subTest(kinds=kinds):
                config = dict(self.config)
                if kinds is None:
                    config.pop("disturbance_types")
                else:
                    config["disturbance_types"] = kinds
                with self.assertRaises(ValueError):
                    self.generate(config)

    def test_missing_required_resource_pool_rejected(self):
        with self.assertRaises(ValueError):
            self.generate(operators=())
        with self.assertRaises(ValueError):
            self.generate(robots=())

    def test_invalid_counts_rejected(self):
        for count in (-1, True, 1.5, "2"):
            with self.subTest(count=count):
                config = dict(self.config, disturbances_per_shift=count)
                with self.assertRaises(ValueError):
                    self.generate(config)

    def test_zero_count_needs_no_event_type_selection(self):
        config = {
            "shift_duration_s": 28800,
            "disturbances_per_shift": 0,
        }
        self.assertEqual(self.generate(config), [])

    def test_invalid_resource_ids_rejected(self):
        for ids in ((3, 3), (True,), (0,), ("3",)):
            with self.subTest(ids=ids):
                with self.assertRaises(ValueError):
                    self.generate(operators=ids)

    def test_generated_events_work_with_resource_state(self):
        operators = [
            Operator(3, "Operator 3", 1.0, 1.0),
            Operator(7, "Operator 7", 1.0, 1.0),
        ]
        robots = [
            Robot(4, "Robot 4", 1.0, 100.0),
            Robot(9, "Robot 9", 1.0, 100.0),
        ]
        events = self.generate()

        for event in events:
            with self.subTest(event_id=event.event_id):
                state = calculate_resource_state(
                    operators, robots, [event], event.start_time_s
                )
                if event.event_type == "operator_absence":
                    self.assertEqual(
                        state.unavailable_operator_ids,
                        frozenset({event.target_resource_id}),
                    )
                else:
                    self.assertAlmostEqual(
                        state.effective_robot_speeds[
                            event.target_resource_id
                        ],
                        1.0 - event.severity * 0.20,
                    )

        self.assertEqual([r.base_speed for r in robots], [1.0, 1.0])
        self.assertEqual([o.base_skill for o in operators], [1.0, 1.0])


if __name__ == "__main__":
    unittest.main()