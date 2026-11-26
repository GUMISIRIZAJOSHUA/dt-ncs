import argparse
from datetime import datetime
from pathlib import Path
import json as backlog_json
import csv
import os
import time
from typing import Dict, List

from src.io_utils import (
    load_yaml,
    load_seeds,
    ensure_directory,
    save_csv,
    save_json,
)
from src.scenario import build_scenario
from src.fatigue_adapter import FatigueAdapter
from src.disturbances import generate_disturbance_events
from src.scheduler import run_shift
from src.metrics import calculate_shift_metrics
from src.statistics import (
    calculate_descriptive_statistics,
    calculate_paired_comparison,
)
from src.visualization import (
    plot_safety_violations,
    plot_fatigue,
    plot_throughput_energy_tradeoff,
    plot_wellbeing_productivity_tradeoff,
)


def metrics_to_rows(
    metrics: List,
) -> List[Dict]:
    rows = []

    for metric in metrics:
        rows.append(
            {
                "arm": metric.arm,
                "scenario_id": metric.scenario_id,
                "completed_tasks": metric.completed_tasks,
                'unfinished_jobs_by_type': backlog_json.dumps(metric.unfinished_jobs_by_type, sort_keys=True),
                "throughput_tasks_per_hour": metric.throughput_tasks_per_hour,
                "makespan_s": metric.makespan_s,
                "dispatch_end_time_s": metric.dispatch_end_time_s,
                "observation_time_s": metric.observation_time_s,
                "termination_reason": metric.termination_reason,
                "total_energy_kj": metric.total_energy_kj,
                "energy_per_task_kj": metric.energy_per_task_kj,
                "expected_defects": metric.expected_defects,
                "defect_rate": metric.defect_rate,
                "final_fatigue": metric.final_fatigue,
                "final_ergonomic_risk": metric.final_ergonomic_risk,
                "safety_violations": metric.safety_violations,
                "veto_events": metric.veto_events,
                "well_being_score": metric.well_being_score,
                "sustainability_score": metric.sustainability_score,
                "overall_score": metric.overall_score,
            }
        )

    return rows


def calculate_summary(
    metrics: List,
) -> Dict:
    metric_names = [
        "completed_tasks",
        "throughput_tasks_per_hour",
        "makespan_s",
        "total_energy_kj",
        "energy_per_task_kj",
        "expected_defects",
        "defect_rate",
        "final_fatigue",
        "final_ergonomic_risk",
        "safety_violations",
        "veto_events",
        "well_being_score",
        "sustainability_score",
        "overall_score",
    ]

    summary = {}

    for metric_name in metric_names:
        summary[metric_name] = {}

        for arm in sorted(set(metric.arm for metric in metrics)):
            values = [
                getattr(metric, metric_name)
                for metric in metrics
                if metric.arm == arm
            ]

            statistics = calculate_descriptive_statistics(values)

            summary[metric_name][arm] = {
                "mean": statistics.mean,
                "standard_deviation": statistics.standard_deviation,
                "standard_error": statistics.standard_error,
                "ci_lower": statistics.ci_lower,
                "ci_upper": statistics.ci_upper,
                "n": statistics.n,
            }

    return summary


