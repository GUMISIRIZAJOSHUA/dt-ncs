import csv, hashlib, json, os, platform, sys, time
from datetime import datetime
from importlib import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_protocol_566 import load_jobs, REPLAY, SCENE, PROJECT_ROOT, start, stop
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

LEAD_S = 2.0
ACK_TIMEOUT_S = 5.0
ORDER = ["ack", "start", "complete", "release"]
MARK = [("Task_A_Start", "Task_A_End"), ("Task_B_Start", "Task_B_End")]
OUT_DIR = PROJECT_ROOT / "results" / ("protocol_566_exec_" + datetime.now().strftime("%Y%m%d_%H%M%S"))

LUA = """
sim = require('sim')

function sysCall_init()
    jobs = {}
    log = ''
    sim.setStringSignal('events_out', '')
    sim.setStringSignal('assign_in', '')
    sim.setStringSignal('ack_out', '')
end

function emit(j, ev, t)
    log = log .. j.id .. '|' .. ev .. '|' .. string.format('%.6f', t) .. '|' .. j.op .. '|' .. j.rb .. '\\n'
    sim.setStringSignal('events_out', log)
end

function sysCall_actuation()
    local t = sim.getSimulationTime()
    local msg = sim.getStringSignal('assign_in')
    if msg and msg ~= '' then
        local f = {}
        for x in string.gmatch(msg, '[^|]+') do f[#f + 1] = x end
        local j = {id = f[1], op = f[2], rb = f[3], st = tonumber(f[4]), dur = tonumber(f[5]), state = 0}
        j.a = sim.getObjectPosition(sim.getObject('/' .. f[6]), -1)
        j.b = sim.getObjectPosition(sim.getObject('/' .. f[7]), -1)
        j.tok = sim.createDummy(0.08)
        sim.setObjectPosition(j.tok, -1, j.a)
        jobs[#jobs + 1] = j
        emit(j, 'ack', t)
        sim.setStringSignal('ack_out', j.id)
        sim.setStringSignal('assign_in', '')
    end
    for _, j in ipairs(jobs) do
        if j.state == 0 and t >= j.st - 1e-9 then
            j.state = 1
            emit(j, 'start', t)
        end
        if j.state == 1 then
            local fr = math.min(1.0, (t - j.st) / j.dur)
            sim.setObjectPosition(j.tok, -1, {j.a[1] + fr * (j.b[1] - j.a[1]), j.a[2] + fr * (j.b[2] - j.a[2]), j.a[3] + fr * (j.b[3] - j.a[3])})
            if t >= j.st + j.dur - 1e-9 then
                j.state = 2
                emit(j, 'complete', t)
                emit(j, 'release', t)
            end
        end
    end
end
"""


def txt(x):
    if x is None:
        return ""
    return x.decode() if isinstance(x, bytes) else str(x)


def mk(aid, op, rb, st, dur, k):
    return {"aid": aid, "op": int(op), "rb": int(rb), "start": st, "dur": dur, "ms": MARK[k % 2][0], "me": MARK[k % 2][1]}


def build_sequences():
    t0 = time.perf_counter()
    jobs = load_jobs()
    replay_wall_s = time.perf_counter() - t0
    s2 = [mk("B3-1001-t%s-%02d" % (j["task_id"], j["idx"]), j["operator"], j["robot"], j["p_start"], j["p_end"] - j["p_start"], j["idx"]) for j in jobs]
    seqs = [
        ("S1_single", False, [mk("S1-01", 1, 1, 0.0, 10.0, 0)]),
        ("S2_sequential_B3", False, s2),
        ("S3_concurrent_disjoint", False, [mk("S3-01", 1, 1, 0.0, 10.0, 0), mk("S3-02", 2, 2, 2.0, 10.0, 1)]),
        ("S4_conflict_control", True, [mk("S4-01", 1, 1, 0.0, 10.0, 0), mk("S4-02", 1, 2, 4.0, 10.0, 1)]),
    ]
    return seqs, replay_wall_s


def send(sim, it, st_abs, stepping):
    msg = "|".join([it["aid"], str(it["op"]), str(it["rb"]), "%.6f" % st_abs, "%.6f" % it["dur"], it["ms"], it["me"]])
    sim.setStringSignal("assign_in", msg)
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < ACK_TIMEOUT_S:
        if stepping:
            sim.step()
        else:
            time.sleep(0.002)
        if txt(sim.getStringSignal("ack_out")) == it["aid"]:
            return (time.perf_counter() - t0) * 1000.0
    raise RuntimeError("no ack for " + it["aid"] + "; check the CoppeliaSim console for script errors")


def run_case(sim, items, stepping):
    sim.loadScene(str(SCENE))
    sim.createScript(sim.scripttype_simulation, LUA, 0, "lua")
    start(sim, stepping)
    wall0 = time.perf_counter()
    disp = []
    try:
        base = sim.getSimulationTime() + LEAD_S
        end_max = max(it["start"] + it["dur"] for it in items)
        for it in items:
            st_abs = base + it["start"]
            ts = sim.getSimulationTime()
            ack_ms = send(sim, it, st_abs, stepping)
            disp.append({"aid": it["aid"], "st_abs": st_abs, "dispatch_sim_t": ts, "ack_wall_ms": ack_ms})
        target = base + end_max + 1.0
        while sim.getSimulationTime() < target:
            if stepping:
                sim.step()
            else:
                time.sleep(0.01)
            if time.perf_counter() - wall0 > 120 + 2 * end_max:
                raise RuntimeError("case timed out")
        raw = sim.getStringSignal("events_out")
    finally:
        stop(sim)
    return disp, raw


