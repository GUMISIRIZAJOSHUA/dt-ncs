import random
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import test_scheduler_disturbances as fixtures
from src import scheduler


class TestExecutionResourceLookup(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.TestSchedulerDisturbances()
        self.case.setUp()
        self.scenario = self.case.scenario
        self.config = self.case.config

    def select(self):
        with patch.object(
            scheduler, "get_score", return_value=1.0
        ), patch.object(
            scheduler,
            "evaluate_safety",
            return_value=SimpleNamespace(is_safe=True),
        ):
            assignment, _ = scheduler.select_assignment(
                "B3",
                self.scenario,
                0.0,
                self.config,
                random.Random(123),
                arm_config=self.case.arm_config,
            )
        return assignment

    def check_execution_targets(self):
        assignment = self.select()
        operator = next(
            item for item in self.scenario.operators
            if item.operator_id == assignment.operator_id
        )
        robot = next(
            item for item in self.scenario.robots
            if item.robot_id == assignment.robot_id
        )
        task = scheduler.get_task(self.scenario, assignment.task_id)
        before_energy = robot.energy_used_kj

        with patch.object(scheduler, "apply_fatigue_update") as update:
            scheduler.execute_assignment(
                assignment,
                self.scenario,
                self.config,
                random.Random(123),
            )

        update.assert_called_once()
        self.assertIs(update.call_args.args[0], operator)
        self.assertAlmostEqual(
            robot.energy_used_kj,
            before_energy + task.robot_energy_kj,
        )
        self.assertIn(task.task_id, operator.completed_tasks)
        self.assertIn(task.task_id, robot.completed_tasks)
        self.assertIn(
            assignment.job_id, self.scenario.completed_job_ids
        )

        for other in self.scenario.operators:
            if other is not operator:
                self.assertEqual(other.completed_tasks, [])
        for other in self.scenario.robots:
            if other is not robot:
                self.assertEqual(other.completed_tasks, [])
                self.assertEqual(other.energy_used_kj, 0.0)

    def check_rejected_without_mutation(self, assignment):
        before = deepcopy(self.scenario)
        with patch.object(scheduler, "apply_fatigue_update") as update:
            with self.assertRaises(ValueError):
                scheduler.execute_assignment(
                    assignment,
                    self.scenario,
                    self.config,
                    random.Random(123),
                )
        update.assert_not_called()
        self.assertEqual(self.scenario, before)

    def test_reordered_resources_update_selected_ids(self):
        self.scenario.operators.reverse()
        self.scenario.robots.reverse()
        self.check_execution_targets()

    def test_noncontiguous_ids_update_selected_resources(self):
        for index, operator in enumerate(self.scenario.operators):
            operator.operator_id = 10 + 20 * index
        for index, robot in enumerate(self.scenario.robots):
            robot.robot_id = 20 + 20 * index
        self.check_execution_targets()

    def test_run_shift_supports_noncontiguous_resource_ids(self):
        for index, operator in enumerate(self.scenario.operators):
            operator.operator_id = 10 + 20 * index
        for index, robot in enumerate(self.scenario.robots):
            robot.robot_id = 20 + 20 * index

        selected_operator = self.scenario.operators[0]
        selected_robot = self.scenario.robots[0]

        with patch.object(
            scheduler, "get_score", return_value=1.0
        ), patch.object(
            scheduler,
            "evaluate_safety",
            return_value=SimpleNamespace(is_safe=True),
        ), patch.object(
            scheduler, "apply_fatigue_update"
        ) as update:
            result = scheduler.run_shift(
                "B3",
                self.scenario,
                self.config,
                123,
                arm_config=self.case.arm_config,
            )

        self.assertEqual(result.completed_tasks, 1)
        self.assertEqual(result.termination_reason, "backlog_exhausted")
        assignment = result.assignments[0]
        self.assertEqual(assignment.operator_id, selected_operator.operator_id)
        self.assertEqual(assignment.robot_id, selected_robot.robot_id)
        update.assert_called_once()
        self.assertIs(update.call_args.args[0], selected_operator)
        self.assertIn(assignment.task_id, selected_operator.completed_tasks)
        self.assertIn(assignment.task_id, selected_robot.completed_tasks)
        self.assertAlmostEqual(selected_robot.energy_used_kj, assignment.energy_kj)

    def test_unknown_operator_rejected_without_mutation(self):
        assignment = self.select()
        assignment.operator_id = 999
        self.check_rejected_without_mutation(assignment)

    def test_unknown_robot_rejected_without_mutation(self):
        assignment = self.select()
        assignment.robot_id = 999
        self.check_rejected_without_mutation(assignment)

    def test_duplicate_target_id_rejected_without_mutation(self):
        assignment = self.select()
        operator = next(
            item for item in self.scenario.operators
            if item.operator_id == assignment.operator_id
        )
        self.scenario.operators.append(deepcopy(operator))
        self.check_rejected_without_mutation(assignment)


if __name__ == "__main__":
    unittest.main()