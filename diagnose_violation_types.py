import sys, runpy
from collections import Counter, defaultdict
import src.scheduler as S
from src.safety import calculate_collision_risk

for name in ("assess_projected_work", "select_assignment", "run_shift"):
    assert hasattr(S, name), name

orig_assess, orig_select, orig_run = S.assess_projected_work, S.select_assignment, S.run_shift
tags = {}
stats = defaultdict(lambda: {"selected": 0, "flagged": 0, "same_id": 0,
                             "type": Counter(), "combo": Counter()})

def assess(operator, task, duration_s, config, collision_risk, safe_zone_risk, adapter):
    r = orig_assess(operator, task, duration_s, config, collision_risk, safe_zone_risk, adapter)
    key = (operator.operator_id, task.task_id, round(float(duration_s), 6), float(collision_risk))
    tags[key] = [v.violation_type for v in r.violations]
    return r

def select(*a, **k):
    tags.clear()
    result = orig_select(*a, **k)
    arm = a[0] if a else k["arm"]
    asg = result[0]
    st = stats[arm]
    st["selected"] += 1
    if asg.operator_id == asg.robot_id:
        st["same_id"] += 1
    if asg.safety_violation:
        st["flagged"] += 1
        key = (asg.operator_id, asg.task_id, round(float(asg.duration_s), 6),
               float(calculate_collision_risk(asg.operator_id, asg.robot_id)))
        types = tags.get(key, ["unknown"])
        st["combo"]["+".join(sorted(types))] += 1
        for t in types:
            st["type"][t] += 1
    return result

def run(*a, **k):
    arm = a[0] if a else k["arm"]
    r = orig_run(*a, **k)
    ok = stats[arm]["flagged"] == r.safety_violations
    print(f"CHECK {arm}: saved safety_violations={r.safety_violations}, "
          f"tallied={stats[arm]['flagged']}, match={ok}", flush=True)
    return r

S.assess_projected_work, S.select_assignment, S.run_shift = assess, select, run
sys.argv = ["run_experiment.py", "--mode", "pilot",
            "--fatigue-parameters", r"configs\fatigue_synthetic_benchmark.yaml"]
runpy.run_path("run_experiment.py", run_name="__main__")

print("\nVIOLATION TYPES FOR SELECTED ASSIGNMENTS (scenario 1, baseline alpha)")
for arm in ["B1", "B2", "B3a", "B3b", "B3"]:
    st = stats[arm]
    print(f"{arm}: selected={st['selected']}, flagged={st['flagged']}, "
          f"same-ID pairings={st['same_id']}")
    print("   by type:", dict(st["type"]))
    print("   by combination:", dict(st["combo"]))