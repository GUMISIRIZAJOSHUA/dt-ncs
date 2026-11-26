"""Explicit fatigue parameter binding; no production defaults or mutation."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from src.fatigue_kernel import advance_recovery, advance_work


@dataclass(frozen=True)
class OperatorFatigueParameters:
    initial_fatigue: float
    alpha_per_s: float
    beta: float
    rho_per_s: float
    fatigue_limit: float


@dataclass(frozen=True)
class FatigueParameters:
    step_size_s: float
    operators: Mapping
    task_demands: Mapping


def _exact_fields(value, expected, name):
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    if set(value) != set(expected):
        raise ValueError(
            f"{name} must contain exactly: {sorted(expected)}"
        )


def _ids(values, name):
    values = list(values)
    if any(type(value) is not int or value <= 0 for value in values):
        raise ValueError(f"{name} must be positive integer IDs")
    if len(values) != len(set(values)):
        raise ValueError(f"{name} contains duplicate IDs")
    return set(values)


def _unit_interval(name, value):
    if isinstance(value, bool):
        raise ValueError(f"{name} must not be boolean")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must lie in [0, 1]") from exc
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise ValueError(f"{name} must lie in [0, 1]")
    return result


def bind_fatigue_parameters(raw, *, operator_ids, task_ids):
    """Validate and copy a dedicated fatigue configuration.

    Does not initialize operators or modify a scenario.
    Uses the current kernel's numerical input restrictions.
    """
    _exact_fields(
        raw,
        {"step_size_s", "operators", "task_demands"},
        "fatigue configuration",
    )

    expected_operators = _ids(operator_ids, "scenario operator IDs")
    expected_tasks = _ids(task_ids, "scenario task IDs")

    operator_rows = raw["operators"]
    demands = raw["task_demands"]
    if not isinstance(operator_rows, Mapping):
        raise ValueError("operators must be an ID-keyed mapping")
    if not isinstance(demands, Mapping):
        raise ValueError("task_demands must be an ID-keyed mapping")

    supplied_operators = _ids(operator_rows, "parameter operator IDs")
    supplied_tasks = _ids(demands, "parameter task IDs")
    if supplied_operators != expected_operators:
        raise ValueError("Operator parameter IDs must match scenario IDs")
    if supplied_tasks != expected_tasks:
        raise ValueError("Task demand IDs must match scenario task IDs")

    # Validate the step even when the scenario has no operators or tasks.
    advance_work(
        0.0,
        0.0,
        alpha_per_s=0.0,
        beta=0.0,
        demand=0.0,
        step_size_s=raw["step_size_s"],
    )
    step_size = float(raw["step_size_s"])

    bound_operators = {}
    fields = {
        "initial_fatigue",
        "alpha_per_s",
        "beta",
        "rho_per_s",
        "fatigue_limit",
    }

    for operator_id, row in operator_rows.items():
        _exact_fields(row, fields, f"operator {operator_id}")

        # Zero-duration calls validate parameters without advancing state.
        advance_work(
            row["initial_fatigue"],
            0.0,
            alpha_per_s=row["alpha_per_s"],
            beta=row["beta"],
            demand=0.0,
            step_size_s=step_size,
        )
        advance_recovery(
            row["initial_fatigue"],
            0.0,
            rho_per_s=row["rho_per_s"],
        )
        limit = _unit_interval(
            "fatigue_limit", row["fatigue_limit"]
        )

        bound_operators[operator_id] = OperatorFatigueParameters(
            initial_fatigue=float(row["initial_fatigue"]),
            alpha_per_s=float(row["alpha_per_s"]),
            beta=float(row["beta"]),
            rho_per_s=float(row["rho_per_s"]),
            fatigue_limit=limit,
        )

    bound_demands = {
        task_id: _unit_interval("task demand", demand)
        for task_id, demand in demands.items()
    }

    return FatigueParameters(
        step_size_s=step_size,
        operators=MappingProxyType(bound_operators),
        task_demands=MappingProxyType(bound_demands),
    )