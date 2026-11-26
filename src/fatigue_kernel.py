"""Deterministic fatigue equations; no production parameter defaults."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkProjection:
    final_fatigue: float
    maximum_fatigue: float


def _nonnegative(name, value):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric, not boolean")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite and non-negative") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


def _unit_interval(name, value):
    value = _nonnegative(name, value)
    if value > 1:
        raise ValueError(f"{name} must lie in [0, 1]")
    return value


def advance_work(
    fatigue,
    duration_s,
    *,
    alpha_per_s,
    beta,
    demand,
    step_size_s,
):
    """Apply bounded discrete work updates, including a final partial step.

    All parameters are explicit. Initial fatigue is validated, not clipped.
    Maximum fatigue includes the initial state and every updated state.
    """
    fatigue = _unit_interval("fatigue", fatigue)
    duration_s = _nonnegative("duration_s", duration_s)
    alpha = _nonnegative("alpha_per_s", alpha_per_s)
    beta = _nonnegative("beta", beta)
    demand = _unit_interval("demand", demand)
    step_size = _nonnegative("step_size_s", step_size_s)
    if step_size == 0:
        raise ValueError("step_size_s must be positive")

    maximum = fatigue
    remaining = duration_s

    if alpha == 0 or demand == 0 or fatigue == 1:
        return WorkProjection(fatigue, maximum)

    while remaining > 0:
        dt = min(step_size, remaining)
        increment = alpha * demand * (1.0 + beta * fatigue) * dt
        if not math.isfinite(increment):
            raise ValueError("Non-finite work increment")

        fatigue = min(1.0, max(0.0, fatigue + increment))
        maximum = max(maximum, fatigue)

        # With non-negative parameters, saturation is absorbing during work.
        if fatigue == 1.0:
            return WorkProjection(fatigue, maximum)

        new_remaining = remaining - dt
        if new_remaining == remaining:
            raise ValueError("Step size too small for this duration")
        remaining = new_remaining

    return WorkProjection(fatigue, maximum)


def advance_recovery(fatigue, duration_s, *, rho_per_s):
    """Apply exponential recovery over one eligible recovery interval."""
    fatigue = _unit_interval("fatigue", fatigue)
    duration_s = _nonnegative("duration_s", duration_s)
    rho = _nonnegative("rho_per_s", rho_per_s)

    if duration_s == 0 or rho == 0 or fatigue == 0:
        return fatigue

    return fatigue * math.exp(-rho * duration_s)