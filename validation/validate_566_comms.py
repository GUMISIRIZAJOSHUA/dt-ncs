import json, math, statistics as st, sys, time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_protocol_566 import SCENE, PROJECT_ROOT, start, stop
from validate_566_execution import txt, parse
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

TIMEOUT_S = 1.0
WARMUP = 20
MEASURED = 200
LEAD_S = 2.0
HOLD_S = 1.5
DUR_S = 5.0
OUT_DIR = PROJECT_ROOT / "results" / ("protocol_566_comms_" + datetime.now().strftime("%Y%m%d_%H%M%S"))

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
        local ok, a, b = pcall(function()
            return sim.getObjectPosition(sim.getObject('/' .. f[6]), -1), sim.getObjectPosition(sim.getObject('/' .. f[7]), -1)
        end)
        local dur = tonumber(f[5])
        if (not ok) or (not dur) or dur <= 0 or #f < 7 then
            log = log .. (f[1] or '?') .. '|reject|' .. string.format('%.6f', t) .. '|' .. (f[2] or '?') .. '|' .. (f[3] or '?') .. '\\n'
            sim.setStringSignal('events_out', log)
            sim.setStringSignal('ack_out', 'REJECT|' .. (f[1] or '?'))
        else
            local j = {id = f[1], op = f[2], rb = f[3], st = tonumber(f[4]), dur = dur, state = 0, a = a, b = b}
            j.tok = sim.createDummy(0.08)
            sim.setObjectPosition(j.tok, -1, j.a)
            jobs[#jobs + 1] = j
            emit(j, 'ack', t)
            sim.setStringSignal('ack_out', j.id)
        end
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


def payload(aid, op, rb, st_abs, dur, ms="Task_A_Start", me="Task_A_End"):
    return "|".join([aid, str(op), str(rb), "%.6f" % st_abs, "%.6f" % dur, ms, me])


def prep(sim):
    sim.loadScene(str(SCENE))
    sim.createScript(sim.scripttype_simulation, LUA, 0, "lua")
    start(sim, False)


def summarize(lat):
    s = sorted(lat)
    d = {"valid_n": len(s)}
    if s:
        d.update(median_ms=st.median(s), p95_ms=s[math.ceil(0.95 * len(s)) - 1], max_ms=s[-1])
    return d


def latency_condition(sim):
    prep(sim)
    lat = []
    timeouts = 0
    unmatched = 0
    try:
        far = sim.getSimulationTime() + 3600.0
        for i in range(WARMUP + MEASURED):
            aid = "L-%04d" % i
            msg = payload(aid, 1, 1, far, DUR_S)
            sim.setStringSignal("ack_out", "")
            t0 = time.perf_counter()
            sim.setStringSignal("assign_in", msg)
            got = None
            seen_other = False
            while time.perf_counter() - t0 < TIMEOUT_S:
                val = txt(sim.getStringSignal("ack_out"))
                if val == aid:
                    got = (time.perf_counter() - t0) * 1000.0
                    break
                if val != "":
                    seen_other = True
            if i < WARMUP:
                continue
            if got is None:
                timeouts += 1
            else:
                lat.append(got)
            if seen_other:
                unmatched += 1
    finally:
        stop(sim)
    out = {"warmup_discarded": WARMUP, "attempted": MEASURED, "timeouts": timeouts, "unmatched_acks": unmatched,
           "timeout_rate": timeouts / MEASURED, "timeout_s": TIMEOUT_S}
    out.update(summarize(lat))
    return out


def exchange(sim, aid, msg, send=True, hold_s=0.0):
    sim.setStringSignal("ack_out", "")
    t0 = time.perf_counter()
    if send:
        sim.setStringSignal("assign_in", msg)
    if hold_s:
        time.sleep(hold_s)
    while time.perf_counter() - t0 < TIMEOUT_S:
        val = txt(sim.getStringSignal("ack_out"))
        if val == aid:
            return "ack"
        if val == "REJECT|" + aid:
            return "reject"
    return "timeout"


def occupancy_conflict(ev, aid):
    starts = [e for e in ev if e["id"] == aid and e["event"] == "start"]
    rels = [e for e in ev if e["id"] == aid and e["event"] == "release"]
    iv = list(zip(starts, rels))
    for i in range(len(iv)):
        for k in range(i + 1, len(iv)):
            same = iv[i][0]["op"] == iv[k][0]["op"] or iv[i][0]["rb"] == iv[k][0]["rb"]
            if same and min(iv[i][1]["t"], iv[k][1]["t"]) - max(iv[i][0]["t"], iv[k][0]["t"]) > 1e-9:
                return True
    return False


def failure_case(sim, name, aid, drop_first, hold_first, marker_start):
    prep(sim)
    attempts = []
    late_ack = False
    try:
        base = sim.getSimulationTime() + LEAD_S
        msg = payload(aid, 1, 1, base, DUR_S, ms=marker_start)
        attempts.append(exchange(sim, aid, msg, send=not drop_first, hold_s=hold_first))
        if attempts[0] != "ack":
            late_ack = txt(sim.getStringSignal("ack_out")) == aid
            attempts.append(exchange(sim, aid, msg))
        while sim.getSimulationTime() < base + DUR_S + 1.0:
            time.sleep(0.01)
        raw = sim.getStringSignal("events_out")
    finally:
        stop(sim)
    ev = parse(raw)
    mine = [e["event"] for e in ev if e["id"] == aid]
    cnt = {k: mine.count(k) for k in ("ack", "start", "complete", "release", "reject")}
    return {"case": name, "attempt_outcomes": attempts, "late_ack_after_timeout": late_ack, "event_counts": cnt,
            "duplicate_execution": cnt["start"] > 1, "lost_completion": cnt["start"] > cnt["complete"],
            "inconsistent_occupancy": occupancy_conflict(ev, aid), "executions": cnt["start"]}


def main():
    client = RemoteAPIClient()
    sim = client.require("sim")
    sim.loadScene(str(SCENE))
    meta = {"coppeliasim_full_version": sim.getInt32Param(sim.intparam_program_full_version),
            "time_step_s": sim.getSimulationTimeStep(), "mode": "setStepping(False), realtime on",
            "topology": "single machine; localhost ZeroMQ remote API", "timeout_s": TIMEOUT_S,
            "warmup": WARMUP, "measured": MEASURED, "hold_s": HOLD_S,
            "timestamp": datetime.now().isoformat(timespec="seconds")}
    print("Running latency condition", flush=True)
    summary = {"meta": meta, "latency": latency_condition(sim), "failures": []}
    for name, aid, drop, hold, marker in (("delayed_ack", "F1-01", False, HOLD_S, "Task_A_Start"),
                                          ("missing_command", "F2-01", True, 0.0, "Task_A_Start"),
                                          ("rejected_invalid_marker", "F3-01", False, 0.0, "No_Such_Marker")):
        print("Running failure case", name, flush=True)
        summary["failures"].append(failure_case(sim, name, aid, drop, hold, marker))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Saved to", OUT_DIR)


if __name__ == "__main__":
    main()