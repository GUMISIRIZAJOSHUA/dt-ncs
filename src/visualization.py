import os
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

import pandas as pd


def ensure_output_directory(
    output_path: str,
) -> None:
    os.makedirs(output_path, exist_ok=True)


def plot_metric_by_arm(
    metrics: List[Dict],
    metric_column: str,
    title: str,
    y_label: str,
    output_path: str,
    output_file: str,
) -> None:
    ensure_output_directory(output_path)

    dataframe = pd.DataFrame(metrics)

    summary = dataframe.groupby("arm")[metric_column].agg(
        ["mean", "std", "count"]
    )

    summary = summary.reset_index()

    error = summary["std"] / summary["count"].apply(
        lambda count: count ** 0.5 if count > 0 else 1.0
    )

    figure, axis = plt.subplots(figsize=(8, 5))

    axis.bar(
        summary["arm"],
        summary["mean"],
        yerr=error,
        capsize=5,
        color="#4C72B0",
    )

    axis.set_title(title)
    axis.set_xlabel("Scheduling arm")
    axis.set_ylabel(y_label)
    axis.grid(axis="y", alpha=0.3)

    figure.tight_layout()

    output_file_path = os.path.join(
        output_path,
        output_file,
    )

    figure.savefig(output_file_path, dpi=300)
    plt.close(figure)


def plot_tradeoff(
    metrics: List[Dict],
    x_column: str,
    y_column: str,
    x_label: str,
    y_label: str,
    title: str,
    output_path: str,
    output_file: str,
) -> None:
    ensure_output_directory(output_path)

    dataframe = pd.DataFrame(metrics)

    figure, axis = plt.subplots(figsize=(8, 5))

    for arm, arm_data in dataframe.groupby("arm"):
        axis.scatter(
            arm_data[x_column],
            arm_data[y_column],
            label=arm,
            alpha=0.7,
        )

    axis.set_title(title)
    axis.set_xlabel(x_label)
    axis.set_ylabel(y_label)
    axis.legend(title="Arm")
    axis.grid(alpha=0.3)

    figure.tight_layout()

    output_file_path = os.path.join(
        output_path,
        output_file,
    )

    figure.savefig(output_file_path, dpi=300)
    plt.close(figure)


def plot_safety_violations(
    metrics: List[Dict],
    output_path: str,
) -> None:
    plot_metric_by_arm(
        metrics=metrics,
        metric_column="safety_violations",
        title="Safety violations by scheduling arm",
        y_label="Safety violations",
        output_path=output_path,
        output_file="safety_violations.png",
    )


def plot_fatigue(
    metrics: List[Dict],
    output_path: str,
) -> None:
    plot_metric_by_arm(
        metrics=metrics,
        metric_column="final_fatigue",
        title="Final operator fatigue by scheduling arm",
        y_label="Final fatigue level",
        output_path=output_path,
        output_file="final_fatigue.png",
    )


def plot_throughput_energy_tradeoff(
    metrics: List[Dict],
    output_path: str,
) -> None:
    plot_tradeoff(
        metrics=metrics,
        x_column="throughput_tasks_per_hour",
        y_column="total_energy_kj",
        x_label="Throughput (tasks/hour)",
        y_label="Total robot energy (kJ)",
        title="Throughput-energy trade-off",
        output_path=output_path,
        output_file="throughput_energy_tradeoff.png",
    )


def plot_wellbeing_productivity_tradeoff(
    metrics: List[Dict],
    output_path: str,
) -> None:
    plot_tradeoff(
        metrics=metrics,
        x_column="throughput_tasks_per_hour",
        y_column="well_being_score",
        x_label="Throughput (tasks/hour)",
        y_label="Well-being score",
        title="Productivity-well-being trade-off",
        output_path=output_path,
        output_file="wellbeing_productivity_tradeoff.png",
    )