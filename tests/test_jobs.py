import unittest

from src.jobs import build_backlog


class TestBuildBacklog(unittest.TestCase):
    def test_one_job_per_type(self):
        ids = list(range(1, 13))
        jobs = build_backlog(ids, {task_id: 1 for task_id in ids})

        self.assertEqual(len(jobs), 12)
        self.assertEqual(len({job.job_id for job in jobs}), 12)
        self.assertEqual([job.task_type_id for job in jobs], ids)

    def test_multiple_instances_of_same_type(self):
        jobs = build_backlog([1, 2], {1: 3, 2: 2})

        self.assertEqual([job.job_id for job in jobs], [1, 2, 3, 4, 5])
        self.assertEqual(
            [job.task_type_id for job in jobs],
            [1, 1, 1, 2, 2],
        )

    def test_zero_quantity(self):
        jobs = build_backlog([1, 2], {1: 0, 2: 2})

        self.assertEqual([job.task_type_id for job in jobs], [2, 2])

    def test_empty_backlog(self):
        self.assertEqual(build_backlog([1, 2], {1: 0, 2: 0}), [])
        self.assertEqual(build_backlog([], {}), [])

    def test_order_is_independent_of_input_order(self):
        first = build_backlog([2, 1], {2: 2, 1: 1})
        second = build_backlog([1, 2], {1: 1, 2: 2})

        self.assertEqual(first, second)

    def test_duplicate_task_type_ids_rejected(self):
        with self.assertRaises(ValueError):
            build_backlog([1, 1], {1: 2})

    def test_missing_or_unknown_quantities_rejected(self):
        for quantities in ({1: 1}, {1: 1, 2: 1, 3: 1}):
            with self.subTest(quantities=quantities):
                with self.assertRaises(ValueError):
                    build_backlog([1, 2], quantities)

    def test_invalid_quantities_rejected(self):
        for quantity in (-1, 1.5, True, "2", None):
            with self.subTest(quantity=quantity):
                with self.assertRaises(ValueError):
                    build_backlog([1], {1: quantity})

    def test_invalid_task_type_ids_rejected(self):
        for task_id in (0, -1, 1.5, True, "1", None):
            with self.subTest(task_id=task_id):
                with self.assertRaises(ValueError):
                    build_backlog([task_id], {task_id: 1})

    def test_noninteger_quantity_keys_rejected(self):
        for key in ("1", 1.0, True):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    build_backlog([1], {key: 1})


if __name__ == "__main__":
    unittest.main()