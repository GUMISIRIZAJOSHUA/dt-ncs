import csv
import os
from collections import Counter

import numpy as np
import matplotlib.pyplot as plt

INPUT = "results/solver_comparison_outcomes_combined.csv"
OUTPUT = "results/figure3_safety_revised"

policies = ["B1", "B2", "B3a", "B3b", "B3", "CH", "RB"]
expected_seeds = set(range(101, 111))

colors = {
    "B1": "#D55E00",
    "B2": "#0072B2",
    "B3a": "#009E73",
    "B3b": "#E69F00",
    "B3": "#882E72",
    "CH": "#6B4C3B",
    "RB": "#777777",
}

with open(INPUT, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

assert len(rows) == 70, "Expected 70 rows."
assert {r["solver"] for r in rows} == set(policies)
assert {r["layout"] for r in rows} == {"2H2R"}

keys = [(r["solver"], int(r["seed"])) for r in rows]
assert all(n == 1 for n in Counter(keys).values()), (
    "Duplicate policy-seed records."
)

values = {}

for policy in policies:
    selected = [r for r in rows if r["solver"] == policy]

    assert len(selected) == 10, f"{policy}: expected 10 rows."
    assert {int(r["seed"]) for r in selected} == expected_seeds

    selected.sort(key=lambda r: int(r["seed"]))
    counts = np.array([
        float(r["safety_violations"]) for r in selected
    ])

    assert np.isfinite(counts).all()
    assert (counts >= 0).all()
    assert (counts == np.floor(counts)).all()

    values[policy] = counts

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "pdf.fonttype": 42,
})

fig, ax = plt.subplots(figsize=(9, 5.2))
x = np.arange(len(policies))
means = np.array([values[p].mean() for p in policies])

ax.bar(
    x,
    means,
    width=0.58,
    color=[colors[p] for p in policies],
    alpha=0.65,
    edgecolor="white",
    linewidth=0.8,
    zorder=2,
)

offsets = np.linspace(-0.18, 0.18, 10)
maximum = max(v.max() for v in values.values())
label_gap = max(maximum * 0.045, 1.0)

for position, policy in enumerate(policies):
    counts = values[policy]
    mean = counts.mean()

    ax.scatter(
        position + offsets,
        counts,
        s=30,
        facecolor=colors[policy],
        edgecolor="white",
        linewidth=0.5,
        zorder=4,
    )

    ax.hlines(
        mean,
        position - 0.29,
        position + 0.29,
        color=colors[policy],
        linewidth=2.2,
        zorder=5,
    )

    label_y = counts.max() + label_gap if mean > 0 else label_gap

    ax.text(
        position,
        label_y,
        f"{mean:,.1f}",
        ha="center",
        va="bottom",
        fontsize=10,
        fontweight="bold" if policy == "B3" else "normal",
    )

ax.set_xticks(x)
ax.set_xticklabels(policies)
ax.set_xlabel("Scheduling policy")
ax.set_ylabel("Executed violation count per run")
ax.set_ylim(-0.035 * maximum, maximum * 1.18)
ax.set_xlim(-0.6, len(policies) - 0.4)
ax.yaxis.grid(True, linestyle="--", alpha=0.25)
ax.set_axisbelow(True)
ax.axhline(0, color="#555555", linewidth=0.7, zorder=1)

fig.text(
    0.5,
    0.02,
    "Bars and horizontal marks: means; dots: 10 matched scenario seeds."
    "\nDots are horizontally offset for visibility; labels show means.",
    ha="center",
    va="bottom",
    fontsize=9,
)

fig.tight_layout(rect=(0, 0.12, 1, 1))
os.makedirs("results", exist_ok=True)

fig.savefig(OUTPUT + ".png", dpi=600, bbox_inches="tight")
fig.savefig(OUTPUT + ".pdf", bbox_inches="tight")
plt.close(fig)

print("Created PNG and PDF versions of Figure 3.")
print("Validated 10 unique matched seeds per policy.")

for policy in policies:
    counts = values[policy]
    print(
        f"{policy}: mean={counts.mean():.1f}, "
        f"runs_with_violations={np.count_nonzero(counts)}/10"
    )