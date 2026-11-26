import json
from pathlib import Path

from src.io_utils import load_yaml, ensure_directory, save_csv, save_json
from src.scenario import build_scenario
from src.scheduler import run_shift
from src.metrics import calculate_shift_metrics


VERIFICATION_ARMS = ["B1", "B2", "B3b", "B3"]
SCENARIO_SEED = 101
SEARCH_SEED = 202


def metrics_to_row(metric):
    return {
        "arm": metric.arm,
        "scenario_id": metric.scenario_id,
        "completed_tasks": metric.completed_tasks,
        "unfinished_jobs_by_type": json.dumps(
            metric.unfinished_jobs_by_type,
            sort_keys=True,
        ),
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


def main():
    config = load_yaml("configs/experiment.yaml")
    tasks_config = load_yaml("configs/tasks.yaml")
    arms_config = load_yaml("configs/arms.yaml")

    config["tasks"] = tasks_config["tasks"]

    config["job_quantities"] = {
        task_id: 1
        for task_id in range(1, 13)
    }

    config["fatigue_noise_sigma"] = 0.0

    output_dir = Path("results/verification")
    ensure_directory(str(output_dir))

    rows = []
    result_records = []

    for arm in VERIFICATION_ARMS:
        print(f"Running verification case for {arm}...")

        scenario = build_scenario(
            config=config,
            scenario_seed=SCENARIO_SEED,
            scenario_id=1,
            disturbance_events=[],
        )

        arm_config = arms_config["arms"][arm]

        result = run_shift(
            arm=arm,
            scenario=scenario,
            config=config,
            search_seed=SEARCH_SEED,
            arm_config=arm_config,
        )

        metric = calculate_shift_metrics(result)
        rows.append(metrics_to_row(metric))

        result_records.append(
            {
                "arm": arm,
                "scenario_seed": SCENARIO_SEED,
                "search_seed": SEARCH_SEED,
                "termination_reason": result.termination_reason,
                "completed_tasks": result.completed_tasks,
                "assignments": [
                    {
                        "job_id": assignment.job_id,
                        "task_id": assignment.task_id,
                        "operator_id": assignment.operator_id,
                        "robot_id": assignment.robot_id,
                        "start_time_s": assignment.start_time_s,
                        "completion_time_s": assignment.completion_time_s,
                        "duration_s": assignment.duration_s,
                        "energy_kj": assignment.energy_kj,
                        "defect_probability": assignment.defect_probability,
                        "objective_score": assignment.objective_score,
                        "vetoed": assignment.vetoed,
                        "safety_violation": assignment.safety_violation,
                    }
                    for assignment in result.assignments
                ],
            }
        )

        print(
            f"Completed {arm}: "
            f"tasks={metric.completed_tasks}, "
            f"throughput={metric.throughput_tasks_per_hour:.2f}, "
            f"final_fatigue={metric.final_fatigue:.3f}"
        )

    save_csv(
        rows,
        str(output_dir / "verification_metrics.csv"),
    )

    save_json(
        {
            "verification_type": "deterministic_base_case",
            "scenario_seed": SCENARIO_SEED,
            "search_seed": SEARCH_SEED,
            "job_count": 12,
            "operator_count": 2,
            "robot_count": 2,
            "shift_duration_s": config["shift_duration_s"],
            "disturbance_events": [],
            "fatigue_noise_sigma": config["fatigue_noise_sigma"],
            "arms": VERIFICATION_ARMS,
            "results": result_records,
        },
        str(output_dir / "verification_results.json"),
    )

    print()
    print("Verification complete.")
    print(f"Results saved in: {output_dir}")


if __name__ == "__main__":
    main()