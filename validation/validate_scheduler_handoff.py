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
RESULTS_PATH = Path("validation") / "scheduler_handoff_results.csv"

TASK_MARKERS = {
    0: ("Task_A_Start", "Task_A_End"),
    1: ("Task_B_Start", "Task_B_End"),
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
        f"Scheduler produced {len(result.assignments)} assignments "
        f"for arm {arm}."
    )

    if len(result.assignments) < 2:
        raise RuntimeError(
            "The scheduler produced fewer than two assignments; "
            "cannot run the two-task handoff test."
        )

    selected_assignments = result.assignments[:2]

    client = RemoteAPIClient()
    sim = client.require("sim")

    print("Connected to CoppeliaSim.")
    sim.loadScene(SCENE_PATH)

    task_token = sim.createDummy(0.10)
    sim.setObjectAlias(task_token, "SchedulerTaskToken")

    rows = []

    sim.setStepping(True)
    sim.startSimulation()

    for assignment_index, assignment in enumerate(selected_assignments):
        start_marker_name, end_marker_name = TASK_MARKERS[assignment_index]

        start_handle = sim.getObject("/" + start_marker_name)
        end_handle = sim.getObject("/" + end_marker_name)

        start_position = sim.getObjectPosition(start_handle, -1)
        end_position = sim.getObjectPosition(end_handle, -1)

        sim.setObjectPosition(task_token, -1, start_position)

        steps = max(1, round(assignment.duration_s / 0.05))

        print(
            f"Executing assignment {assignment_index + 1}: "
            f"task_id={assignment.task_id}, "
            f"operator={assignment.operator_id}, "
            f"robot={assignment.robot_id}, "
            f"planned_duration={assignment.duration_s:.3f} s, "
            f"simulation_steps={steps}"
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

        execution_start = sim.getSimulationTime() - assignment.duration_s
        execution_end = sim.getSimulationTime()

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
                "executed_start_s": execution_start,
                "executed_end_s": execution_end,
                "executed_duration_s": assignment.duration_s,
                "energy_kj": assignment.energy_kj,
                "vetoed": assignment.vetoed,
                "safety_violation": assignment.safety_violation,
                "start_marker": start_marker_name,
                "end_marker": end_marker_name,
            }
        )

        print(
            f"Completed assignment {assignment_index + 1}: "
            f"executed_time={execution_end:.3f} s, "
            f"safety_violation={assignment.safety_violation}"
        )

    sim.stopSimulation()

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved handoff results: {RESULTS_PATH}")
    print("Scheduler-to-CoppeliaSim handoff validation completed.")


if __name__ == "__main__":
    main()