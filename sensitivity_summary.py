import numpy as np
import pandas as pd

RUNS = {
    "LOW 0.00075": r"results\stage_a_full_20261125_035846_490619",
    "BASE 0.001": r"results\stage_a_full_20261125_145934_824098",
    "HIGH 0.00125": r"results\stage_a_full_20261126_021248_243744",
}
METRICS = ["final_fatigue", "throughput_tasks_per_hour", "completed_tasks",
           "safety_violations", "veto_events"]
ARMS = ["B1", "B2", "B3a", "B3b", "B3"]

pd.set_option("display.width", 200)
data = {k: pd.read_csv(v + r"\shift_metrics.csv") for k, v in RUNS.items()}

for name, m in data.items():
    print(f"\n=== {name}: mean per arm ===")
    print(m.groupby("arm")[METRICS].mean().reindex(ARMS).round(4).to_string())

def paired(m, a, b, col):
    x = m[m.arm == a].set_index("scenario_id")[col]
    y = m[m.arm == b].set_index("scenario_id")[col]
    d = (x - y.reindex(x.index)).dropna()
    se = d.std(ddof=1) / np.sqrt(len(d))
    return d.mean(), d.mean() - 1.96 * se, d.mean() + 1.96 * se, len(d)

print("\n=== Paired differences (normal-approx 95% CI) ===")
for name, m in data.items():
    for a, b in [("B3", "B2"), ("B3a", "B2"), ("B3", "B3b")]:
        for col in ["final_fatigue", "throughput_tasks_per_hour"]:
            mean, lo, hi, n = paired(m, a, b, col)
            print(f"{name:13s} {a}-{b} {col:27s} {mean:+.4f} [{lo:+.4f}, {hi:+.4f}] n={n}")