def calculate_comparisons(
    metrics: List,
) -> List[Dict]:
    comparison_metrics = [
        "completed_tasks",
        "throughput_tasks_per_hour",
        "total_energy_kj",
        "energy_per_task_kj",
        "defect_rate",
        "final_fatigue",
        "final_ergonomic_risk",
        "safety_violations",
        "veto_events",
        "well_being_score",
        "sustainability_score",
        "overall_score",
    ]

    by_arm = {}
    for metric in metrics:
        arm_metrics = by_arm.setdefault(metric.arm, {})
        if metric.scenario_id in arm_metrics:
            raise ValueError(
                f"Duplicate scenario ID for {metric.arm}: "
                f"{metric.scenario_id}"
            )
        arm_metrics[metric.scenario_id] = metric

    arms = sorted(by_arm)
    if not arms:
        return []

    scenario_ids = set(by_arm[arms[0]])
    for arm in arms:
        if set(by_arm[arm]) != scenario_ids:
            raise ValueError(
                f"Scenario IDs do not match for arm {arm}"
            )

    if len(scenario_ids) < 2:
        return []

    ordered_ids = sorted(scenario_ids)
    comparisons = []

    for metric_name in comparison_metrics:
        for arm_a in arms:
            for arm_b in arms:
                if arm_a == arm_b:
                    continue

                values_a = [
                    getattr(by_arm[arm_a][scenario_id], metric_name)
                    for scenario_id in ordered_ids
                ]
                values_b = [
                    getattr(by_arm[arm_b][scenario_id], metric_name)
                    for scenario_id in ordered_ids
                ]

                comparison = calculate_paired_comparison(
                    arm_a=arm_a,
                    arm_b=arm_b,
                    metric=metric_name,
                    values_a=values_a,
                    values_b=values_b,
                )

                comparisons.append(
                    {
                        "metric": metric_name,
                        "arm_a": arm_a,
                        "arm_b": arm_b,
                        "mean_difference": comparison.mean_difference,
                        "standard_deviation_difference":
                            comparison.standard_deviation_difference,
                        "standard_error_difference":
                            comparison.standard_error_difference,
                        "ci_lower": comparison.ci_lower,
                        "ci_upper": comparison.ci_upper,
                        "t_statistic": comparison.t_statistic,
                        "degrees_of_freedom":
                            comparison.degrees_of_freedom,
                        "p_value": comparison.p_value,
                        "cohens_d": comparison.cohens_d,
                    }
                )

    return comparisons


def save_comparison_csv(
    comparisons: List[Dict],
    output_path: str,
) -> None:
    comparison_columns = [
        "metric",
        "arm_a",
        "arm_b",
        "mean_difference",
        "standard_deviation_difference",
        "standard_error_difference",
        "ci_lower",
        "ci_upper",
        "t_statistic",
        "degrees_of_freedom",
        "p_value",
        "cohens_d",
    ]

    ensure_directory(os.path.dirname(output_path))

    with open(
        output_path,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=comparison_columns,
        )

        writer.writeheader()

        for comparison in comparisons:
            writer.writerow(comparison)



def select_seed_rows(seeds, config, arms_config, mode):
    arms = config["arms"]
    if not arms or len(arms) != len(set(arms)):
        raise ValueError("Configured arms must be nonempty and unique")

    if set(arms) != set(arms_config["arms"]):
        raise ValueError("Experiment and arm-definition keys differ")

    by_arm = {arm: {} for arm in arms}
    for row in seeds:
        arm = row["arm"]
        if arm not in by_arm:
            raise ValueError(f"Unexpected seed-file arm: {arm}")

        replicate = row["replicate"]
        if replicate in by_arm[arm]:
            raise ValueError(
                f"Duplicate seed row: {arm}, replicate {replicate}"
            )
        by_arm[arm][replicate] = row

    replicate_ids = set(by_arm[arms[0]])
    if not replicate_ids:
        raise ValueError("No seed replicates found")

    for arm in arms:
        if set(by_arm[arm]) != replicate_ids:
            raise ValueError(f"Replicate IDs do not match for {arm}")

    for replicate in sorted(replicate_ids):
        scenario_seeds = {
            by_arm[arm][replicate]["scenario_seed"]
            for arm in arms
        }
        if len(scenario_seeds) != 1:
            raise ValueError(
                f"Scenario seeds differ for replicate {replicate}"
            )

    count_key = (
        "pilot_replicates_per_arm"
        if mode == "pilot"
        else "replicates_per_arm"
    )
    count = config[count_key]
    if type(count) is not int or count < 1:
        raise ValueError(f"Invalid {count_key}: {count}")

    if mode == "full" and len(replicate_ids) != count:
        raise ValueError(
            f"Full run requires exactly {count} replicates per arm; "
            f"found {len(replicate_ids)}"
        )
    if len(replicate_ids) < count:
        raise ValueError("Not enough replicates for requested mode")

    selected_ids = sorted(replicate_ids)[:count]
    return [
        by_arm[arm][replicate]
        for replicate in selected_ids
        for arm in arms
    ]



