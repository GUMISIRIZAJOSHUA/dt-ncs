import time, statistics as st
from pathlib import Path
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

client = RemoteAPIClient()
sim = client.require("sim")
out = []
out.append("CoppeliaSim full version: " + str(sim.getInt32Param(sim.intparam_program_full_version)))
sim.loadScene(str(Path("validation/hrc_validation_scene.ttt").resolve()))
out.append("simulation time step (s): " + str(sim.getSimulationTimeStep()))

sim.setStepping(True)
sim.startSimulation()
t0 = sim.getSimulationTime()
for _ in range(20): sim.step()
out.append("stepping: 20 steps advanced sim time by " + str(round(sim.getSimulationTime() - t0, 4)) + " s")
lat = [(lambda a: (sim.getSimulationTime(), (time.perf_counter() - a) * 1000)[1])(time.perf_counter()) for _ in range(200)]
lat.sort()
out.append("getSimulationTime latency ms: n=%d median=%.3f p95=%.3f max=%.3f" % (len(lat), st.median(lat), lat[int(0.95 * len(lat)) - 1], lat[-1]))
sim.stopSimulation()
while sim.getSimulationState() != sim.simulation_stopped: time.sleep(0.05)

sim.setStepping(False)
sim.startSimulation()
w0 = time.perf_counter(); s0 = sim.getSimulationTime()
time.sleep(2.0)
w1 = time.perf_counter(); s1 = sim.getSimulationTime()
out.append("non-stepping: %.3f s sim time over %.3f s wall clock" % (s1 - s0, w1 - w0))
sim.stopSimulation()
while sim.getSimulationState() != sim.simulation_stopped: time.sleep(0.05)

text = "\n".join(out)
Path("probe_coppelia.txt").write_text(text, encoding="utf-8")
print(text)