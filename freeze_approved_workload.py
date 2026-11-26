import copy
import shutil
from datetime import datetime
from pathlib import Path

import yaml

from src.io_utils import load_yaml, load_seeds
from src.scenario import build_scenario
from src.disturbances import generate_disturbance_events
from run_experiment import prepare_fatigue_adapter, select_seed_rows


def main():
    path = Path("configs/experiment.yaml")
    original = path.read_bytes()
    config = yaml.safe_load(original.decode("utf-8-sig"))
    tasks = load_yaml("configs/tasks.yaml")["tasks"]
    arms = load_yaml("configs/arms.yaml")
    seeds = load_seeds("configs/seeds.csv")
    fatigue = load_yaml("configs/fatigue_synthetic_benchmark.yaml")

    ids = [task["id"] for task in tasks]
    if (
        len(ids) != 12
        or any(type(task_id) is not int for task_id in ids)
        or set(ids) != set(range(1, 13))
    ):
        raise ValueError("Expected exactly task IDs 1 through 12")
    if config["shift_duration_s"] != 28800:
        raise ValueError("Unexpected shift duration")
    if config["disturbances_per_shift"] != 2:
        raise ValueError("Unexpected disturbance count")
    if config["pilot_replicates_per_arm"] != 1:
        raise ValueError("Expected one pilot replicate per arm")
    if set(config["arms"]) != {"B1", "B2", "B3a", "B3b", "B3"}:
        raise ValueError("Unexpected configured arms")

    config["job_quantities"] = {
        task_id: 100 for task_id in sorted(ids)
    }
    config["workload_provenance"] = (
        "user_approved_2026-11-24;"
        "synthetic_balanced_100_jobs_per_task_type;"
        "1200_jobs_total;"
        "selected_after_approved_10_shift_engineering_sizing;"
        "results/engineering_workload_sizing_20261124_081316_759450"
    )
    config["disturbance_types"] = [
        "operator_absence",
        "robot_degradation",
    ]
    config["disturbance_provenance"] = (
        "user_approved_synthetic_policy_2026-11-24;"
        "independent_type_and_target_sampling;"
        "two_events_not_one_guaranteed_per_type;"
        "legacy_uncalibrated_timing_and_severity;"
        "dispatch_time_non_preemptive_effects"
    )

    text = yaml.safe_dump(config, sort_keys=False)
    reloaded = yaml.safe_load(text)
    pilot_seeds = select_seed_rows(seeds, reloaded, arms, "pilot")
    if len(pilot_seeds) != 5:
        raise ValueError("Expected five selected pilot shifts")

    for row in pilot_seeds:
        scenario_config = copy.deepcopy(reloaded)
        scenario_config["tasks"] = copy.deepcopy(tasks)
        scenario = build_scenario(
            config=scenario_config,
            scenario_seed=row["scenario_seed"],
            scenario_id=row["replicate"],
            disturbance_events=[],
        )
        if len(scenario.jobs) != 1200:
            raise ValueError("Expected 1200 backlog jobs")
        prepare_fatigue_adapter(scenario, fatigue)
        events = generate_disturbance_events(
            scenario_config,
            row["scenario_seed"],
            operator_ids=[o.operator_id for o in scenario.operators],
            robot_ids=[r.robot_id for r in scenario.robots],
        )
        if len(events) != 2:
            raise ValueError("Expected two generated events")

    if path.read_bytes() != original:
        raise RuntimeError("Configuration changed during validation")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = Path("repair_backups") / stamp / path
    backup.parent.mkdir(parents=True, exist_ok=False)
    shutil.copy2(path, backup)

    temporary = path.with_name(path.name + "." + stamp + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    temporary.replace(path)

    print("PASS: ordinary pilot inputs validated for all five arms.")
    print("Updated:", path)
    print("Backup:", backup)
    print("Workload: 100 jobs per type; 1200 jobs total.")
    print("Fatigue: approved benchmark file bound and initialized")
    print("         on disposable preflight scenarios only.")
    print("No shifts executed. Pilot and full launch remain on hold.")


if __name__ == "__main__":
    main()