import hashlib
from pathlib import Path
import pandas as pd

R = Path("results")
ORIG = R / "stage_a_full_20261124_091315_391055"
BASE = R / "stage_a_full_20261125_145934_824098"
LOW = R / "stage_a_full_20261125_035846_490619"
HIGH = R / "stage_a_full_20261126_021248_243744"
KEY = ["metric", "arm_a", "arm_b"]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]

for name in ("shift_metrics.csv", "paired_comparisons.csv", "selected_seeds.csv"):
    print(name, "ORIG==BASE:", sha(ORIG / name) == sha(BASE / name))

def holm(p):
    m = len(p)
    order = sorted(range(m), key=lambda i: p[i])
    adj, run = [0.0] * m, 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * p[i]))
        adj[i] = run
    return adj

ref = pd.read_csv(ORIG / "paired_comparisons_holm_120.csv")
raw = pd.read_csv(ORIG / "paired_comparisons.csv")
print("\nraw rows:", len(raw), "| unique keys:", len(raw.drop_duplicates(KEY)))
print("ref rows:", len(ref), "| unique keys:", len(ref.drop_duplicates(KEY)))
print("metrics:", ref["metric"].nunique(), "| arms:", sorted(set(ref.arm_a) | set(ref.arm_b)))

chk = ref.copy()
chk["holm_recomputed"] = holm(chk["p_value"].tolist())
print("max |holm diff| on ORIG:", (chk["holm_recomputed"] - chk["holm_p_value"]).abs().max())

Path("output").mkdir(exist_ok=True)
for label, folder in (("LOW", LOW), ("HIGH", HIGH)):
    d = pd.read_csv(folder / "paired_comparisons.csv")
    m = ref[KEY].merge(d, on=KEY, how="left")
    print("\n" + label, "matched rows:", m["p_value"].notna().sum(), "of", len(ref))
    m["holm_p_value"] = holm(m["p_value"].fillna(1.0).tolist())
    m["holm_family_size"] = len(m)
    m.to_csv("output/paired_comparisons_holm_120_" + label + ".csv", index=False)
print("\nsaved output files")