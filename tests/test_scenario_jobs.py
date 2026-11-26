import unittest
from src.io_utils import load_yaml
from src.scenario import build_scenario

class TestScenarioJobs(unittest.TestCase):
    def make_config(self):
        config = load_yaml('configs/experiment.yaml')
        config.update(load_yaml('configs/tasks.yaml'))
        return config

    def test_verification_backlog(self):
        config = self.make_config()
        ids = [task['id'] for task in config['tasks']]
        config['job_quantities'] = {i: 1 for i in ids}
        scenario = build_scenario(config, 123, 1, [])
        self.assertEqual(len(scenario.jobs), 12)
        self.assertEqual([j.job_id for j in scenario.jobs], list(range(1, 13)))
        self.assertEqual([j.task_type_id for j in scenario.jobs], sorted(ids))
        self.assertEqual(scenario.completed_job_ids, set())

    def test_explicit_quantities(self):
        config = self.make_config()
        quantities = {task['id']: 0 for task in config['tasks']}
        quantities[1] = 3
        quantities[2] = 2
        config['job_quantities'] = quantities
        scenario = build_scenario(config, 123, 1, [])
        self.assertEqual([j.job_id for j in scenario.jobs], [1, 2, 3, 4, 5])
        self.assertEqual([j.task_type_id for j in scenario.jobs], [1, 1, 1, 2, 2])

    def test_missing_quantities_rejected(self):
        config = self.make_config()
        config.pop('job_quantities', None)
        with self.assertRaises(KeyError):
            build_scenario(config, 123, 1, [])

    def make_scheduler_case(self):
        import random
        config = self.make_config()
        config['job_quantities'] = {t['id']: 0 for t in config['tasks']}
        config['job_quantities'][1] = 2
        config['fatigue_noise_sigma'] = 0.0
        return config, build_scenario(config, 123, 1, []), random.Random(456)

    def test_scheduler_completes_distinct_same_type_jobs(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from src import scheduler
        config, scenario, rng = self.make_scheduler_case()
        with patch.multiple(scheduler, get_score=lambda *a, **kwargs: 1.0, evaluate_safety=lambda *a: SimpleNamespace(is_safe=True), calculate_collision_risk=lambda *a: 0.0, calculate_safe_zone_risk=lambda *a: 0.0, calculate_ergonomic_risk=lambda *a: 0.0):
            first, _ = scheduler.select_assignment('B1', scenario, 0.0, config, rng, arm_config={'veto': False, 'objective': 'productivity'})
            scheduler.execute_assignment(first, scenario, config, rng)
            second, _ = scheduler.select_assignment('B1', scenario, first.completion_time_s, config, rng, arm_config={'veto': False, 'objective': 'productivity'})
            self.assertNotEqual(first.job_id, second.job_id)
            self.assertEqual(first.task_id, second.task_id)
            scheduler.execute_assignment(second, scenario, config, rng)
        self.assertEqual(scenario.completed_job_ids, {1, 2})

    def test_duplicate_execution_rejected_without_state_change(self):
        from copy import deepcopy
        from src.scheduler import Assignment, execute_assignment
        config, scenario, rng = self.make_scheduler_case()
        assignment = Assignment(job_id=1, task_id=1, operator_id=1, robot_id=1, start_time_s=0.0, completion_time_s=1.0, duration_s=1.0, energy_kj=45.2, defect_probability=0.015, objective_score=1.0, vetoed=False, safety_violation=False)
        execute_assignment(assignment, scenario, config, rng)
        before = deepcopy(scenario)
        rng_before = rng.getstate()
        with self.assertRaises(ValueError):
            execute_assignment(assignment, scenario, config, rng)
        self.assertEqual(scenario, before)
        self.assertEqual(rng.getstate(), rng_before)

    def test_overlong_candidates_excluded_before_scoring(self):
        from unittest.mock import patch
        from src import scheduler
        config, scenario, rng = self.make_scheduler_case()
        scenario.shift_duration_s = 1.0
        with patch.object(scheduler, 'get_score') as score:
            with self.assertRaises(RuntimeError):
                scheduler.select_assignment('B1', scenario, 0.0, config, rng, arm_config={'veto': False, 'objective': 'productivity'})
            score.assert_not_called()
        self.assertEqual(scenario.completed_job_ids, set())

    def select_identity_candidate(self, scenario, config, rng, now):
        from unittest.mock import patch
        from types import SimpleNamespace
        from src import scheduler
        with patch.multiple(scheduler, get_score=lambda *a, **kwargs: 1.0, evaluate_safety=lambda *a: SimpleNamespace(is_safe=True), calculate_collision_risk=lambda *a: 0.0, calculate_safe_zone_risk=lambda *a: 0.0, calculate_ergonomic_risk=lambda *a: 0.0):
            return scheduler.select_assignment('B1', scenario, now, config, rng, arm_config={'veto': False, 'objective': 'productivity'})[0]

    def test_exact_boundary_candidate_allowed(self):
        config, scenario, rng = self.make_scheduler_case()
        task = next(t for t in scenario.tasks if t.task_id == 1)
        task.manual_time_s = 10.0
        task.robot_time_s = 10.0
        for operator in scenario.operators:
            operator.base_skill = 1.0
        for robot in scenario.robots:
            robot.base_speed = 1.0
        scenario.shift_duration_s = 15.0
        assignment = self.select_identity_candidate(scenario, config, rng, 5.0)
        self.assertEqual(assignment.duration_s, 10.0)
        self.assertEqual(assignment.completion_time_s, 15.0)

    def test_fitting_candidate_not_hidden_by_overlong_candidate(self):
        config, scenario, rng = self.make_scheduler_case()
        task = next(t for t in scenario.tasks if t.task_id == 1)
        task.manual_time_s = 10.0
        task.robot_time_s = 10.0
        scenario.operators[0].base_skill = 0.5
        scenario.operators[1].base_skill = 1.0
        for robot in scenario.robots:
            robot.base_speed = 1.0
        scenario.shift_duration_s = 15.0
        assignment = self.select_identity_candidate(scenario, config, rng, 5.0)
        self.assertEqual(assignment.operator_id, scenario.operators[1].operator_id)
        self.assertEqual(assignment.completion_time_s, 15.0)

    def test_shift_recovery_uses_nonoverlapping_intervals(self):
        from unittest.mock import patch
        from src import scheduler
        config, scenario, rng = self.make_scheduler_case()
        scenario.shift_duration_s = 30.0
        scenario.operators[1].fatigue_level = 1.0
        def assignment(job_id, start, duration):
            return scheduler.Assignment(job_id=job_id, task_id=1, operator_id=1, robot_id=1, start_time_s=start, completion_time_s=start + duration, duration_s=duration, energy_kj=45.2, defect_probability=0.015, objective_score=1.0, vetoed=False, safety_violation=False)
        selected = [(assignment(1, 0.0, 10.0), 0), (assignment(2, 10.0, 20.0), 0)]
        with patch.object(scheduler, 'select_assignment', side_effect=selected), patch.object(scheduler, 'apply_active_disturbances'), patch.object(scheduler, 'apply_recovery', wraps=scheduler.apply_recovery) as recovery:
            result = scheduler.run_shift('B1', scenario, config, 456, arm_config={'veto': False, 'objective': 'productivity'})
        intervals = [(c.args[0].operator_id, c.args[1]) for c in recovery.call_args_list]
        self.assertEqual(intervals, [(2, 10.0), (2, 20.0)])
        self.assertAlmostEqual(scenario.operators[1].fatigue_level, 0.55)
        self.assertEqual(scenario.completed_job_ids, {1, 2})
        self.assertEqual(result.completed_tasks, 2)
        self.assertEqual(result.makespan_s, 30.0)

    def test_unfinished_demand_when_no_job_fits(self):
        from unittest.mock import patch
        from src import scheduler
        config, scenario, rng = self.make_scheduler_case()
        scenario.shift_duration_s = 1.0
        with patch.object(scheduler, 'apply_active_disturbances'):
            result = scheduler.run_shift('B1', scenario, config, 456, arm_config={'veto': False, 'objective': 'productivity'})
        expected = {task.task_id: 0 for task in scenario.tasks}
        expected[1] = 2
        self.assertEqual(result.unfinished_jobs_by_type, expected)
        self.assertEqual(result.completed_tasks, 0)
        self.assertEqual(scenario.completed_job_ids, set())

    def test_partial_and_complete_backlog_accounting(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from src import scheduler
        for horizon, completed, unfinished in ((10.0, 1, 1), (20.0, 2, 0)):
            with self.subTest(horizon=horizon):
                config, scenario, rng = self.make_scheduler_case()
                task = next(t for t in scenario.tasks if t.task_id == 1)
                task.manual_time_s = 10.0
                task.robot_time_s = 10.0
                for operator in scenario.operators:
                    operator.base_skill = 1.0
                for robot in scenario.robots:
                    robot.base_speed = 1.0
                scenario.shift_duration_s = horizon
                with patch.multiple(scheduler, get_score=lambda *a, **kwargs: 1.0, evaluate_safety=lambda *a: SimpleNamespace(is_safe=True), calculate_collision_risk=lambda *a: 0.0, calculate_safe_zone_risk=lambda *a: 0.0, calculate_ergonomic_risk=lambda *a: 0.0, apply_active_disturbances=lambda *a: None):
                    result = scheduler.run_shift('B1', scenario, config, 456, arm_config={'veto': False, 'objective': 'productivity'})
                expected = {t.task_id: 0 for t in scenario.tasks}
                expected[1] = unfinished
                self.assertEqual(result.unfinished_jobs_by_type, expected)
                self.assertEqual(result.completed_tasks, completed)
                ids = [a.job_id for a in result.assignments]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(set(ids), scenario.completed_job_ids)
                self.assertEqual(completed + sum(result.unfinished_jobs_by_type.values()), len(scenario.jobs))
                self.assertTrue(all(a.completion_time_s <= horizon for a in result.assignments))

    def test_metrics_preserve_unfinished_demand(self):
        from unittest.mock import patch
        from src import scheduler
        from src.metrics import calculate_shift_metrics
        config, scenario, rng = self.make_scheduler_case()
        scenario.shift_duration_s = 1.0
        with patch.object(scheduler, 'apply_active_disturbances'):
            result = scheduler.run_shift('B1', scenario, config, 456, arm_config={'veto': False, 'objective': 'productivity'})
        metric = calculate_shift_metrics(result)
        expected = {task.task_id: 0 for task in scenario.tasks}
        expected[1] = 2
        self.assertEqual(metric.unfinished_jobs_by_type, expected)
        self.assertIsNot(metric.unfinished_jobs_by_type, result.unfinished_jobs_by_type)
        result.unfinished_jobs_by_type[1] = 999
        self.assertEqual(metric.unfinished_jobs_by_type, expected)

    def test_unfinished_demand_csv_round_trip(self):
        import csv
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from src import scheduler
        from src.metrics import calculate_shift_metrics
        from src.io_utils import save_csv
        from run_experiment import metrics_to_rows
        config, scenario, rng = self.make_scheduler_case()
        scenario.shift_duration_s = 1.0
        with patch.object(scheduler, 'apply_active_disturbances'):
            result = scheduler.run_shift('B1', scenario, config, 456, arm_config={'veto': False, 'objective': 'productivity'})
        metric = calculate_shift_metrics(result)
        rows = metrics_to_rows([metric])
        self.assertEqual(len(rows), 1)
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'metrics.csv'
            save_csv(rows, str(path))
            with path.open(encoding='utf-8', newline='') as stream:
                saved = list(csv.DictReader(stream))
        self.assertEqual(len(saved), 1)
        restored = json.loads(saved[0]['unfinished_jobs_by_type'])
        expected = {str(key): value for key, value in metric.unfinished_jobs_by_type.items()}
        self.assertEqual(restored, expected)
        self.assertEqual(restored['1'], 2)
