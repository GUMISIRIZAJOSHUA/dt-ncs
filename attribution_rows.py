from pathlib import Path
import pandas as pd

R = Path("results")
files = {
    "LOW": Path("output/paired_comparisons_holm_120_LOW.csv"),
    "BASE": R / "stage_a_full_20261124_091315_391055" / "paired_comparisons_holm_120.csv",
    "HIGH": Path("output/paired_comparisons_holm_120_HIGH.csv"),
}
pairs = {("B2", "B3a"), ("B2", "B3b"), ("B2", "B3"), ("B3a", "B3b")}
metrics = ["final_fatigue", "throughput_tasks_per_hour", "overall_score"]
cols = ["metric", "arm_a", "arm_b", "mean_difference", "ci_lower", "ci_upper", "holm_p_value"]
parts = []
for label, p in files.items():
    d = pd.read_csv(p)
    d = d[d.metric.isin(metrics) & d.apply(lambda r: (r.arm_a, r.arm_b) in pairs, axis=1)][cols].copy()
    d.insert(0, "batch", label)
    parts.append(d)
pd.set_option("display.width", 200)
print(pd.concat(parts).round(4).to_string(index=False))
