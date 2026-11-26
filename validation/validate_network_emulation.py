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
RESULTS_PATH = Path("validation") / "network_emulation_results.csv"

SIMULATION_TIMESTEP_S = 0.05
NUMBER_OF_ASSIGNMENTS = 12

BASE_LATENCY_MS = 50.0
JITTER_MS = 10.0
PACKET_LOSS_PROBABILITY = 0.02
MAXIMUM_RETRIES = 3

TASK_MARKERS = [
    ("Task_A_Start", "Task_A_End"),
    ("Task_B_Start", "Task_B_End"),
]


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

    assignments = result.assignments[:NUMBER_OF_ASSIGNMENTS]

    print(
        f"Validating {len(assignments)} scheduler assignments "
        f"under emulated network conditions."
    )

    network = NetworkEmulatedRemoteAPI(
        base_latency_ms=BASE_LATENCY_MS,
        jitter_ms=JITTER_MS,
        packet_loss_probability=PACKET_LOSS_PROBABILITY,
        maximum_retries=MAXIMUM_RETRIES,
        seed=42,
    )

    sim = network.sim

    print(
        "Connected to CoppeliaSim through the network-emulation layer."
    )

    network.call("loadScene", SCENE_PATH)

    task_token = network.call("createDummy", 0.10)
    network.call(
        "setObjectAlias",
        task_token,
        "NetworkEmulatedTaskToken",
    )

    marker_handles = []

    for start_name, end_name in TASK_MARKERS:
        start_handle = network.call("getObject", "/" + start_name)
        end_handle = network.call("getObject", "/" + end_name)

        marker_handles.append(
            {
                "start": start_handle,
                "end": end_handle,
                "start_name": start_name,
                "end_name": end_name,
            }
        )

    rows = []

    network.call("setStepping", True)
    network.call("startSimulation")

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

        executed_end = network.call("getSimulationTime")
        executed_start = executed_end - assignment.duration_s

        rows.append(
            {
                "arm": arm,
                "assignment_index": assignment_index + 1,
                "task_id": assignment.task_id,
                "operator_id": assignment.operator_id,
                "robot_id": assignment.robot_id,
                "planned_duration_s": assignment.duration_s,
                "executed_start_s": executed_start,
                "executed_end_s": executed_end,
                "executed_duration_s": assignment.duration_s,
                "vetoed": assignment.vetoed,
                "safety_violation": assignment.safety_violation,
                "start_marker": markers["start_name"],
                "end_marker": markers["end_name"],
            }
        )

    network.call("stopSimulation")

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = network.summary()

    print()
    print("Network-emulation validation summary")
    print(f"Assignments executed: {len(rows)}")
    print(f"Commands sent: {summary['commands_sent']}")
    print(f"Commands succeeded: {summary['commands_succeeded']}")
    print(f"Commands dropped: {summary['commands_dropped']}")
    print(f"Commands retried: {summary['commands_retried']}")
    print(
        f"Mean application RTT: "
        f"{summary['mean_round_trip_ms']:.3f} ms"
    )
    print(
        f"Maximum application RTT: "
        f"{summary['maximum_round_trip_ms']:.3f} ms"
    )
    print(
        f"Packet-loss setting: "
        f"{PACKET_LOSS_PROBABILITY:.3f}"
    )
    print(
        f"Latency setting: "
        f"{BASE_LATENCY_MS:.1f} ms +/- {JITTER_MS:.1f} ms"
    )
    print(f"Saved assignment results: {RESULTS_PATH}")
    print("Network-emulation validation completed.")


if __name__ == "__main__":
    main()
