# Synthetic benchmark fatigue baseline

Approval date: 2026-11-24
File creation time (UTC): 2026-11-24T00:07:27.851830+00:00

## Status and provenance

The user explicitly approved these numerical fatigue values.
They are synthetic design choices, not physiologically calibrated,
not paper-derived, and not a validated model of real workers.

The values match the earlier smoke configuration, but benchmark use
was approved separately. The smoke file was not modified.

Source file: configs/fatigue_synthetic_smoke_only.yaml
Source SHA-256: 1c0f2425e91a8a0de539ea44b38d8c90642950a90489b6faa565c456df67d161
Benchmark file: configs/fatigue_synthetic_benchmark.yaml
Benchmark SHA-256: 1539e2138cc1add9e8d313e960dff9544e156d1b3e6ea4b921eb45d6e3e0295f

## Approved values

Both operators, IDs 1 and 2:
- initial_fatigue: 0.10
- alpha_per_s: 0.001
- beta: 0.0
- rho_per_s: 0.001
- fatigue_limit: 0.80

Integration step_size_s: 0.5
Demand for every task ID from 1 through 12: 0.50

## Design rationale

Identical operator fatigue parameters avoid introducing operator-specific
fatigue coefficients into this baseline. Uniform task demand deliberately
does not represent measured differences among task types.

## Validation and limitations

The serialized YAML was loaded and accepted by FatigueAdapter, which
invokes bind_fatigue_parameters, for operator IDs 1 and 2 and task IDs 1-12.
This is schema and parameter-binding validation only.

No actual scenario was loaded, initialized, or executed.
Matching IDs in the eventual scenario remains to be checked.
No global safety threshold was read or modified by this script.
Kernel trajectories and numerical interpretation were not reverified here.

## Execution approval

This configuration does not authorize a pilot or main experiment.
Task quantities, engineering sizing runs, and experiment run counts
remain separate decisions. Sensitivity conditions are not approved
for execution by approval of this baseline.
