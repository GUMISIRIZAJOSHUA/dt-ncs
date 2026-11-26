import csv, hashlib, json, math, platform, statistics as st, sys, time
from datetime import datetime
from importlib import metadata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from coppeliasim_zmqremoteapi_client import RemoteAPIClient
from src.io_utils import load_yaml
from src.disturbances import generate_disturbance_events
from src.scenario import build_scenario
from src.scheduler import run_shift
from run_experiment import prepare_fatigue_adapter

ARM = "B3"
SCENARIO_SEED = 1
SEARCH_SEED = 1
N_JOBS = 5
MAX_SPAN_S = 300.0
LATENCY_N = 200
TIMEOUT_S = 1.0
SCENE = PROJECT_ROOT / "validation" / "hrc_validation_scene.ttt"
OUT_DIR = PROJECT_ROOT / "results" / ("protocol_566_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
MARKERS = [("Task_A_Start", "Task_A_End"), ("Task_B_Start", "Task_B_End")]


PILOT = PROJECT_ROOT / "results" / "stage_a_pilot_20261126_132907_625348"
EXPECTED_COMPLETED = 1137
EXPECTED_ENERGY_KJ = 57978.5
REPLAY = {}


def load_jobs():
    config = load_yaml(str(PROJECT_ROOT / "configs" / "experiment.yaml"))
    config["tasks"] = load_yaml(str(PROJECT_ROOT / "configs" / "tasks.yaml"))["tasks"]
    arms_config = load_yaml(str(PROJECT_ROOT / "configs" / "arms.yaml"))
    run_cfg = json.loads((PILOT / "run_configuration.json").read_text(encoding="utf-8"))
    fatigue_path = run_cfg.get("fatigue_parameter_source") or str(PROJECT_ROOT / "configs" / "fatigue_synthetic_benchmark.yaml")
    fatigue_raw = load_yaml(fatigue_path)
    with (PILOT / "selected_seeds.csv").open(encoding="utf-8-sig", newline="") as f:
        row = [r for r in csv.DictReader(f) if r["arm"] == ARM and r["replicate"] == "1"][0]
    scenario_seed = int(row["scenario_seed"])
    search_seed = int(row["search_seed"])
    scenario = build_scenario(config=config, scenario_seed=scenario_seed, scenario_id=int(row["replicate"]), disturbance_events=[])
    prepare_fatigue_adapter(scenario, fatigue_raw)
    scenario.disturbance_events = generate_disturbance_events(
        config, scenario_seed,
        operator_ids=[o.operator_id for o in scenario.operators],
        robot_ids=[r.robot_id for r in scenario.robots])
    result = run_shift(arm=ARM, scenario=scenario, config=config, search_seed=search_seed, arm_config=arms_config["arms"][ARM])
    executed = [a for a in result.assignments if not a.vetoed]
    REPLAY.update({"scenario_seed": scenario_seed, "search_seed": search_seed, "fatigue_source": fatigue_path,
                   "non_vetoed_assignments": len(executed), "expected_completed": EXPECTED_COMPLETED,
                   "assignment_energy_kj": sum(a.energy_kj for a in executed), "expected_energy_kj": EXPECTED_ENERGY_KJ})
    print("Replay check:", REPLAY)
    ok = sorted(executed, key=lambda a: (a.start_time_s, a.task_id))[:N_JOBS]
    t0 = ok[0].start_time_s
    return [{"idx": i, "task_id": a.task_id, "operator": a.operator_id, "robot": a.robot_id,
             "p_start": a.start_time_s - t0, "p_end": a.completion_time_s - t0,
             "sched_dur": a.duration_s} for i, a in enumerate(ok)]


def start(sim, stepping):
    sim.setStepping(stepping)
    sim.setBoolParam(sim.boolparam_realtime_simulation, not stepping)
    sim.startSimulation()


def stop(sim):
    sim.stopSimulation()
    while sim.getSimulationState() != sim.simulation_stopped:
        time.sleep(0.05)


def run_sequence(sim, jobs, stepping):
    sim.loadScene(str(SCENE))
    pts = []
    tokens = []
    for i, j in enumerate(jobs):
        s_name, e_name = MARKERS[i % 2]
        pts.append((sim.getObjectPosition(sim.getObject("/" + s_name), -1),
                    sim.getObjectPosition(sim.getObject("/" + e_name), -1)))
        h = sim.createDummy(0.08)
        sim.setObjectAlias(h, "Job_" + str(j["task_id"]))
        tokens.append(h)
    rec = [{"start": None, "end": None} for _ in jobs]
    span = max(j["p_end"] for j in jobs)
    start(sim, stepping)
    wall0 = time.perf_counter()
    sim_t0 = sim.getSimulationTime()
    try:
        while any(r["end"] is None for r in rec):
            t = sim.getSimulationTime() - sim_t0
            for j, r, h, (a, b) in zip(jobs, rec, tokens, pts):
                if r["start"] is None and t >= j["p_start"]:
                    r["start"] = t
                if r["start"] is not None and r["end"] is None:
                    f = min(1.0, (t - j["p_start"]) / max(1e-9, j["p_end"] - j["p_start"]))
                    sim.setObjectPosition(h, -1, [a[k] + f * (b[k] - a[k]) for k in range(3)])
                    if t >= j["p_end"]:
                        r["end"] = t
            if stepping:
                sim.step()
            else:
                time.sleep(0.005)
            if time.perf_counter() - wall0 > 120 + 4 * span:
                raise RuntimeError("sequence timed out")
    finally:
        wall = time.perf_counter() - wall0
        sim_elapsed = sim.getSimulationTime() - sim_t0
        stop(sim)
    return rec, wall, sim_elapsed


def overlaps(rows, key, s, e):
    n = 0
    for i in range(len(rows)):
        for k in range(i + 1, len(rows)):
            if rows[i][key] == rows[k][key] and min(rows[i][e], rows[k][e]) - max(rows[i][s], rows[k][s]) > 1e-9:
                n += 1
    return n


def evaluate(jobs, rec, tol):
    rows = []
    for j, r in zip(jobs, rec):
        rows.append({"idx": j["idx"], "task_id": j["task_id"], "operator": j["operator"], "robot": j["robot"],
                     "planned_start_s": j["p_start"], "planned_end_s": j["p_end"],
                     "scheduler_duration_s": j["sched_dur"],
                     "executed_start_s": r["start"], "executed_end_s": r["end"],
                     "planned_duration_s": j["p_end"] - j["p_start"],
                     "executed_duration_s": r["end"] - r["start"]})
    for r in rows:
        r["duration_error_s"] = r["executed_duration_s"] - r["planned_duration_s"]
    order = [r["idx"] for r in sorted(rows, key=lambda x: (x["executed_start_s"], x["planned_start_s"], x["idx"]))]
    chk = {"start_order_matches_plan": order == sorted(order),
           "max_abs_duration_error_s": max(abs(r["duration_error_s"]) for r in rows),
           "min_start_lag_s": min(r["executed_start_s"] - r["planned_start_s"] for r in rows),
           "tolerance_s": tol}
    for key in ("operator", "robot"):
        chk["planned_overlaps_" + key] = overlaps(rows, key, "planned_start_s", "planned_end_s")
        chk["executed_overlaps_" + key] = overlaps(rows, key, "executed_start_s", "executed_end_s")
    chk["passed"] = (chk["start_order_matches_plan"] and chk["max_abs_duration_error_s"] <= tol
                     and chk["min_start_lag_s"] >= -1e-9 and chk["executed_overlaps_operator"] == 0
                     and chk["executed_overlaps_robot"] == 0)
    return rows, chk


def latency_test(sim, n, label):
    lat = []
    timeouts = 0
    mismatches = 0
    for i in range(n):
        cid = "cmd_%s_%05d" % (label, i)
        a = time.perf_counter()
        sim.setStringSignal("cmd_id", cid)
        ack = sim.getStringSignal("cmd_id")
        ms = (time.perf_counter() - a) * 1000.0
        if isinstance(ack, bytes):
            ack = ack.decode()
        if ms > TIMEOUT_S * 1000.0:
            timeouts += 1
        elif ack != cid:
            mismatches += 1
        else:
            lat.append(ms)
    s = sorted(lat)
    d = {"sent": n, "valid_n": len(s), "timeouts": timeouts, "mismatches": mismatches}
    if s:
        d.update(median_ms=st.median(s), p95_ms=s[math.ceil(0.95 * len(s)) - 1], max_ms=s[-1])
    return d


def main():
    jobs = load_jobs()
    span = max(j["p_end"] for j in jobs)
    print("Jobs (task, operator, robot, start, end):",
          [(j["task_id"], j["operator"], j["robot"], round(j["p_start"], 2), round(j["p_end"], 2)) for j in jobs])
    if span > MAX_SPAN_S:
        raise SystemExit("Planned span %.1f s exceeds MAX_SPAN_S; reduce N_JOBS." % span)
    client = RemoteAPIClient()
    sim = client.require("sim")
    sim.loadScene(str(SCENE))
    dt = sim.getSimulationTimeStep()
    meta = {"replay_check": REPLAY, "coppeliasim_full_version": sim.getInt32Param(sim.intparam_program_full_version),
            "client_package": metadata.version("coppeliasim-zmqremoteapi-client"),
            "python": platform.python_version(), "arm": ARM, "scenario_seed": SCENARIO_SEED,
            "search_seed": SEARCH_SEED, "n_jobs": len(jobs), "planned_span_s": span,
            "time_step_s": dt, "latency_n": LATENCY_N, "timeout_s": TIMEOUT_S,
            "scene_sha256": hashlib.sha256(SCENE.read_bytes()).hexdigest(),
            "timestamp": datetime.now().isoformat(timespec="seconds")}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    summary = {"meta": meta}
    for mode, stepping, tol in (("stepping", True, dt + 1e-9), ("non_stepping_realtime", False, 0.1)):
        rec, wall, sim_el = run_sequence(sim, jobs, stepping)
        rows, chk = evaluate(jobs, rec, tol)
        chk["wall_s"] = wall
        chk["sim_s"] = sim_el
        for r in rows:
            r["mode"] = mode
        all_rows += rows
        sim.loadScene(str(SCENE))
        start(sim, stepping)
        lat = latency_test(sim, LATENCY_N, mode)
        stop(sim)
        summary[mode] = {"sequence": chk, "latency": lat}
    with (OUT_DIR / "events.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Saved to", OUT_DIR)


if __name__ == "__main__":
    main()