import unittest
from contextlib import ExitStack
from unittest.mock import patch

import run_experiment as runner


class StopBeforeShift(Exception):
    pass


class TestRunnerConfigurationPreflight(unittest.TestCase):
    def config(self):
        return dict(shift_duration_s=1000, disturbances_per_shift=2, disturbance_types=["operator_absence", "robot_degradation"], job_quantities={30: 1}, arms=["A"], pilot_replicates_per_arm=1, replicates_per_arm=1)

    def task(self):
        return dict(id=30, name="Verification", manual_time_s=1, robot_time_s=1, fatigue_coefficient=1, cognitive_load=0, robot_energy_kj=1, defect_risk=0)

    def setup_runner(self, stack, config, smoke=False):
        argv = ["run_experiment.py"] + (["--smoke-check"] if smoke else [])
        seeds = [dict(arm="A", replicate=1, scenario_seed=123, search_seed=456)]
        stack.enter_context(patch("sys.argv", argv))
        stack.enter_context(patch.object(runner, "load_yaml", side_effect=[config, dict(tasks=[self.task()]), dict(arms={"A": dict(veto=True, objective="productivity")})]))
        stack.enter_context(patch.object(runner, "load_seeds", return_value=seeds))
        mkdir = stack.enter_context(patch.object(runner.os, "makedirs"))
        csv = stack.enter_context(patch.object(runner, "save_csv"))
        saved = stack.enter_context(patch.object(runner, "save_json"))
        dispatch = stack.enter_context(patch.object(runner, "run_shift", side_effect=StopBeforeShift))
        stack.enter_context(patch("builtins.print"))
        return mkdir, csv, saved, dispatch

    def assert_rejected(self, config):
        with ExitStack() as stack:
            mkdir, csv, saved, dispatch = self.setup_runner(stack, config)
            with self.assertRaises(ValueError):
                runner.main()
            mkdir.assert_not_called()
            csv.assert_not_called()
            saved.assert_not_called()
            dispatch.assert_not_called()

    def test_invalid_workload_rejected_before_output(self):
        for quantities in (None, {}, {31: 1}, {30: -1}, {30: True}, {30: 1.5}):
            with self.subTest(quantities=quantities):
                config = self.config()
                if quantities is None:
                    del config["job_quantities"]
                else:
                    config["job_quantities"] = quantities
                self.assert_rejected(config)

    def test_invalid_disturbances_rejected_before_output(self):
        cases = [("disturbance_types", None), ("disturbance_types", []), ("disturbance_types", ["unsupported"]), ("disturbance_types", ["operator_absence", "operator_absence"]), ("disturbances_per_shift", -1), ("disturbances_per_shift", True)]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                config = self.config()
                if value is None:
                    del config[key]
                else:
                    config[key] = value
                self.assert_rejected(config)

    def test_smoke_overrides_survive_preflight_and_are_labeled(self):
        config = self.config()
        del config["job_quantities"]
        del config["disturbance_types"]
        with ExitStack() as stack:
            mkdir, csv, saved, dispatch = self.setup_runner(stack, config, smoke=True)
            with self.assertRaises(StopBeforeShift):
                runner.main()
            mkdir.assert_called_once()
            dispatch.assert_called_once()
            metadata = saved.call_args_list[0].args[0]
            self.assertTrue(metadata["smoke_check"])
            self.assertEqual(metadata["run_type"], "smoke")
            experiment = metadata["experiment"]
            self.assertEqual(experiment["job_quantities"], {30: 1})
            self.assertEqual(experiment["disturbances_per_shift"], 2)
            self.assertEqual(set(experiment["disturbance_types"]), {"operator_absence", "robot_degradation"})
            self.assertIn("synthetic_smoke_check", experiment["workload_provenance"])
            self.assertIn("synthetic_smoke_check", experiment["disturbance_provenance"])
            scenario = dispatch.call_args.kwargs["scenario"]
            self.assertEqual(len(scenario.jobs), 1)
            self.assertEqual(len(scenario.disturbance_events), 2)


if __name__ == "__main__":
    unittest.main()
