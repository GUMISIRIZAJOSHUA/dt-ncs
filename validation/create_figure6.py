import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


VALIDATION_DIR = Path(__file__).resolve().parent

FULL_SHIFT_RESULTS = (
    VALIDATION_DIR / "full_shift_validation_results.csv"
)

NETWORK_RESULT_FILES = [
    VALIDATION_DIR / "network_condition_sweep_partial_results.csv",
    VALIDATION_DIR / "network_condition_sweep_results.csv",
]

OUTPUT_PNG = VALIDATION_DIR / "figure6_revised.png"
OUTPUT_PDF = VALIDATION_DIR / "figure6_revised.pdf"
# Reported makespans from the completed full-shift validation.
SCHEDULER_MAKESPAN_S = 358.019
SIMULATOR_MAKESPAN_S = 358.050

CONDITION_ORDER = [
    "low_delay",
    "moderate_delay",
    "degraded_delay",
]


def read_csv(path):
    if not path.is_file():
        raise FileNotFoundError(f"Required CSV not found: {path}")

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")

        return [
            row
            for row in reader
            if any(
                str(value).strip()
                for value in row.values()
                if value is not None
            )
        ]


def numeric(row, key):
    value = row.get(key)

    if value is None or str(value).strip() == "":
        raise ValueError(
            f"Missing numeric column '{key}' in row:\n{row}"
        )

    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid value for '{key}': {value!r}"
        ) from error

    if not math.isfinite(number):
        raise ValueError(
            f"Non-finite value for '{key}': {value!r}"
        )

    return number


def integer(row, key):
    number = numeric(row, key)

    if not number.is_integer():
        raise ValueError(
            f"Expected an integer for '{key}', found {number}"
        )

    return int(number)


def load_assignments():
    rows = read_csv(FULL_SHIFT_RESULTS)

    if len(rows) != 12:
        raise ValueError(
            f"Expected 12 assignments, found {len(rows)} "
            f"in {FULL_SHIFT_RESULTS}"
        )

    rows.sort(
        key=lambda row: integer(row, "assignment_index")
    )

    indices = [
        integer(row, "assignment_index")
        for row in rows
    ]

    if indices != list(range(1, 13)):
        raise ValueError(
            "Assignment indices must be exactly 1 through 12."
        )

    task_ids = [row.get("task_id") for row in rows]

    if None in task_ids or len(set(task_ids)) != 12:
        raise ValueError(
            "Expected 12 distinct task IDs."
        )

    for row in rows:
        start = numeric(row, "planned_start_s")
        duration = numeric(row, "planned_duration_s")

        if start < 0 or duration <= 0:
            raise ValueError(
                f"Invalid assignment timing:\n{row}"
            )

    return rows


def load_network_results():
    by_condition = {}

    for path in NETWORK_RESULT_FILES:
        if not path.is_file():
            continue

        for row in read_csv(path):
            condition = row.get("condition", "").strip()

            if condition in CONDITION_ORDER:
                # The final results file takes precedence
                # when a condition appears in both files.
                by_condition[condition] = row

    missing = [
        condition
        for condition in CONDITION_ORDER
        if condition not in by_condition
    ]

    if missing:
        raise ValueError(
            "Missing network conditions: "
            + ", ".join(missing)
            + "\nExpected results in:\n"
            + "\n".join(
                str(path)
                for path in NETWORK_RESULT_FILES
            )
            + "\nNo missing measurements have been fabricated."
        )

    rows = [
        by_condition[condition]
        for condition in CONDITION_ORDER
    ]

    for row in rows:
        for key in [
            "base_latency_ms",
            "jitter_ms",
            "packet_loss_probability",
        ]:
            numeric(row, key)

        for key in [
            "assignments_executed",
            "commands_dropped",
            "commands_retried",
            "unrecoverable_failures",
        ]:
            if integer(row, key) < 0:
                raise ValueError(
                    f"Negative count for '{key}': {row}"
                )

    return rows