def parse(raw):
    ev = []
    for line in txt(raw).splitlines():
        p = line.split("|")
        if len(p) == 5:
            ev.append({"id": p[0], "event": p[1], "t": float(p[2]), "op": p[3], "rb": p[4]})
    return ev


def overlap_count(rows, key):
    n = 0
    for i in range(len(rows)):
        for k in range(i + 1, len(rows)):
            if rows[i][key] == rows[k][key] and min(rows[i]["release_t"], rows[k]["release_t"]) - max(rows[i]["start_t"], rows[k]["start_t"]) > 1e-9:
                n += 1
    return n


def evaluate(mode, seq, items, disp, ev, dt, expect_conflict):
    ids = [it["aid"] for it in items]
    unknown = sorted({e["id"] for e in ev} - set(ids))
    rows = []
    events_ok = True
    dur_ok = True
    lag_ok = True
    for it, d in zip(items, disp):
        seqev = [e for e in ev if e["id"] == it["aid"]]
        good = [e["event"] for e in seqev] == ORDER and all(seqev[k]["t"] <= seqev[k + 1]["t"] + 1e-9 for k in range(3))
        events_ok = events_ok and good
        t = {e["event"]: e["t"] for e in seqev}
        row = {"mode": mode, "sequence": seq, "assignment_id": it["aid"], "operator": it["op"], "robot": it["rb"],
               "planned_start_abs_s": d["st_abs"], "planned_duration_s": it["dur"], "events_in_order_once": good,
               "dispatch_sim_t": d["dispatch_sim_t"], "ack_wall_ms": d["ack_wall_ms"]}
        if good:
            row.update(ack_t=t["ack"], start_t=t["start"], complete_t=t["complete"], release_t=t["release"],
                       executed_duration_s=t["complete"] - t["start"], duration_error_s=t["complete"] - t["start"] - it["dur"],
                       start_lag_s=t["start"] - d["st_abs"])
            dur_ok = dur_ok and abs(row["duration_error_s"]) <= dt + 1e-9
            lag_ok = lag_ok and -1e-9 <= row["start_lag_s"] <= dt + 1e-9
        rows.append(row)
    good_rows = [r for r in rows if r["events_in_order_once"]]
    op_c = overlap_count(good_rows, "operator")
    rb_c = overlap_count(good_rows, "robot")
    detected = (op_c + rb_c) > 0
    chk = {"assignments": len(items), "events_once_in_order": events_ok, "unknown_ids": unknown,
           "durations_within_one_step": dur_ok, "start_lag_within_one_step": lag_ok,
           "executed_overlaps_operator": op_c, "executed_overlaps_robot": rb_c,
           "conflict_expected": expect_conflict, "conflict_detected": detected}
    chk["passed"] = events_ok and not unknown and dur_ok and lag_ok and (detected == expect_conflict)
    return rows, chk


def main():
    seqs, replay_wall_s = build_sequences()
    client = RemoteAPIClient()
    sim = client.require("sim")
    sim.loadScene(str(SCENE))
    dt = sim.getSimulationTimeStep()
    meta = {"coppeliasim_full_version": sim.getInt32Param(sim.intparam_program_full_version),
            "client_package": metadata.version("coppeliasim-zmqremoteapi-client"),
            "python": platform.python_version(), "os": platform.platform(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "topology": "single machine; Python client and CoppeliaSim on localhost via ZeroMQ remote API",
            "time_step_s": dt, "lead_s": LEAD_S, "ack_timeout_s": ACK_TIMEOUT_S,
            "stepping_mode": "setStepping(True), realtime off", "non_stepping_mode": "setStepping(False), realtime on",
            "scene_sha256": hashlib.sha256(SCENE.read_bytes()).hexdigest(), "replay_check": REPLAY,
            "scheduler_replay_wall_s_including_scenario_build": replay_wall_s,
            "timestamp": datetime.now().isoformat(timespec="seconds")}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    summary = {"meta": meta, "cases": []}
    for mode, stepping in (("stepping", True), ("non_stepping_realtime", False)):
        for seq, expect_conflict, items in seqs:
            print("Running", mode, seq, flush=True)
            disp, raw = run_case(sim, items, stepping)
            rows, chk = evaluate(mode, seq, items, disp, parse(raw), dt, expect_conflict)
            all_rows += rows
            summary["cases"].append({"mode": mode, "sequence": seq, **chk})
    with (OUT_DIR / "assignments.csv").open("w", encoding="utf-8", newline="") as f:
        names = sorted({k for r in all_rows for k in r})
        w = csv.DictWriter(f, fieldnames=names)
        w.writeheader()
        w.writerows(all_rows)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Saved to", OUT_DIR)


if __name__ == "__main__":
    main()