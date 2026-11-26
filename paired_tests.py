import sys
from pathlib import Path
import pandas as pd
from scipy.stats import binomtest, wilcoxon

if len(sys.argv) < 3:
    sys.exit("usage: py paired_tests.py LOW_DIR BASE_DIR HIGH_DIR")

labels = ["LOW", "BASE", "HIGH"][: len(sys.argv) - 1]
metrics = ["completed_tasks", "total_energy_kj", "final_fatigue",
           "final_ergonomic_risk", "well_being_score", "overall_score"]
focal, others = "B3", ["B1", "B2", "B3a", "B3b"]
EPS = 1e-9

def holm(p):
    order = sorted(range(len(p)), key=lambda i: p[i])
    adj, running, m = [None] * len(p), 0.0, len(p)
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return adj

rows = []
for label, folder in zip(labels, sys.argv[1:]):
    d = pd.read_csv(Path(folder) / "shift_metrics.csv")
    for m in metrics:
        w = d.pivot(index="scenario_id", columns="arm", values=m)
        for o in others:
            diff = (w[focal] - w[o]).dropna()
            nz = diff[diff.abs() > EPS]
            pos, neg = int((nz > 0).sum()), int((nz < 0).sum())
            p_sign = binomtest(pos, pos + neg, 0.5).pvalue if pos + neg else float("nan")
            try:
                p_wil = wilcoxon(nz).pvalue if len(nz) else float("nan")
            except ValueError:
                p_wil = float("nan")
            rows.append(dict(batch=label, metric=m, comparator=o, n=len(diff),
                             nonzero=len(nz), higher=pos, lower=neg,
                             median_diff=diff.median(), p_sign=p_sign,
                             p_wilcoxon=p_wil))

res = pd.DataFrame(rows)
for col in ("p_sign", "p_wilcoxon"):
    res[col + "_holm"] = float("nan")
    for b, g in res.groupby("batch"):
        ok = g[col].notna()
        idx = g[ok].index
        res.loc[idx, col + "_holm"] = holm(g.loc[idx, col].tolist())

Path("output").mkdir(exist_ok=True)
res.to_csv("output/paired_tests.csv", index=False)
pd.set_option("display.width", 220, "display.max_rows", 500)
print(res.round(4).to_string(index=False))