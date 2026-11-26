from pathlib import Path
import pandas as pd, numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNS = {
    0.00075: "stage_a_full_20261125_035846_490619",
    0.00100: "stage_a_full_20261125_145934_824098",
    0.00125: "stage_a_full_20261126_021248_243744",
}
ARMS = ["B1", "B2", "B3a", "B3b", "B3"]
COMPARATORS = ["B1", "B2", "B3a", "B3b"]
METRICS = ["final_fatigue", "throughput_tasks_per_hour", "completed_tasks",
           "final_ergonomic_risk", "safety_violations", "energy_per_task_kj",
           "defect_rate", "well_being_score", "overall_score"]
PLOT = {"final_fatigue": "Endpoint fatigue",
        "throughput_tasks_per_hour": "Throughput (tasks/h)"}

out = Path("results/sensitivity_analysis"); out.mkdir(parents=True, exist_ok=True)

frames = []
for a, name in RUNS.items():
    d = pd.read_csv(Path("results") / name / "shift_metrics.csv")
    d["alpha_per_s"] = a
    frames.append(d)
df = pd.concat(frames, ignore_index=True)
assert len(df) == 450 and not df.duplicated(["alpha_per_s", "arm", "scenario_id"]).any()

def ci95(x):
    x = np.asarray(x, float); n = len(x)
    m = x.mean()
    if n < 2: return m, np.nan, np.nan, np.nan
    sd = x.std(ddof=1); h = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
    return m, sd, m - h, m + h

# Table 1: configuration and sample size
t1 = (df.groupby(["alpha_per_s", "arm"]).agg(
        n_scenarios=("scenario_id", "nunique"), n_rows=("scenario_id", "size"))
      .reset_index())
t1["run_directory"] = t1.alpha_per_s.map(RUNS)
t1.to_csv(out / "table_config_sample_size.csv", index=False)

# Table 2: outcome summary
rows = []
for (a, arm), g in df.groupby(["alpha_per_s", "arm"]):
    for m in METRICS:
        mean, sd, lo, hi = ci95(g[m])
        rows.append(dict(alpha_per_s=a, arm=arm, metric=m, n=len(g),
                         mean=mean, sd=sd, ci95_low=lo, ci95_high=hi))
t2 = pd.DataFrame(rows)
t2.to_csv(out / "table_outcome_summary_long.csv", index=False)
wide = t2.assign(txt=t2.apply(lambda r: f"{r['mean']:.3f} [{r.ci95_low:.3f}, {r.ci95_high:.3f}]", axis=1)) \
         .pivot_table(index=["metric", "arm"], columns="alpha_per_s", values="txt", aggfunc="first")
wide.to_csv(out / "table_outcome_summary_wide.csv")

# Table 3: paired B3 minus comparator by scenario
rows = []
for a in RUNS:
    p = df[df.alpha_per_s == a]
    for m in METRICS:
        w = p.pivot(index="scenario_id", columns="arm", values=m)
        for c in COMPARATORS:
            diff = (w["B3"] - w[c]).dropna()
            mean, sd, lo, hi = ci95(diff)
            rows.append(dict(alpha_per_s=a, metric=m, comparison=f"B3-{c}", n_pairs=len(diff),
                             mean_diff=mean, sd_diff=sd, ci95_low=lo, ci95_high=hi,
                             n_nonzero=int((diff.abs() > 1e-12).sum())))
t3 = pd.DataFrame(rows)
t3.to_csv(out / "table_paired_differences.csv", index=False)

# Figures: sensitivity by arm
for m, label in PLOT.items():
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for arm in ARMS:
        s = t2[(t2.arm == arm) & (t2.metric == m)].sort_values("alpha_per_s")
        ax.errorbar(s.alpha_per_s, s["mean"],
                    yerr=[s["mean"] - s.ci95_low, s.ci95_high - s["mean"]],
                    marker="o", capsize=3, label=arm)
    ax.set_xticks(list(RUNS)); ax.set_xlabel("Fatigue accumulation rate α (1/s)")
    ax.set_ylabel(label); ax.set_title(f"{label} vs accumulation rate (mean, 95% CI, n=30)")
    ax.legend(); ax.grid(alpha=.3); fig.tight_layout()
    fig.savefig(out / f"fig_sensitivity_{m}.png", dpi=200); plt.close(fig)

# Figures: paired differences
for m, label in PLOT.items():
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
    for ax, a in zip(axes, RUNS):
        s = t3[(t3.alpha_per_s == a) & (t3.metric == m)].set_index("comparison").loc[[f"B3-{c}" for c in COMPARATORS]]
        ax.errorbar(range(len(s)), s.mean_diff,
                    yerr=[s.mean_diff - s.ci95_low, s.ci95_high - s.mean_diff],
                    fmt="o", capsize=4)
        ax.axhline(0, color="k", lw=.8)
        ax.set_xticks(range(len(s))); ax.set_xticklabels(s.index, rotation=30)
        ax.set_title(f"α = {a}"); ax.grid(alpha=.3)
    axes[0].set_ylabel(f"Paired difference in {label.lower()}")
    fig.suptitle(f"B3 minus comparator, scenario-paired (mean, 95% CI, n=30)")
    fig.tight_layout(); fig.savefig(out / f"fig_paired_{m}.png", dpi=200); plt.close(fig)

print(t1.to_string(index=False))
print(wide.loc[["final_fatigue", "throughput_tasks_per_hour"]].to_string())
print(t3[t3.metric.isin(PLOT)].round(4).to_string(index=False))
print("Saved to", out.resolve())