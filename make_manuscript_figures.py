from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageOps, ImageDraw
from scipy.stats import t

ROOT = Path("results/stage_a_full_20261124_091315_391055")
DATA = pd.read_csv(ROOT / "shift_metrics.csv")

ARMS = ["B1", "B2", "B3a", "B3b", "B3"]
COLORS = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00"]
MARKERS = ["o", "s", "^", "D", "P"]

required = {
    "arm", "scenario_id", "final_fatigue", "safety_violations",
    "throughput_tasks_per_hour", "total_energy_kj", "well_being_score",
}
assert required.issubset(DATA.columns), "Required columns are missing."
assert not DATA.duplicated(["arm", "scenario_id"]).any()
assert set(DATA["arm"]) == set(ARMS)

for arm in ARMS:
    assert len(DATA.loc[DATA["arm"] == arm]) == 30, arm

OUT = ROOT / "manuscript_figures"
OUT.mkdir(exist_ok=False)

plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "legend.fontsize": 9,
    "pdf.fonttype": 42,
})

saved = []


def save_figure(fig, stem):
    fig.savefig(OUT / f"{stem}.png", dpi=300, facecolor="white")
    fig.savefig(OUT / f"{stem}.pdf", facecolor="white")
    plt.close(fig)
    saved.append(stem)


def bar_plot(column, title, ylabel, stem, fatigue=False):
    summary = (
        DATA.groupby("arm")[column]
        .agg(["mean", "std", "count"])
        .reindex(ARMS)
    )
    half_width = (
        t.ppf(0.975, summary["count"] - 1)
        * summary["std"] / np.sqrt(summary["count"])
    )

    fig, ax = plt.subplots(figsize=(8, 5.5))
    x = np.arange(len(ARMS))
    ax.bar(
        x, summary["mean"], yerr=half_width,
        color=COLORS, capsize=5, width=0.65,
        edgecolor="black", linewidth=0.5,
    )
    ax.set_xticks(x, ARMS)
    ax.set_xlabel("Scheduling arm")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.25)

    upper = float((summary["mean"] + half_width).max())
    ax.set_ylim(0, 1.10 if fatigue else max(1, upper * 1.17))

    for i, mean in enumerate(summary["mean"]):
        label = f"{mean:.3f}" if fatigue else (
            "0" if mean == 0 else f"{mean:.1f}"
        )
        ax.annotate(
            label,
            (i, mean + float(half_width.iloc[i])),
            xytext=(0, 7), textcoords="offset points",
            ha="center", va="bottom", fontsize=10,
        )

    fig.text(
        0.5, 0.025,
        "30 scenarios per arm; error bars: unadjusted 95% t confidence intervals.",
        ha="center", fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    save_figure(fig, stem)


def scatter_plot(column, title, ylabel, stem, note):
    fig, ax = plt.subplots(figsize=(8, 5.5))

    for arm, color, marker in zip(ARMS, COLORS, MARKERS):
        group = DATA.loc[DATA["arm"] == arm]
        ax.scatter(
            group["throughput_tasks_per_hour"], group[column],
            label=arm, color=color, marker=marker,
            s=48, alpha=0.65, edgecolors="black", linewidths=0.35,
        )

    ax.set_xlabel("Throughput (completed jobs/hour)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(alpha=0.25)
    ax.set_axisbelow(True)
    ax.legend(
        title="Arm", loc="upper left",
        bbox_to_anchor=(1.01, 1), borderaxespad=0,
    )

    if column == "well_being_score":
        ax.set_ylim(0, 1)
    elif column == "total_energy_kj":
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)

    fig.text(0.5, 0.025, note, ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    save_figure(fig, stem)


bar_plot(
    "final_fatigue",
    "Endpoint fatigue by scheduling arm",
    "Maximum operator fatigue at dispatch termination",
    "fig01_endpoint_fatigue",
    fatigue=True,
)

bar_plot(
    "safety_violations",
    "Executed assignments flagged unsafe at selection",
    "Flagged-unsafe executed assignments per shift",
    "fig02_flagged_unsafe_executions",
)

scatter_plot(
    "total_energy_kj",
    "Throughput and total robot energy",
    "Total robot energy per shift (kJ)",
    "fig03_throughput_total_energy",
    "Each point: one arm-scenario observation. Overlapping points may be hidden.",
)

scatter_plot(
    "well_being_score",
    "Throughput and fatigue-derived well-being",
    "Fatigue-derived endpoint well-being index",
    "fig04_throughput_derived_wellbeing",
    "Each point: one arm-scenario observation. Index W = 1 - 0.86F.",
)

canvas = Image.new("RGB", (1800, 1320), "white")
draw = ImageDraw.Draw(canvas)

for i, stem in enumerate(saved):
    with Image.open(OUT / f"{stem}.png") as image:
        thumb = ImageOps.contain(image.convert("RGB"), (900, 620))
    x = (i % 2) * 900
    y = (i // 2) * 660
    draw.text((x + 15, y + 8), stem, fill="black")
    canvas.paste(thumb, (x, y + 30))

canvas.save(OUT / "manuscript_contact_sheet.png")

metadata = {
    "source": str(ROOT / "shift_metrics.csv"),
    "arm_order": ARMS,
    "observations_per_arm": 30,
    "bar_error_bars": "Unadjusted 95% Student-t confidence intervals for arm means",
    "scatter_points": "Individual arm-scenario observations; no jitter",
    "energy_outcome": "Total robot energy per shift, not energy per job",
    "wellbeing": "Fatigue-derived endpoint index; not an independent measurement",
    "original_outputs_modified": False,
}
(OUT / "figure_metadata.json").write_text(
    json.dumps(metadata, indent=2), encoding="utf-8"
)

print("Created figures in:", OUT)
for path in sorted(OUT.iterdir()):
    print(path.name, path.stat().st_size, "bytes")