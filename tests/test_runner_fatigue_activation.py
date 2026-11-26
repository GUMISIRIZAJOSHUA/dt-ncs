import json
import unittest
from contextlib import ExitStack
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import run_experiment as runner


class StopDispatch(Exception):
    pass


class TestRunnerFatigueActivation(unittest.TestCase):
    def raw(self):
        # Synthetic verification parameters only.
        return dict(step_size_s=0.5, operators={1: dict(initial_fatigue=0.25, alpha_per_s=0.02, beta=0.0, rho_per_s=0.02, fatigue_limit=0.8)}, task_demands={30: 1.0})

    def scenario(self, **kwargs):
        return SimpleNamespace(operators=[SimpleNamespace(operator_id=1, fatigue_level=0.0)], tasks=[SimpleNamespace(task_id=30)], robots=[SimpleNamespace(robot_id=1)], disturbance_events=[])

    def setup_main(self, stack, raw, enabled=True):
        config = dict(arms=["A", "B"], job_quantities={30: 1})
        seeds = [dict(arm=arm, replicate=1, scenario_seed=123, search_seed=456) for arm in ("A", "B")]
        argv = ["run_experiment.py"]
        if enabled:
            argv += ["--fatigue-parameters", "verification.yaml"]
        stack.enter_context(patch("sys.argv", argv))
        stack.enter_context(patch.object(runner, "load_yaml", side_effect=[config, dict(tasks=[]), dict(arms={"A": {}, "B": {}})] + ([raw] if enabled else [])))
        stack.enter_context(patch.object(runner, "load_seeds", return_value=seeds))
        stack.enter_context(patch.object(runner, "select_seed_rows", return_value=seeds))
        stack.enter_context(patch.object(runner, "build_scenario", side_effect=self.scenario))
        mkdir = stack.enter_context(patch.object(runner.os, "makedirs"))
        stack.enter_context(patch.object(runner, "save_csv"))
        saved = stack.enter_context(patch.object(runner, "save_json"))
        stack.enter_context(patch.object(runner, "generate_disturbance_events", return_value=[]))
        metric = SimpleNamespace(completed_tasks=0, throughput_tasks_per_hour=0.0, final_fatigue=0.0)
        stack.enter_context(patch.object(runner, "calculate_shift_metrics", return_value=metric))
        stack.enter_context(patch("builtins.print"))
        return mkdir, saved

    def test_default_metadata_is_legacy(self):
        data = runner.fatigue_run_metadata()
        self.assertEqual(data["safety_semantics"], "pre_assignment_state_only")
        self.assertEqual(data["fatigue_model"], "existing_noisy_increment_linear_recovery")
        self.assertIsNone(data["fatigue_parameters"])
        json.dumps(data, allow_nan=False)

    def test_each_scenario_gets_fresh_initialized_adapter(self):
        first, second = self.scenario(), self.scenario()
        raw = self.raw()
        before = deepcopy(raw)
        a = runner.prepare_fatigue_adapter(first, raw)
        b = runner.prepare_fatigue_adapter(second, raw)
        self.assertIsNot(a, b)
        self.assertIs(first._fatigue_adapter, a)
        self.assertIs(second._fatigue_adapter, b)
        self.assertEqual(first.operators[0].fatigue_level, 0.25)
        first.operators[0].fatigue_level = 0.7
        self.assertEqual(second.operators[0].fatigue_level, 0.25)
        self.assertEqual(raw, before)

    def test_metadata_is_normalized_strict_json_snapshot(self):
        raw = self.raw()
        adapter = runner.prepare_fatigue_adapter(self.scenario(), raw)
        data = runner.fatigue_run_metadata(adapter, "verification.yaml")
        self.assertEqual(json.loads(json.dumps(data, allow_nan=False)), data)
        self.assertEqual(data["fatigue_parameters"]["operators"]["1"]["initial_fatigue"], 0.25)
        self.assertEqual(data["fatigue_parameters"]["task_demands"], {"30": 1.0})
        self.assertNotEqual(data["safety_semantics"], "pre_assignment_state_only")
        raw["operators"][1]["initial_fatigue"] = 0.9
        self.assertEqual(data["fatigue_parameters"]["operators"]["1"]["initial_fatigue"], 0.25)

    def test_invalid_parameters_fail_before_output_creation(self):
        invalid_cases = [{}, self.raw()]
        invalid_cases[1]["task_demands"] = {31: 1.0}
        for raw in invalid_cases:
            with self.subTest(raw=raw), ExitStack() as stack:
                mkdir, saved = self.setup_main(stack, raw)
                dispatch = stack.enter_context(patch.object(runner, "run_shift"))
                with self.assertRaises(ValueError):
                    runner.main()
                mkdir.assert_not_called()
                saved.assert_not_called()
                dispatch.assert_not_called()

    def test_main_initializes_both_arms_and_preserves_legacy_default(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), ExitStack() as stack:
                mkdir, saved = self.setup_main(stack, self.raw(), enabled)
                scenarios = []
                def dispatch(**kwargs):
                    scenario = kwargs["scenario"]
                    scenarios.append(scenario)
                    self.assertEqual(hasattr(scenario, "_fatigue_adapter"), enabled)
                    self.assertEqual(scenario.operators[0].fatigue_level, 0.25 if enabled else 0.0)
                    if len(scenarios) == 2:
                        raise StopDispatch()
                    scenario.operators[0].fatigue_level = 0.7
                    return object()
                mocked = stack.enter_context(patch.object(runner, "run_shift", side_effect=dispatch))
                with self.assertRaises(StopDispatch):
                    runner.main()
                self.assertEqual(mocked.call_count, 2)
                self.assertEqual([c.kwargs["arm"] for c in mocked.call_args_list], ["A", "B"])
                self.assertIsNot(scenarios[0], scenarios[1])
                metadata = saved.call_args_list[0].args[0]
                reporting = metadata["reporting_semantics"]
                self.assertEqual(reporting["throughput_denominator"], "configured_shift_duration_s")
                self.assertEqual(reporting["final_fatigue"], "maximum_operator_fatigue_at_dispatch_termination")
                self.assertEqual(reporting["final_ergonomic_risk"], "maximum_operator_endpoint_risk_with_zero_cognitive_load")
                self.assertEqual(reporting["post_dispatch_recovery"], "not_simulated")
                self.assertEqual(reporting["safety_violations"], "count_of_executed_assignments_flagged_unsafe_at_selection")
                self.assertEqual(reporting["safety_assessment_basis"], metadata["safety_semantics"])
                self.assertEqual(reporting["veto_events"], "unsafe_candidate_count_accumulated_on_successful_veto_enabled_selections")
                self.assertEqual(reporting["collision_geometry"], "operator_and_robot_ids_used_as_positions")
                self.assertEqual(reporting["safe_zone_geometry"], "operator_id_used_as_position_with_fixed_zone_center_2_5")
                self.assertEqual(reporting["continuous_safety_trace"], "not_recorded")
                json.dumps(metadata, allow_nan=False)
                if enabled:
                    self.assertIsNot(scenarios[0]._fatigue_adapter, scenarios[1]._fatigue_adapter)
                    self.assertEqual(metadata["fatigue_parameters"]["task_demands"], {"30": 1.0})
                else:
                    self.assertEqual(metadata["safety_semantics"], "pre_assignment_state_only")
                    self.assertIsNone(metadata["fatigue_parameters"])


if __name__ == "__main__":
    unittest.main()
