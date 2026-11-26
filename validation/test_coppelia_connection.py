from coppeliasim_zmqremoteapi_client import RemoteAPIClient

def main():
    client = RemoteAPIClient()
    sim = client.require("sim")
    print("Connected to CoppeliaSim.")
    sim.setStepping(True)
    sim.startSimulation()
    for _ in range(10):
        sim.step()
        print("Simulation time:", sim.getSimulationTime())
    sim.stopSimulation()
    print("Connection smoke test completed.")

if __name__ == "__main__":
    main()
