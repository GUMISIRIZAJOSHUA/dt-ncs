from pathlib import Path


VALIDATION_DIR = Path("validation")
VALIDATION_DIR.mkdir(exist_ok=True)

CLIENT_PATH = VALIDATION_DIR / "network_emulated_client.py"
VALIDATOR_PATH = VALIDATION_DIR / "validate_network_emulation.py"

client_code = '''import random
import time
from typing import Any

from coppeliasim_zmqremoteapi_client import RemoteAPIClient


class NetworkEmulatedRemoteAPI:
    def __init__(
        self,
        base_latency_ms: float = 50.0,
        jitter_ms: float = 10.0,
        packet_loss_probability: float = 0.02,
        maximum_retries: int = 3,
        seed: int = 42,
    ):
        self.base_latency_ms = base_latency_ms
        self.jitter_ms = jitter_ms
        self.packet_loss_probability = packet_loss_probability
        self.maximum_retries = maximum_retries
        self.rng = random.Random(seed)

        self.commands_sent = 0
        self.commands_dropped = 0
        self.commands_retried = 0
        self.commands_succeeded = 0
        self.round_trip_times_ms = []

        client = RemoteAPIClient()
        self.sim = client.require("sim")

    def _emulate_transmission(self) -> None:
        latency_ms = self.base_latency_ms + self.rng.uniform(
            -self.jitter_ms,
            self.jitter_ms,
        )

        latency_ms = max(0.0, latency_ms)
        time.sleep(latency_ms / 1000.0)

    def call(self, function_name: str, *args: Any) -> Any:
        self.commands_sent += 1

        for attempt in range(self.maximum_retries + 1):
            self._emulate_transmission()

            if self.rng.random() < self.packet_loss_probability:
                self.commands_dropped += 1

                if attempt < self.maximum_retries:
                    self.commands_retried += 1
                    continue

                raise RuntimeError(
                    f"Network-emulated command failed after "
                    f"{self.maximum_retries} retries: {function_name}"
                )

            start_time = time.perf_counter()
            result = getattr(self.sim, function_name)(*args)
            round_trip_ms = (
                time.perf_counter() - start_time
            ) * 1000.0

            self.round_trip_times_ms.append(round_trip_ms)
            self.commands_succeeded += 1

            return result

        raise RuntimeError(
            f"Unreachable network-emulation state: {function_name}"
        )

    def summary(self) -> dict:
        if self.round_trip_times_ms:
            mean_rtt = sum(self.round_trip_times_ms) / len(
                self.round_trip_times_ms
            )

            minimum_rtt = min(self.round_trip_times_ms)
            maximum_rtt = max(self.round_trip_times_ms)
        else:
            mean_rtt = 0.0
            minimum_rtt = 0.0
            maximum_rtt = 0.0

        return {
            "commands_sent": self.commands_sent,
            "commands_succeeded": self.commands_succeeded,
            "commands_dropped": self.commands_dropped,
            "commands_retried": self.commands_retried,
            "mean_round_trip_ms": mean_rtt,
            "minimum_round_trip_ms": minimum_rtt,
            "maximum_round_trip_ms": maximum_rtt,
            "packet_loss_probability": self.packet_loss_probability,
            "base_latency_ms": self.base_latency_ms,
            "jitter_ms": self.jitter_ms,
        }
'''

validator_code = '''import csv
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
'''

CLIENT_PATH.write_text(client_code, encoding="utf-8")
VALIDATOR_PATH.write_text(validator_code, encoding="utf-8")

print(f"Created: {CLIENT_PATH}")
print(f"Created: {VALIDATOR_PATH}")