def style_axis(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(
        axis="both",
        labelsize=9,
    )
    ax.set_axisbelow(True)


def plot_timeline(ax, assignments):
    for row in assignments:
        index = integer(row, "assignment_index")
        start = numeric(row, "planned_start_s")
        duration = numeric(row, "planned_duration_s")

        ax.barh(
            index,
            duration,
            left=start,
            height=0.62,
            color="#2E6F9E",
            edgecolor="white",
            linewidth=0.6,
        )

    maximum_end = max(
        numeric(row, "planned_start_s")
        + numeric(row, "planned_duration_s")
        for row in assignments
    )

    ax.set_title(
        "A. Planned assignment timeline",
        loc="left",
        fontweight="bold",
        fontsize=11,
        pad=14,
    )
    ax.set_xlabel("Planned time (s)", fontsize=10)
    ax.set_ylabel("Assignment index", fontsize=10)
    ax.set_yticks(range(1, 13))
    ax.set_ylim(0.3, 12.7)
    ax.set_xlim(
        0,
        max(maximum_end, SIMULATOR_MAKESPAN_S) * 1.03,
    )
    ax.grid(
        axis="x",
        linestyle="--",
        alpha=0.3,
    )
    style_axis(ax)


def plot_makespan(ax):
    values = [
        SCHEDULER_MAKESPAN_S,
        SIMULATOR_MAKESPAN_S,
    ]

    bars = ax.bar(
        [0, 1],
        values,
        width=0.58,
        color=["#2E6F9E", "#D97B29"],
        edgecolor="white",
        linewidth=0.8,
    )

    for bar, value in zip(bars, values):
        ax.annotate(
            f"{value:.3f} s",
            xy=(
                bar.get_x() + bar.get_width() / 2,
                value,
            ),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    difference = abs(values[1] - values[0])

    ax.set_title(
        "B. Makespan agreement",
        loc="left",
        fontweight="bold",
        fontsize=11,
        pad=14,
    )
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Scheduler", "CoppeliaSim"])
    ax.set_ylabel("Makespan (s)", fontsize=10)
    ax.set_ylim(0, 405)
    ax.set_yticks([0, 100, 200, 300, 400])

    ax.text(
        0.5,
        0.06,
        f"Absolute difference: {difference:.3f} s",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=9,
        bbox={
            "boxstyle": "round,pad=0.4",
            "facecolor": "white",
            "edgecolor": "#AAAAAA",
            "alpha": 0.95,
        },
    )

    ax.grid(
        axis="y",
        linestyle="--",
        alpha=0.3,
    )
    style_axis(ax)


def condition_label(row):
    names = {
        "low_delay": "Low delay",
        "moderate_delay": "Moderate delay",
        "degraded_delay": "Degraded delay",
    }

    condition = row["condition"].strip()
    latency = numeric(row, "base_latency_ms")
    jitter = numeric(row, "jitter_ms")
    loss = (
        numeric(row, "packet_loss_probability") * 100
    )

    return (
        f"{names[condition]}\n"
        f"{latency:g} ± {jitter:g} ms\n"
        f"{loss:g}% loss"
    )


def plot_network(ax, rows):
    dropped = [
        integer(row, "commands_dropped")
        for row in rows
    ]
    retried = [
        integer(row, "commands_retried")
        for row in rows
    ]
    failures = [
        integer(row, "unrecoverable_failures")
        for row in rows
    ]
    completed = [
        integer(row, "assignments_executed")
        for row in rows
    ]

    x = np.arange(len(rows))
    width = 0.34

    dropped_bars = ax.bar(
        x - width / 2,
        dropped,
        width,
        color="#C0504D",
        edgecolor="white",
        linewidth=0.7,
        label="Dropped commands",
    )

    retried_bars = ax.bar(
        x + width / 2,
        retried,
        width,
        color="#4F81BD",
        edgecolor="white",
        linewidth=0.7,
        label="Retried commands",
    )

    for bars in [dropped_bars, retried_bars]:
        for bar in bars:
            ax.annotate(
                f"{int(bar.get_height())}",
                xy=(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                ),
                xytext=(0, 5),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    maximum_count = max(dropped + retried + [1])
    upper_limit = (
        math.ceil(maximum_count * 1.35 / 100) * 100
    )

    ax.set_title(
        "C. Network-emulation robustness",
        loc="left",
        fontweight="bold",
        fontsize=11,
        pad=14,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(
        [condition_label(row) for row in rows]
    )
    ax.set_ylabel("Reported count", fontsize=10)
    ax.set_ylim(0, upper_limit)

    ax.legend(
        loc="upper left",
        frameon=False,
        fontsize=9,
    )

    if all(value == 12 for value in completed) and all(
        value == 0 for value in failures
    ):
        status = (
            "All conditions: 12/12 assignments; "
            "0 unrecoverable failures"
        )
    else:
        status = (
            "Assignments completed: "
            + "/".join(str(value) for value in completed)
            + "; failures: "
            + "/".join(str(value) for value in failures)
        )

    ax.text(
        0.5,
        -0.23,
        status,
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8.5,
    )

    ax.grid(
        axis="y",
        linestyle="--",
        alpha=0.3,
    )
    style_axis(ax)


def main():
    assignments = load_assignments()
    network_rows = load_network_results()

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.labelsize": 10,
            "axes.titlesize": 11,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.facecolor": "white",
        }
    )

    figure, axes = plt.subplots(
        1,
        3,
        figsize=(16, 5.4),
        gridspec_kw={
            "width_ratios": [1.3, 0.85, 1.4],
        },
    )

    plot_timeline(axes[0], assignments)
    plot_makespan(axes[1])
    plot_network(axes[2], network_rows)

    figure.subplots_adjust(
        left=0.055,
        right=0.99,
        top=0.88,
        bottom=0.28,
        wspace=0.32,
    )

    figure.savefig(
        OUTPUT_PNG,
        dpi=400,
        bbox_inches="tight",
    )
    figure.savefig(
        OUTPUT_PDF,
        bbox_inches="tight",
    )
    plt.close(figure)

    for path in [OUTPUT_PNG, OUTPUT_PDF]:
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(
                f"Output was not created correctly: {path}"
            )

        print(f"Created: {path}")

    print(
        "Panel A uses planned assignment times. "
        "Network results are ordered low, moderate, degraded."
    )


if __name__ == "__main__":
    main()