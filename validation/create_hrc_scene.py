from pathlib import Path

from coppeliasim_zmqremoteapi_client import RemoteAPIClient


SCENE_PATH = str(Path(__file__).resolve().parent / "hrc_validation_scene.ttt")


def create_box(sim, name, size, position, color):
    handle = sim.createPrimitiveShape(
        sim.primitiveshape_cuboid,
        size,
        0,
    )
    sim.setObjectAlias(handle, name)
    sim.setObjectPosition(handle, -1, position)
    sim.setShapeColor(handle, None, sim.colorcomponent_ambient_diffuse, color)
    return handle


def create_marker(sim, name, position):
    handle = sim.createDummy(0.05)
    sim.setObjectAlias(handle, name)
    sim.setObjectPosition(handle, -1, position)
    return handle


def main():
    client = RemoteAPIClient()
    sim = client.require("sim")

    print("Connected to CoppeliaSim.")

    # Start from an empty scene so the result is reproducible.
    sim.closeScene()

    # Factory floor.
    create_box(
        sim,
        "FactoryFloor",
        [4.0, 3.0, 0.05],
        [0.0, 0.0, -0.025],
        [0.75, 0.75, 0.75],
    )

    # Simplified collaborative-robot workstation.
    create_box(
        sim,
        "RobotWorkstation",
        [0.8, 0.8, 0.8],
        [-1.2, 0.0, 0.4],
        [0.35, 0.35, 0.45],
    )

    # Two assembly workstations.
    create_box(
        sim,
        "Workstation_A",
        [0.6, 0.6, 0.7],
        [0.8, 0.8, 0.35],
        [0.30, 0.55, 0.75],
    )

    create_box(
        sim,
        "Workstation_B",
        [0.6, 0.6, 0.7],
        [0.8, -0.8, 0.35],
        [0.30, 0.55, 0.75],
    )

    # Simplified human-operator placeholder.
    create_box(
        sim,
        "HumanOperator",
        [0.35, 0.35, 1.10],
        [0.0, 0.0, 0.55],
        [0.85, 0.55, 0.20],
    )

    # Task markers used by the scheduler handoff test.
    create_marker(sim, "Task_A_Start", [0.8, 0.8, 0.75])
    create_marker(sim, "Task_A_End", [0.0, 0.0, 0.75])
    create_marker(sim, "Task_B_Start", [0.8, -0.8, 0.75])
    create_marker(sim, "Task_B_End", [0.0, 0.0, 0.75])

    # Save the generated scene for repeatable validation.
    sim.saveScene(SCENE_PATH)
    print(f"Saved reproducible scene: {SCENE_PATH}")

    # Run a short deterministic smoke test.
    sim.setStepping(True)
    sim.startSimulation()

    for step in range(10):
        sim.step()
        simulation_time = sim.getSimulationTime()
        print(f"Step {step + 1}: simulation time = {simulation_time:.3f} s")

    sim.stopSimulation()
    print("Minimal HRC scene validation completed.")


if __name__ == "__main__":
    main()