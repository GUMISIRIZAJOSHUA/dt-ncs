import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from network_emulated_client import NetworkEmulatedRemoteAPI

from src.io_utils import load_yaml
from src.disturbances import generate_disturbance_events
from src.scenario import build_scenario
from src.scheduler import run_shift


SCENE_PATH = str(Path("validation") / "hrc_validation_scene.ttt")
RESULTS_PATH = Path("validation") / "network_condition_sweep_results.csv"

SIMULATION_TIMESTEP_S = 0.05
NUMBER_OF_ASSIGNMENTS = 12

NETWORK_CONDITIONS = [
    {
        "condition": "degraded_delay",
        "base_latency_ms": 100.0,
        "jitter_ms": 20.0,
        "packet_loss_probability": 0.03,
    },
]
TASK_MARKERS = [
    ("Task_A_Start", "Task_A_End"),
    ("Task_B_Start", "Task_B_End"),
]


def execute_condition(
    condition,
    config,
    scenario,
    result,
):
    assignments = result.assignments[:NUMBER_OF_ASSIGNMENTS]

    network = NetworkEmulatedRemoteAPI(
        base_latency_ms=condition["base_latency_ms"],
        jitter_ms=condition["jitter_ms"],
        packet_loss_probability=condition[
            "packet_loss_probability"
        ],
        maximum_retries=10,
        seed=42,
    )

    sim = network.sim

    network.call("loadScene", SCENE_PATH)

    task_token = network.call("createDummy", 0.10)
    network.call(
        "setObjectAlias",
        task_token,
        "NetworkSweepTaskToken",
    )

    marker_handles = []

    for start_name, end_name in TASK_MARKERS:
        marker_handles.append(
            {
                "start": network.call(
                    "getObject",
                    "/" + start_name,
                ),
                "end": network.call(
                    "getObject",
                    "/" + end_name,
                ),
                "start_name": start_name,
                "end_name": end_name,
            }
        )

    network.call("setStepping", True)
    network.call("startSimulation")

    completed_assignments = 0

    for assignment_index, assignment in enumerate(assignments):
        markers = marker_handles[
            assignment_index % len(marker_handles)
        ]

        start_position = network.call(
            "getObjectPosition",
            markers["start"],
            -1,
        )

        end_position = network.call(
            "getObjectPosition",
            markers["end"],
            -1,
        )

        network.call(
            "setObjectPosition",
            task_token,
            -1,
            start_position,
        )

        steps = max(
            1,
            round(assignment.duration_s / SIMULATION_TIMESTEP_S),
        )

        for step in range(steps):
            fraction = (step + 1) / steps

            token_position = [
                start_position[index]
                + fraction * (end_position[index] - start_position[index])
                for index in range(3)
            ]

            network.call(
                "setObjectPosition",
                task_token,
                -1,
                token_position,
            )

            network.call("step")

        completed_assignments += 1

    final_simulation_time = network.call("getSimulationTime")
    network.call("stopSimulation")

    summary = network.summary()

    return {
        "condition": condition["condition"],
        "base_latency_ms": condition["base_latency_ms"],
        "jitter_ms": condition["jitter_ms"],
        "packet_loss_probability": condition[
            "packet_loss_probability"
        ],
        "assignments_executed": completed_assignments,
        "scheduler_makespan_s": result.makespan_s,
        "simulator_makespan_s": final_simulation_time,
        "makespan_difference_s": final_simulation_time
        - result.makespan_s,
        "commands_sent": summary["commands_sent"],
        "commands_succeeded": summary["commands_succeeded"],
        "commands_dropped": summary["commands_dropped"],
        "commands_retried": summary["commands_retried"],
        "unrecoverable_failures": summary["commands_sent"]
        - summary["commands_succeeded"],
        "mean_local_rtt_ms": summary["mean_round_trip_ms"],
        "maximum_local_rtt_ms": summary["maximum_round_trip_ms"],
        "safety_violations": result.safety_violations,
        "veto_events": result.veto_events,
    }


def main():
    config = load_yaml("configs/experiment.yaml")
    tasks_config = load_yaml("configs/tasks.yaml")
    config["tasks"] = tasks_config["tasks"]

    scenario_seed = 1
    search_seed = 1
    arm = "B3"

    disturbance_events = generate_disturbance_events(
        config,
        scenario_seed,
    )

    scenario = build_scenario(
        config=config,
        scenario_seed=scenario_seed,
        scenario_id=1,
        disturbance_events=disturbance_events,
    )

    result = run_shift(
        arm=arm,
        scenario=scenario,
        config=config,
        search_seed=search_seed,
    )

    print(
        f"Scheduler produced {len(result.assignments)} assignments; "
        f"validating first {NUMBER_OF_ASSIGNMENTS} under "
        f"{len(NETWORK_CONDITIONS)} network conditions."
    )

    rows = []

    for condition in NETWORK_CONDITIONS:
        print()
        print(
            f"Running condition: {condition['condition']} "
            f"({condition['base_latency_ms']:.0f} ms +/- "
            f"{condition['jitter_ms']:.0f} ms, "
            f"{condition['packet_loss_probability'] * 100:.1f}% loss)"
        )

        row = execute_condition(
            condition,
            config,
            scenario,
            result,
        )

        rows.append(row)

        print(
            f"Completed: assignments={row['assignments_executed']}, "
            f"commands={row['commands_sent']}, "
            f"drops={row['commands_dropped']}, "
            f"retries={row['commands_retried']}, "
            f"failures={row['unrecoverable_failures']}"
        )

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print()
    print("Network-condition sweep complete.")
    print(f"Saved results: {RESULTS_PATH}")


if __name__ == "__main__":
    main()