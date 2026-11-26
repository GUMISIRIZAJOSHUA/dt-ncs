import copy
import csv
import hashlib
import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from src.io_utils import load_yaml, load_seeds
from src.scenario import build_scenario
from src.disturbances import generate_disturbance_events
from src.scheduler import run_shift
from run_experiment import (
    prepare_fatigue_adapter,
    select_seed_rows,
)


QUANTITIES = (50, 100)
EXPECTED_ARMS = {"B1", "B2", "B3a", "B3b", "B3"}
EXPECTED_TASK_IDS = set(range(1, 13))
FATIGUE_PATH = Path("configs/fatigue_synthetic_benchmark.yaml")


def write_json(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)


def make_config(base, tasks, quantity):
    config = copy.deepcopy(base)
    config["tasks"] = copy.deepcopy(tasks)
    config["job_quantities"] = {
        task_id: quantity for task_id in sorted(EXPECTED_TASK_IDS)
    }
    config["pilot_replicates_per_arm"] = 1
    config["disturbance_types"] = [
        "operator_absence",
        "robot_degradation",
    ]
    config["workload_provenance"] = (
        "approved_engineering_sizing_equal_quantity_per_task_type"
    )
    config["disturbance_provenance"] = (
        "approved_synthetic_policy;"
        "independent_type_and_target_sampling;"
        "legacy_uncalibrated_timing_and_severity;"
        "dispatch_time_non_preemptive_effects"
    )
    return config


def make_scenario(config, seed_row, fatigue_raw):
    scenario = build_scenario(
        config=config,
        scenario_seed=seed_row["scenario_seed"],
        scenario_id=seed_row["replicate"],
        disturbance_events=[],
    )
    prepare_fatigue_adapter(scenario, fatigue_raw)
    scenario.disturbance_events = generate_disturbance_events(
        config,
        seed_row["scenario_seed"],
        operator_ids=[o.operator_id for o in scenario.operators],
        robot_ids=[r.robot_id for r in scenario.robots],
    )
    return scenario


def event_coverage(event, assignments):
    start = event.start_time_s
    end = start + event.duration_s
    target = event.target_resource_id

    if event.event_type == "operator_absence":
        targeted = [
            a for a in assignments if a.operator_id == target
        ]
    else:
        targeted = [
            a for a in assignments if a.robot_id == target
        ]

    overlaps = [
        a for a in targeted
        if a.start_time_s < end and a.completion_time_s > start
    ]
    active_dispatches = [
        a for a in targeted if start <= a.start_time_s < end
    ]
    crossing_start = [
        a for a in targeted
        if a.start_time_s < start < a.completion_time_s
    ]

    return {
        "event_type": event.event_type,
        "target_resource_id": target,
        "start_time_s": start,
        "duration_s": event.duration_s,
        "end_time_s": end,
        "severity": event.severity,
        "targeted_assignment_overlap_count": len(overlaps),
        "targeted_assignment_overlap_s": sum(
            max(
                0.0,
                min(a.completion_time_s, end)
                - max(a.start_time_s, start),
            )
            for a in overlaps
        ),
        "targeted_dispatches_while_event_active": len(active_dispatches),
        "targeted_assignments_crossing_event_start": len(crossing_start),
    }


