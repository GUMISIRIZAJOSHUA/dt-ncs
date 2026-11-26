import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNS = {
    0.00075: r"results\stage_a_full_20261125_035846_490619",
    0.001: r"results\stage_a_full_20261125_145934_824098",
    0.00125: r"results\stage_a_full_20261126_021248_243744",
}
ALPHAS = list(RUNS)
ARMS = ["B1", "B2", "B3a", "B3b", "B3"]
OUT = "figures_sensitivity"
os.makedirs(OUT, exist_ok=True)
data = {a: pd.read_csv(p + r"\shift_metrics.csv") for a, p in RUNS.items()}

def paired(m, a, b, col):
    x = m[m.arm == a].set_index("scenario_id")[col]
    y = m[m.arm == b].set_index("scenario_id")[col]
    d = (x - y.reindex(x.index)).dropna()
    se = d.std(ddof=1) / np.sqrt(len(d))
    return d.mean(), 1.96 * se

# Figure 1: endpoint fatigue by arm
fig, ax = plt.subplots(figsize=(6.5, 4.5))
for arm in ARMS:
    ys = [data[a][data[a].arm == arm]["final_fatigue"].mean() for a in ALPHAS]
    ax.plot(ALPHAS, ys, marker="o", label=arm)
ax.set_xticks(ALPHAS)
ax.set_xlabel("Fatigue accumulation rate (alpha, per s)")
ax.set_ylabel("Mean endpoint fatigue (0-1)")
ax.set_title("Endpoint fatigue by arm and accumulation rate")
ax.legend(ncol=3, fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig1_fatigue_by_arm.png"), dpi=200)
plt.close(fig)

# Figure 2: paired differences with 95% CI
contrasts = [("B3", "B2"), ("B3a", "B2"), ("B3", "B3b")]
metrics = [("final_fatigue", "Delta endpoint fatigue"),
           ("throughput_tasks_per_hour", "Delta throughput (tasks/h)")]
fig, axes = plt.subplots(2, 1, figsize=(7, 8), sharex=True)
width = 0.18
for ax, (col, label) in zip(axes, metrics):
    for i, (a, b) in enumerate(contrasts):
        xs, ms, es = [], [], []
        for j, al in enumerate(ALPHAS):
            mean, err = paired(data[al], a, b, col)
            xs.append(j + (i - 1) * width)
            ms.append(mean)
            es.append(err)
        ax.errorbar(xs, ms, yerr=es, fmt="o", capsize=3, label=f"{a} - {b}")
    ax.axhline(0, color="grey", lw=0.8)
    ax.set_ylabel(label)
    ax.legend(fontsize=8)
axes[1].set_xticks(range(len(ALPHAS)))
axes[1].set_xticklabels([str(a) for a in ALPHAS])
axes[1].set_xlabel("Fatigue accumulation rate (alpha, per s)")
axes[0].set_title("Paired differences over 30 scenarios (95% CI, normal approx.)")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig2_paired_differences.png"), dpi=200)
plt.close(fig)

# Figure 3: safety violations
fig, ax = plt.subplots(figsize=(6.5, 4.5))
x = np.arange(len(ALPHAS))
for k, arm in enumerate(["B1", "B2"]):
    ys = [data[a][data[a].arm == arm]["safety_violations"].mean() for a in ALPHAS]
    bars = ax.bar(x + (k - 0.5) * 0.35, ys, 0.35, label=arm)
    ax.bar_label(bars, fmt="%.0f", fontsize=8)
ax.set_xticks(x)
ax.set_xticklabels([str(a) for a in ALPHAS])
ax.set_xlabel("Fatigue accumulation rate (alpha, per s)")
ax.set_ylabel("Mean selected-assignment violations per shift")
ax.set_title("Safety violations (B3a, B3b, B3: 0 by construction)")
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig3_safety_violations.png"), dpi=200)
plt.close(fig)
print("saved to", OUT, os.listdir(OUT))