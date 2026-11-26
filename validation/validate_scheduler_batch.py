import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from coppeliasim_zmqremoteapi_client import RemoteAPIClient

from src.io_utils import load_yaml
from src.disturbances import generate_disturbance_events
from src.scenario import build_scenario
from src.scheduler import run_shift


SCENE_PATH = str(Path("validation") / "hrc_validation_scene.ttt")
RESULTS_PATH = Path("validation") / "scheduler_batch_results.csv"

NUMBER_OF_ASSIGNMENTS = 20
SIMULATION_TIMESTEP_S = 0.05

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
        f"Scheduler produced {len(result.assignments)} assignments; "
        f"validating first {len(assignments)}."
    )

    client = RemoteAPIClient()
    sim = client.require("sim")

    print("Connected to CoppeliaSim.")
    sim.loadScene(SCENE_PATH)

    task_token = sim.createDummy(0.10)
    sim.setObjectAlias(task_token, "SchedulerTaskToken")

    marker_handles = []

    for start_name, end_name in TASK_MARKERS:
        start_handle = sim.getObject("/" + start_name)
        end_handle = sim.getObject("/" + end_name)

        marker_handles.append(
            {
                "start": start_handle,
                "end": end_handle,
                "start_name": start_name,
                "end_name": end_name,
            }
        )

    rows = []

    sim.setStepping(True)
    sim.startSimulation()

    for assignment_index, assignment in enumerate(assignments):
        markers = marker_handles[assignment_index % len(marker_handles)]

        start_position = sim.getObjectPosition(markers["start"], -1)
        end_position = sim.getObjectPosition(markers["end"], -1)

        sim.setObjectPosition(task_token, -1, start_position)

        steps = max(1, round(assignment.duration_s / SIMULATION_TIMESTEP_S))

        print(
            f"Assignment {assignment_index + 1}: "
            f"task={assignment.task_id}, "
            f"operator={assignment.operator_id}, "
            f"robot={assignment.robot_id}, "
            f"duration={assignment.duration_s:.3f} s, "
            f"steps={steps}"
        )

        for step in range(steps):
            fraction = (step + 1) / steps

            token_position = [
                start_position[index]
                + fraction * (end_position[index] - start_position[index])
                for index in range(3)
            ]

            sim.setObjectPosition(task_token, -1, token_position)
            sim.step()

        executed_end = sim.getSimulationTime()
        executed_start = executed_end - assignment.duration_s

        rows.append(
            {
                "arm": arm,
                "assignment_index": assignment_index + 1,
                "task_id": assignment.task_id,
                "operator_id": assignment.operator_id,
                "robot_id": assignment.robot_id,
                "planned_start_s": assignment.start_time_s,
                "planned_completion_s": assignment.completion_time_s,
                "planned_duration_s": assignment.duration_s,
                "executed_start_s": executed_start,
                "executed_end_s": executed_end,
                "executed_duration_s": assignment.duration_s,
                "energy_kj": assignment.energy_kj,
                "vetoed": assignment.vetoed,
                "safety_violation": assignment.safety_violation,
                "start_marker": markers["start_name"],
                "end_marker": markers["end_name"],
            }
        )

    sim.stopSimulation()

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    safety_violations = sum(
        row["safety_violation"] for row in rows
    )

    vetoed_assignments = sum(
        row["vetoed"] for row in rows
    )

    print(
        f"Batch validation complete: assignments={len(rows)}, "
        f"safety_violations={safety_violations}, "
        f"vetoed_assignments={vetoed_assignments}."
    )
    print(f"Saved batch results: {RESULTS_PATH}")


if __name__ == "__main__":
    main()