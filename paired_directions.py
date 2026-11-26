import sys
from pathlib import Path
import pandas as pd

if len(sys.argv) < 3:
    sys.exit("usage: py paired_directions.py LOW_DIR BASE_DIR HIGH_DIR")

labels = ["LOW", "BASE", "HIGH"][: len(sys.argv) - 1]
metrics = ["completed_tasks", "throughput_tasks_per_hour", "total_energy_kj",
           "final_fatigue", "final_ergonomic_risk", "well_being_score",
           "overall_score"]
focal = "B3"
others = ["B1", "B2", "B3a", "B3b"]

def load(folder):
    for p in sorted(Path(folder).rglob("*.csv")):
        try:
            d = pd.read_csv(p)
        except Exception:
            continue
        if {"arm", "scenario_id"} <= set(d.columns) and len(d) == 150:
            print("using", p)
            return d
    sys.exit("no 150-row results csv in " + folder)

out = []
for label, folder in zip(labels, sys.argv[1:]):
    d = load(folder)
    for m in metrics:
        w = d.pivot(index="scenario_id", columns="arm", values=m)
        for o in others:
            diff = (w[focal] - w[o]).dropna()
            out.append(dict(batch=label, metric=m, comparator=o, n=len(diff),
                            focal_higher=int((diff > 1e-9).sum()),
                            focal_lower=int((diff < -1e-9).sum()),
                            tied=int((diff.abs() <= 1e-9).sum()),
                            median_diff=diff.median(),
                            mean_diff=diff.mean()))

res = pd.DataFrame(out)
Path("output").mkdir(exist_ok=True)
res.to_csv("output/paired_directions.csv", index=False)
pd.set_option("display.width", 200, "display.max_rows", 500)
print(res.round(4).to_string(index=False))