def prepare_fatigue_adapter(scenario, raw):
    """Validate explicit parameters and initialize this scenario only."""
    adapter = FatigueAdapter(
        raw,
        operator_ids=[o.operator_id for o in scenario.operators],
        task_ids=[t.task_id for t in scenario.tasks],
    )
    adapter.initialize(scenario.operators)
    scenario._fatigue_adapter = adapter
    return adapter


def fatigue_run_metadata(adapter=None, parameter_path=None):
    """Return ordinary JSON data, never the runtime adapter."""
    if adapter is None:
        return {
            "safety_semantics": "pre_assignment_state_only",
            "fatigue_model": "existing_noisy_increment_linear_recovery",
            "fatigue_parameters": None,
            "fatigue_parameter_source": None,
        }

    parameters = adapter.parameters
    return {
        "safety_semantics": (
            "projected_work_maximum_fatigue_and_ergonomic_risk;"
            "existing_geometry_checks;"
            "arm_specific_veto"
        ),
        "fatigue_model": (
            "explicit_deterministic_fatigue_kernel_with_recovery"
        ),
        "fatigue_parameter_source": str(
            Path(parameter_path).resolve()
        ),
        "fatigue_parameters": {
            "step_size_s": parameters.step_size_s,
            "operators": {
                str(operator_id): {
                    "initial_fatigue": row.initial_fatigue,
                    "alpha_per_s": row.alpha_per_s,
                    "beta": row.beta,
                    "rho_per_s": row.rho_per_s,
                    "fatigue_limit": row.fatigue_limit,
                }
                for operator_id, row in parameters.operators.items()
            },
            "task_demands": {
                str(task_id): demand
                for task_id, demand in parameters.task_demands.items()
            },
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("pilot", "full"), default="pilot"
    )
    parser.add_argument(
        "--smoke-check",
        action="store_true",
        help="Pilot-only synthetic workload: one job per task type.",
    )
    parser.add_argument(
        "--fatigue-parameters",
        default=None,
        metavar="PATH",
        help=(
            "Explicit fatigue YAML file with integer operator/task keys. "
            "Omit to retain the legacy fatigue model."
        ),
    )
    args = parser.parse_args()
    if args.smoke_check and args.mode != "pilot":
        parser.error("--smoke-check requires --mode pilot")

    run_label = "smoke" if args.smoke_check else args.mode
    start_time = time.time()

    config = load_yaml("configs/experiment.yaml")
    tasks_config = load_yaml("configs/tasks.yaml")
    arms_config = load_yaml("configs/arms.yaml")
    seeds = load_seeds("configs/seeds.csv")

    config["tasks"] = tasks_config["tasks"]

    if args.smoke_check:
        task_ids = [task["id"] for task in config["tasks"]]
        if (
            not task_ids
            or any(type(task_id) is not int for task_id in task_ids)
            or any(task_id <= 0 for task_id in task_ids)
            or len(task_ids) != len(set(task_ids))
        ):
            raise ValueError("Invalid task IDs for smoke-check workload")

        config["job_quantities"] = {
            task_id: 1 for task_id in task_ids
        }
        config["pilot_replicates_per_arm"] = 1
        config["workload_provenance"] = (
            "synthetic_smoke_check_one_job_per_task_type"
        )
        config["disturbance_types"] = [
            "operator_absence",
            "robot_degradation",
        ]
        config["disturbance_provenance"] = (
            "synthetic_smoke_check_supported_event_types;"
            "configured_count_retained;"
            "legacy_uncalibrated_timing_and_severity"
        )
    elif "job_quantities" not in config:
        raise ValueError(
            "Explicit job_quantities required for pilot/full runs. "
            "Use --mode pilot --smoke-check only for a synthetic "
            "execution check."
        )

    seeds = select_seed_rows(
        seeds, config, arms_config, args.mode
    )

    # Validate workload and disturbances before creating any run output.
    # This disposable scenario is never dispatched or reused by an arm.
    preflight = build_scenario(
        config=config,
        scenario_seed=seeds[0]["scenario_seed"],
        scenario_id=seeds[0]["replicate"],
        disturbance_events=[],
    )
    generate_disturbance_events(
        config,
        seeds[0]["scenario_seed"],
        operator_ids=[o.operator_id for o in preflight.operators],
        robot_ids=[r.robot_id for r in preflight.robots],
    )

    fatigue_raw = None
    fatigue_metadata = fatigue_run_metadata()
    if args.fatigue_parameters is not None:
        fatigue_raw = load_yaml(args.fatigue_parameters)
        preflight_adapter = prepare_fatigue_adapter(
            preflight, fatigue_raw
        )
        fatigue_metadata = fatigue_run_metadata(
            preflight_adapter, args.fatigue_parameters
        )
        backlog_json.dumps(fatigue_metadata, allow_nan=False)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    results_dir = os.path.join(
        "results", f"stage_a_{run_label}_{timestamp}"
    )
    os.makedirs(results_dir, exist_ok=False)

    save_csv(
        seeds,
        os.path.join(results_dir, "selected_seeds.csv"),
    )
    save_json(
        {
            "mode": args.mode,
            "run_type": run_label,
            "smoke_check": args.smoke_check,
            "experiment": config,
            "arms": arms_config,
            **fatigue_metadata,
            "observation_semantics": "dispatch_termination_time",
            "reporting_semantics": {
                "throughput_denominator": "configured_shift_duration_s",
                "final_fatigue": "maximum_operator_fatigue_at_dispatch_termination",
                "final_ergonomic_risk": "maximum_operator_endpoint_risk_with_zero_cognitive_load",
                "post_dispatch_recovery": "not_simulated",
                "safety_violations": "count_of_executed_assignments_flagged_unsafe_at_selection",
                "safety_assessment_basis": fatigue_metadata["safety_semantics"],
                "veto_events": "unsafe_candidate_count_accumulated_on_successful_veto_enabled_selections",
                "collision_geometry": "operator_and_robot_ids_used_as_positions",
                "safe_zone_geometry": "operator_id_used_as_position_with_fixed_zone_center_2_5",
                "continuous_safety_trace": "not_recorded",
            },
        },
        os.path.join(results_dir, "run_configuration.json"),
    )
    print(f"Run type: {run_label}; shifts selected: {len(seeds)}")
    print(f"Output directory: {results_dir}")

    all_metrics = []

    for seed_row in seeds:
        arm = seed_row["arm"]
        replicate = seed_row["replicate"]
        scenario_seed = seed_row["scenario_seed"]
        search_seed = seed_row["search_seed"]

        scenario = build_scenario(
            config=config,
            scenario_seed=scenario_seed,
            scenario_id=replicate,
            disturbance_events=[],
        )

        if args.fatigue_parameters is not None:
            prepare_fatigue_adapter(scenario, fatigue_raw)

        scenario.disturbance_events = generate_disturbance_events(
            config,
            scenario_seed,
            operator_ids=[operator.operator_id for operator in scenario.operators],
            robot_ids=[robot.robot_id for robot in scenario.robots],
        )

        result = run_shift(
            arm=arm,
            scenario=scenario,
            config=config,
            search_seed=search_seed,
            arm_config=arms_config["arms"][arm],
        )

        metric = calculate_shift_metrics(result)
        all_metrics.append(metric)

        print(
            f"Completed {arm} replicate {replicate}: "
            f"tasks={metric.completed_tasks}, "
            f"throughput={metric.throughput_tasks_per_hour:.2f}, "
            f"fatigue={metric.final_fatigue:.3f}"
        )

    rows = metrics_to_rows(all_metrics)

    save_csv(
        rows,
        os.path.join(results_dir, "shift_metrics.csv"),
    )

    summary = calculate_summary(all_metrics)

    save_json(
        summary,
        os.path.join(results_dir, "summary_statistics.json"),
    )

    comparisons = calculate_comparisons(all_metrics)

    save_comparison_csv(
        comparisons,
        os.path.join(results_dir, "paired_comparisons.csv"),
    )

    plot_safety_violations(rows, results_dir)
    plot_fatigue(rows, results_dir)
    plot_throughput_energy_tradeoff(rows, results_dir)
    plot_wellbeing_productivity_tradeoff(rows, results_dir)

    elapsed_time = time.time() - start_time

    print()
    print("Experiment complete.")
    print(f"Total runtime: {elapsed_time:.2f} seconds")
    print(f"Results saved in: {results_dir}")


if __name__ == "__main__":
    main()
