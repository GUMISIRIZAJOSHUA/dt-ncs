import unittest
from copy import deepcopy

from src.fatigue_parameters import bind_fatigue_parameters


class TestFatigueParameters(unittest.TestCase):
    def setUp(self):
        # Synthetic verification values only.
        self.raw = {
            "step_size_s": 0.5,
            "operators": {
                10: {
                    "initial_fatigue": 0.2,
                    "alpha_per_s": 0.01,
                    "beta": 0.5,
                    "rho_per_s": 0.02,
                    "fatigue_limit": 0.8,
                }
            },
            "task_demands": {30: 0.4},
        }

    def bind(self, raw=None, operator_ids=(10,), task_ids=(30,)):
        return bind_fatigue_parameters(
            self.raw if raw is None else raw,
            operator_ids=operator_ids,
            task_ids=task_ids,
        )

    def test_explicit_values_bound_by_id(self):
        bound = self.bind()
        self.assertEqual(bound.step_size_s, 0.5)
        self.assertEqual(bound.operators[10].initial_fatigue, 0.2)
        self.assertEqual(bound.operators[10].alpha_per_s, 0.01)
        self.assertEqual(bound.operators[10].beta, 0.5)
        self.assertEqual(bound.operators[10].rho_per_s, 0.02)
        self.assertEqual(bound.operators[10].fatigue_limit, 0.8)
        self.assertEqual(bound.task_demands[30], 0.4)

    def test_binding_does_not_mutate_input(self):
        before = deepcopy(self.raw)
        self.bind()
        self.assertEqual(self.raw, before)

    def test_bound_values_are_copied_and_mappings_read_only(self):
        bound = self.bind()
        self.raw["operators"][10]["alpha_per_s"] = 99.0
        self.raw["task_demands"][30] = 0.9

        self.assertEqual(bound.operators[10].alpha_per_s, 0.01)
        self.assertEqual(bound.task_demands[30], 0.4)
        with self.assertRaises(TypeError):
            bound.task_demands[30] = 0.7
        with self.assertRaises(TypeError):
            bound.operators[10] = None

    def test_missing_or_extra_operator_fields_rejected(self):
        for field in tuple(self.raw["operators"][10]):
            raw = deepcopy(self.raw)
            del raw["operators"][10][field]
            with self.subTest(missing=field):
                with self.assertRaises(ValueError):
                    self.bind(raw)

        raw = deepcopy(self.raw)
        raw["operators"][10]["base_skill"] = 1.0
        with self.assertRaises(ValueError):
            self.bind(raw)

    def test_operator_and_task_coverage_must_match(self):
        for operators, tasks in (
            ((10, 20), (30,)),
            ((), (30,)),
            ((10,), (30, 40)),
            ((10,), ()),
        ):
            with self.subTest(operators=operators, tasks=tasks):
                with self.assertRaises(ValueError):
                    self.bind(
                        operator_ids=operators,
                        task_ids=tasks,
                    )

    def test_duplicate_or_noninteger_ids_rejected(self):
        for ids in ((10, 10), ("10",), (True,), (0,)):
            with self.subTest(ids=ids):
                with self.assertRaises(ValueError):
                    self.bind(operator_ids=ids)

        raw = deepcopy(self.raw)
        raw["task_demands"] = {"30": 0.4}
        with self.assertRaises(ValueError):
            self.bind(raw)

    def test_invalid_numeric_parameters_rejected(self):
        cases = (
            ("initial_fatigue", -0.1),
            ("initial_fatigue", 1.1),
            ("alpha_per_s", -0.01),
            ("beta", -1.0),
            ("rho_per_s", float("nan")),
            ("fatigue_limit", 1.1),
            ("fatigue_limit", True),
        )
        for field, value in cases:
            raw = deepcopy(self.raw)
            raw["operators"][10][field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    self.bind(raw)

        for field, value in (
            ("step_size_s", 0.0),
            ("step_size_s", float("inf")),
            ("task_demands", {30: 1.1}),
            ("task_demands", {30: True}),
        ):
            raw = deepcopy(self.raw)
            raw[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    self.bind(raw)

    def test_legacy_configuration_is_not_a_fallback(self):
        with self.assertRaises(ValueError):
            self.bind({
                "fatigue_update_rate_hz": 1,
                "fatigue_critical_threshold": 0.8,
            })


if __name__ == "__main__":
    unittest.main()