def main():
    started = time.perf_counter()
    base = load_yaml("configs/experiment.yaml")
    tasks = load_yaml("configs/tasks.yaml")["tasks"]
    arms_config = load_yaml("configs/arms.yaml")
    seeds = load_seeds("configs/seeds.csv")
    fatigue_raw = load_yaml(str(FATIGUE_PATH))

    task_ids = [task["id"] for task in tasks]
    if (
        len(task_ids) != 12
        or any(type(task_id) is not int for task_id in task_ids)
        or set(task_ids) != EXPECTED_TASK_IDS
    ):
        raise ValueError("Sizing requires task IDs 1 through 12 exactly")
    if set(base["arms"]) != EXPECTED_ARMS:
        raise ValueError("Sizing requires the five approved arms")
    if base["shift_duration_s"] != 28800:
        raise ValueError("Sizing requires the approved 28800-second shift")
    if base["disturbances_per_shift"] != 2:
        raise ValueError("Sizing requires two disturbances per shift")
    if base["fatigue_critical_threshold"] != 0.80:
        raise ValueError("Unexpected global fatigue threshold")

    expected_row = {
        "initial_fatigue": 0.10,
        "alpha_per_s": 0.001,
        "beta": 0.0,
        "rho_per_s": 0.001,
        "fatigue_limit": 0.80,
    }
    approved_fatigue = {
        "step_size_s": 0.5,
        "operators": {
            operator_id: dict(expected_row)
            for operator_id in (1, 2)
        },
        "task_demands": {
            task_id: 0.50 for task_id in range(1, 13)
        },
    }
    if fatigue_raw != approved_fatigue:
        raise ValueError("Fatigue file differs from the approved baseline")

    configs = {
        q: make_config(base, tasks, q) for q in QUANTITIES
    }
    selected = select_seed_rows(
        seeds, configs[50], arms_config, "pilot"
    )
    if len(selected) != 5:
        raise ValueError("Expected exactly five paired seed rows")

    for quantity, config in configs.items():
        for seed_row in selected:
            scenario = make_scenario(config, seed_row, fatigue_raw)
            if len(scenario.jobs) != 12 * quantity:
                raise ValueError("Unexpected backlog size")
            if len(scenario.disturbance_events) != 2:
                raise ValueError("Unexpected disturbance count")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output = Path("results") / f"engineering_workload_sizing_{timestamp}"
    output.mkdir(parents=True, exist_ok=False)

    input_paths = [
        Path("configs/experiment.yaml"),
        Path("configs/tasks.yaml"),
        Path("configs/arms.yaml"),
        Path("configs/seeds.csv"),
        FATIGUE_PATH,
    ]
    metadata = {
        "run_type": "approved_engineering_workload_sizing",
        "not_pilot_or_main_experiment": True,
        "quantities_per_task_type": list(QUANTITIES),
        "planned_shifts": 10,
        "selected_seeds": selected,
        "effective_configs": {
            str(q): config for q, config in configs.items()
        },
        "arms": arms_config,
        "fatigue_parameters": fatigue_raw,
        "fatigue_parameter_source": str(FATIGUE_PATH.resolve()),
        "input_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in input_paths
        },
        "interpretation": {
            "scheduling": "sequential_non_preemptive_dispatch_time",
            "observation": "dispatch_termination_not_fixed_end_of_shift",
            "event_overlap": (
                "Overlap is not proof of causal effect. An absent operator "
                "can be excluded without an overlapping assignment. "
                "Mid-assignment event changes do not alter that assignment."
            ),
            "selection": (
                "Prefer the smallest candidate retaining backlog across "
                "all arms through the shift; inspect other early "
                "termination reasons before freezing quantities."
            ),
        },
    }
    write_json(output / "sizing_configuration.json", metadata)

    columns = [
        "quantity_per_type",
        "initial_jobs",
        "arm",
        "replicate",
        "scenario_seed",
        "search_seed",
        "completed_tasks",
        "unfinished_jobs",
        "unfinished_jobs_by_type",
        "makespan_s",
        "dispatch_end_time_s",
        "termination_reason",
        "throughput_tasks_per_hour",
        "final_fatigue",
        "safety_violations",
        "veto_events",
        "events_started_before_dispatch_end",
        "events_with_targeted_assignment_overlap",
        "runtime_s",
    ]

    print("Output directory:", output, flush=True)
    print("Engineering sizing only: 10 shifts.", flush=True)

    with (output / "sizing_metrics.csv").open(
        "x", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        handle.flush()

        for quantity, config in configs.items():
            for seed_row in selected:
                arm = seed_row["arm"]
                label = f"q{quantity}_{arm}"
                print("Starting", label, flush=True)
                shift_started = time.perf_counter()
                scenario = make_scenario(config, seed_row, fatigue_raw)

                result = run_shift(
                    arm=arm,
                    scenario=scenario,
                    config=config,
                    search_seed=seed_row["search_seed"],
                    arm_config=arms_config["arms"][arm],
                )

                coverage = [
                    event_coverage(event, result.assignments)
                    for event in scenario.disturbance_events
                ]
                write_json(
                    output / f"{label}_event_coverage.json",
                    coverage,
                )
                write_json(
                    output / f"{label}_assignments.json",
                    [asdict(a) for a in result.assignments],
                )

                row = {
                    "quantity_per_type": quantity,
                    "initial_jobs": 12 * quantity,
                    "arm": arm,
                    "replicate": seed_row["replicate"],
                    "scenario_seed": seed_row["scenario_seed"],
                    "search_seed": seed_row["search_seed"],
                    "completed_tasks": result.completed_tasks,
                    "unfinished_jobs": sum(
                        result.unfinished_jobs_by_type.values()
                    ),
                    "unfinished_jobs_by_type": json.dumps(
                        result.unfinished_jobs_by_type, sort_keys=True
                    ),
                    "makespan_s": result.makespan_s,
                    "dispatch_end_time_s": result.dispatch_end_time_s,
                    "termination_reason": result.termination_reason,
                    "throughput_tasks_per_hour": (
                        result.throughput_tasks_per_hour
                    ),
                    "final_fatigue": result.final_fatigue,
                    "safety_violations": result.safety_violations,
                    "veto_events": result.veto_events,
                    "events_started_before_dispatch_end": sum(
                        e["start_time_s"] < result.dispatch_end_time_s
                        for e in coverage
                    ),
                    "events_with_targeted_assignment_overlap": sum(
                        e["targeted_assignment_overlap_count"] > 0
                        for e in coverage
                    ),
                    "runtime_s": time.perf_counter() - shift_started,
                }
                writer.writerow(row)
                handle.flush()

                print(
                    f"Completed {label}: "
                    f"tasks={result.completed_tasks}, "
                    f"remaining={row['unfinished_jobs']}, "
                    f"dispatch_end={result.dispatch_end_time_s:.1f}s, "
                    f"reason={result.termination_reason}, "
                    f"fatigue={result.final_fatigue:.4f}, "
                    f"violations={result.safety_violations}",
                    flush=True,
                )

    write_json(
        output / "completion.json",
        {
            "completed_shifts": 10,
            "runtime_s": time.perf_counter() - started,
            "status": "engineering_sizing_complete",
        },
    )
    print("Sizing complete. Results:", output, flush=True)


if __name__ == "__main__":
    main()