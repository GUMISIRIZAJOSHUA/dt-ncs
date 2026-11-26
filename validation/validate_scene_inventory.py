from pathlib import Path

from coppeliasim_zmqremoteapi_client import RemoteAPIClient


SCENE_PATH = str(Path("validation") / "hrc_validation_scene.ttt")

EXPECTED_OBJECTS = [
    "FactoryFloor",
    "RobotWorkstation",
    "Workstation_A",
    "Workstation_B",
    "HumanOperator",
    "Task_A_Start",
    "Task_A_End",
    "Task_B_Start",
    "Task_B_End",
]


def main():
    client = RemoteAPIClient()
    sim = client.require("sim")

    print("Connected to CoppeliaSim.")
    sim.loadScene(SCENE_PATH)
    print(f"Loaded scene: {SCENE_PATH}")

    handles = {}

    for name in EXPECTED_OBJECTS:
        handle = sim.getObject("/" + name)
        handles[name] = handle
        position = sim.getObjectPosition(handle, -1)
        print(
            f"{name}: handle={handle}, "
            f"position=({position[0]:.3f}, {position[1]:.3f}, {position[2]:.3f})"
        )

    missing = [name for name in EXPECTED_OBJECTS if handles.get(name) is None]
    if missing:
        raise RuntimeError(f"Missing expected scene objects: {missing}")

    sim.setStepping(True)
    sim.startSimulation()

    for step in range(5):
        sim.step()

        human_position = sim.getObjectPosition(handles["HumanOperator"], -1)
        task_a_position = sim.getObjectPosition(handles["Task_A_End"], -1)

        print(
            f"Step {step + 1}: "
            f"time={sim.getSimulationTime():.3f} s, "
            f"human=({human_position[0]:.3f}, {human_position[1]:.3f}, "
            f"{human_position[2]:.3f}), "
            f"task_A_end=({task_a_position[0]:.3f}, "
            f"{task_a_position[1]:.3f}, {task_a_position[2]:.3f})"
        )

    sim.stopSimulation()
    print("Scene inventory and state-read validation completed.")


if __name__ == "__main__":
    main()