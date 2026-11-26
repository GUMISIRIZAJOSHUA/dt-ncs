import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from src import scheduler

class TestFatigueAdapterBridge(unittest.TestCase):
    def make_case(self):
        operator = SimpleNamespace(operator_id=10, fatigue_level=0.2, completed_tasks=[])
        robot = SimpleNamespace(robot_id=20, energy_used_kj=0.0, completed_tasks=[])
        task = SimpleNamespace(task_id=30, robot_energy_kj=5.0)
        job = SimpleNamespace(job_id=1, task_type_id=30)
        adapter = Mock()
        scenario = SimpleNamespace(operators=[operator], robots=[robot], tasks=[task], jobs=[job], completed_job_ids=set(), completed_task_ids=set(), disturbance_events=[], shift_duration_s=100.0, _fatigue_adapter=adapter)
        return scenario, operator, adapter

    def test_execution_routes_to_attached_adapter(self):
        scenario, operator, adapter = self.make_case()
        assignment = SimpleNamespace(job_id=1, task_id=30, operator_id=10, robot_id=20, duration_s=2.0)
        with patch.object(scheduler, "apply_fatigue_update") as legacy:
            scheduler.execute_assignment(assignment, scenario, {}, Mock())
        adapter.apply_work.assert_called_once_with(operator, 30, 2.0)
        legacy.assert_not_called()
        self.assertEqual(scenario.completed_job_ids, {1})

    def test_idle_recovery_routes_to_attached_adapter(self):
        scenario, operator, adapter = self.make_case()
        state = SimpleNamespace(unavailable_operator_ids=set())
        with patch.object(scheduler, "calculate_resource_state", return_value=state), patch.object(scheduler, "apply_recovery") as legacy:
            scheduler.apply_idle_recovery_interval(scenario, 0.0, 2.0, {})
        adapter.apply_recovery.assert_called_once_with(operator, 2.0)
        legacy.assert_not_called()

if __name__ == "__main__":
    unittest.main()
