import os
import csv
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.stats import t

INPUT = "results/solver_comparison_outcomes_combined.csv"
OUTPUT = "results/figure2_revised"
order = ["B1", "B2", "B3a", "B3b", "B3", "CH", "RB"]
zoom_order = ["B2", "B3a", "B3b", "B3"]

labels = {
    "B1": "B1: Productivity-first, no veto",
    "B2": "B2: Weighted sum, no veto",
    "B3a": "B3a: Veto + weighted sum",
    "B3b": "B3b: Veto + multiplicative synergy",
    "B3": "B3: Full DT-NCS",
    "CH": "CH: Constructive heuristic",
    "RB": "RB: Rule-based",
}

colors = {
    "B1": "#D55E00",
    "B2": "#0072B2",
    "B3a": "#009E73",
    "B3b": "#E69F00",
    "B3": "#882E72",
    "CH": "#6B4C3B",
    "RB": "#777777",
}

markers = {
    "B1": "s",
    "B2": "D",
    "B3a": "^",
    "B3b": "v",
    "B3": "*",
    "CH": "P",
    "RB": "o",
}

with open(INPUT, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

summary = {}

for solver in order:
    selected = [r for r in rows if r["solver"] == solver]

    if len(selected) != 10:
        raise ValueError(
            f"{solver}: expected 10 observations, found {len(selected)}."
        )

    x = np.array([float(r["productivity"]) for r in selected])
    y = np.array([float(r["wellbeing"]) for r in selected])

    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError(f"{solver}: non-finite values found.")

    critical = t.ppf(0.975, len(selected) - 1)

    summary[solver] = {
        "x": x.mean(),
        "y": y.mean(),
        "xci": critical * x.std(ddof=1) / np.sqrt(len(x)),
        "yci": critical * y.std(ddof=1) / np.sqrt(len(y)),
    }

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "pdf.fonttype": 42,
})

fig, axes = plt.subplots(1, 2, figsize=(12, 5.8))
fig.subplots_adjust(
    left=0.08,
    right=0.98,
    bottom=0.29,
    top=0.90,
    wspace=0.30,
)

overview_offsets = {
    "B1": (9, -12),
    "B2": (8, -17),
    "B3a": (-32, 18),
    "B3b": (-36, -18),
    "B3": (-30, 3),
    "CH": (9, 6),
    "RB": (9, 7),
}

zoom_offsets = {
    "B2": (14, -5),
    "B3a": (-48, 24),
    "B3b": (14, -20),
    "B3": (-46, -12),
}


def draw_panel(ax, policies, offsets):
    for solver in policies:
        d = summary[solver]

        ax.errorbar(
            d["x"],
            d["y"],
            xerr=d["xci"],
            yerr=d["yci"],
            fmt=markers[solver],
            markersize=13 if solver == "B3" else 7,
            color=colors[solver],
            ecolor=colors[solver],
            elinewidth=1.1,
            capsize=3,
            markeredgecolor="white",
            markeredgewidth=0.5,
            zorder=5 if solver == "B3" else 3,
        )

        ax.annotate(
            solver,
            (d["x"], d["y"]),
            xytext=offsets[solver],
            textcoords="offset points",
            fontsize=9,
            fontweight="bold" if solver == "B3" else "normal",
            arrowprops={
                "arrowstyle": "-",
                "color": colors[solver],
                "linewidth": 0.7,
            },
            zorder=6,
        )

    ax.set_xlabel("Mean productivity (tasks/h)")
    ax.set_ylabel("Mean well-being")
    ax.grid(True, linestyle="--", alpha=0.25)
    ax.set_axisbelow(True)


draw_panel(axes[0], order, overview_offsets)
draw_panel(axes[1], zoom_order, zoom_offsets)

axes[0].set_title("(a) All scheduling policies", loc="left", pad=12)
axes[1].set_title("(b) Detail of high-well-being policies", loc="left", pad=12)

axes[0].set_ylim(0.40, 1.01)

xlow = min(summary[s]["x"] - summary[s]["xci"] for s in zoom_order)
xhigh = max(summary[s]["x"] + summary[s]["xci"] for s in zoom_order)
ylow = min(summary[s]["y"] - summary[s]["yci"] for s in zoom_order)
yhigh = max(summary[s]["y"] + summary[s]["yci"] for s in zoom_order)

xpad = max((xhigh - xlow) * 0.30, 2.0)
ypad = max((yhigh - ylow) * 0.65, 0.008)

axes[1].set_xlim(xlow - xpad, xhigh + xpad)
axes[1].set_ylim(ylow - ypad, min(1.0, yhigh + ypad))

handles = [
    Line2D(
        [0], [0],
        marker=markers[s],
        color="none",
        markerfacecolor=colors[s],
        markeredgecolor=colors[s],
        markersize=10 if s == "B3" else 7,
        label=labels[s],
    )
    for s in order
]

fig.legend(
    handles=handles,
    loc="lower center",
    bbox_to_anchor=(0.5, 0.025),
    ncol=3,
    frameon=False,
    fontsize=9,
    columnspacing=1.8,
    handletextpad=0.6,
)

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

fig.savefig(OUTPUT + ".png", dpi=600, bbox_inches="tight")
fig.savefig(OUTPUT + ".pdf", bbox_inches="tight")
plt.close(fig)

print("Created PNG and PDF versions of Figure 2.")
print("Each policy contains 10 observations.")
print("Error bars: marginal 95% Student-t confidence intervals.")