"""Fatigue-only feasibility; not a complete assignment safety check."""

import math

from src.fatigue_kernel import advance_recovery, advance_work


def is_work_fatigue_feasible(
    fatigue,
    duration_s,
    *,
    fatigue_limit,
    alpha_per_s,
    beta,
    demand,
    step_size_s,
):
    """Check the maximum fatigue of the complete discrete work projection."""
    if isinstance(fatigue_limit, bool):
        raise ValueError("fatigue_limit must be numeric, not boolean")
    try:
        limit = float(fatigue_limit)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("fatigue_limit must lie in [0, 1]") from exc
    if not math.isfinite(limit) or not 0 <= limit <= 1:
        raise ValueError("fatigue_limit must lie in [0, 1]")

    projection = advance_work(
        fatigue,
        duration_s,
        alpha_per_s=alpha_per_s,
        beta=beta,
        demand=demand,
        step_size_s=step_size_s,
    )
    return projection.maximum_fatigue <= limit


def find_work_feasible_rest_delay(
    fatigue,
    duration_s,
    *,
    fatigue_limit,
    alpha_per_s,
    beta,
    demand,
    step_size_s,
    rho_per_s,
    max_delay_s,
):
    """Return a feasible rest delay within the bound, or None.

    Assumes continuous eligible recovery before the assignment, with
    unchanged work duration, demand, parameters, and numerical step size.

    This does not check availability, disturbances, geometry, ergonomics,
    or the production horizon. The caller must handle those constraints.
    """
    work_parameters = {
        "fatigue_limit": fatigue_limit,
        "alpha_per_s": alpha_per_s,
        "beta": beta,
        "demand": demand,
        "step_size_s": step_size_s,
    }

    # Validate work inputs even if the recovery interval cannot help.
    initially_feasible = is_work_fatigue_feasible(
        fatigue, duration_s, **work_parameters
    )

    # Validate recovery inputs even if the assignment is already feasible.
    maximum_rested_fatigue = advance_recovery(
        fatigue, max_delay_s, rho_per_s=rho_per_s
    )
    upper = float(max_delay_s)

    if initially_feasible:
        return 0.0

    if not is_work_fatigue_feasible(
        maximum_rested_fatigue, duration_s, **work_parameters
    ):
        return None

    lower = 0.0

    # Non-negative accumulation parameters make the work projection
    # monotone in starting fatigue. Keep the upper endpoint feasible.
    for _ in range(64):
        midpoint = lower + (upper - lower) / 2.0
        if midpoint == lower or midpoint == upper:
            break

        rested_fatigue = advance_recovery(
            fatigue, midpoint, rho_per_s=rho_per_s
        )
        if is_work_fatigue_feasible(
            rested_fatigue, duration_s, **work_parameters
        ):
            upper = midpoint
        else:
            lower = midpoint

    return upper