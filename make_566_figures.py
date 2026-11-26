import csv, json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

R = Path("results")
EXEC = R / "protocol_566_exec_20261126_160131"
COMMS = R / "protocol_566_comms_20261126_161129"
OUT = R / "protocol_566_figures"
OUT.mkdir(exist_ok=True)

summary = json.loads((EXEC / "summary.json").read_text(encoding="utf-8"))
comms = json.loads((COMMS / "summary.json").read_text(encoding="utf-8"))
rows = list(csv.DictReader((EXEC / "assignments.csv").open(encoding="utf-8")))

t65 = []
for c in summary["cases"]:
    sub = [r for r in rows if r["mode"] == c["mode"] and r["sequence"] == c["sequence"]]
    t65.append({"mode": c["mode"], "sequence": c["sequence"], "assignments": c["assignments"],
                "events_once_in_order": c["events_once_in_order"],
                "max_abs_duration_error_s": round(max(abs(float(r["duration_error_s"])) for r in sub), 4),
                "max_start_lag_s": round(max(float(r["start_lag_s"]) for r in sub), 4),
                "executed_overlaps_operator": c["executed_overlaps_operator"],
                "executed_overlaps_robot": c["executed_overlaps_robot"],
                "conflict_expected": c["conflict_expected"], "conflict_detected": c["conflict_detected"],
                "passed": c["passed"]})
with (OUT / "table_6_5_execution.csv").open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(t65[0].keys()))
    w.writeheader()
    w.writerows(t65)

lat = comms["latency"]
with (OUT / "table_6_6a_latency.csv").open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["attempted", "valid_n", "median_ms", "p95_ms", "max_ms", "timeouts", "unmatched_acks", "warmup", "timeout_s"])
    w.writerow([lat["attempted"], lat["valid_n"], round(lat["median_ms"], 1), round(lat["p95_ms"], 1), round(lat["max_ms"], 1),
                lat["timeouts"], lat["unmatched_acks"], lat["warmup_discarded"], lat["timeout_s"]])

with (OUT / "table_6_6b_failures.csv").open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["case", "attempt_outcomes", "late_ack_after_timeout", "executions", "duplicate_execution", "lost_completion", "inconsistent_occupancy"])
    for c in comms["failures"]:
        w.writerow([c["case"], " then ".join(c["attempt_outcomes"]), c["late_ack_after_timeout"], c["executions"],
                    c["duplicate_execution"], c["lost_completion"], c["inconsistent_occupancy"]])

seqs = ["S2_sequential_B3", "S3_concurrent_disjoint", "S4_conflict_control"]
titles = {"S2_sequential_B3": "Sequential (five B3 jobs)", "S3_concurrent_disjoint": "Concurrent, disjoint resources",
          "S4_conflict_control": "Shared-operator conflict (negative control)"}
colors = {"1": "tab:blue", "2": "tab:orange"}
fig, axes = plt.subplots(3, 1, figsize=(7.5, 6.5), gridspec_kw={"height_ratios": [5, 2, 2]})
for ax, s in zip(axes, seqs):
    sub = sorted([r for r in rows if r["mode"] == "stepping" and r["sequence"] == s], key=lambda r: float(r["start_t"]))
    t0 = float(sub[0]["start_t"])
    for y, r in enumerate(sub):
        a, b, k = float(r["start_t"]) - t0, float(r["release_t"]) - t0, float(r["ack_t"]) - t0
        ax.barh(y, b - a, left=a, color=colors[r["operator"]], edgecolor="black", height=0.6)
        ax.plot(k, y, marker="v", color="black", markersize=5)
        ax.text(a + (b - a) / 2, y, "robot " + r["robot"], ha="center", va="center", fontsize=7)
    ax.set_yticks(range(len(sub)))
    ax.set_yticklabels([r["assignment_id"] for r in sub], fontsize=7)
    ax.invert_yaxis()
    ax.set_title(titles[s], fontsize=9)
    ax.set_xlabel("Simulation time since first start (s)", fontsize=8)
fig.legend(handles=[Patch(color="tab:blue", label="Operator 1"), Patch(color="tab:orange", label="Operator 2")], loc="upper right", fontsize=8)
fig.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig(OUT / "figure_6_4_event_timelines.png", dpi=300)
print("Wrote:", sorted(p.name for p in OUT.iterdir()))