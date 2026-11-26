from datetime import datetime, timezone
from pathlib import Path
import hashlib

import yaml

from src.fatigue_adapter import FatigueAdapter


def main():
    source = Path("configs/fatigue_synthetic_smoke_only.yaml")
    target = Path("configs/fatigue_synthetic_benchmark.yaml")
    provenance = Path("configs/fatigue_synthetic_benchmark_provenance.md")

    operator_parameters = {
        "initial_fatigue": 0.10,
        "alpha_per_s": 0.001,
        "beta": 0.0,
        "rho_per_s": 0.001,
        "fatigue_limit": 0.80,
    }
    approved = {
        "step_size_s": 0.5,
        "operators": {
            operator_id: dict(operator_parameters)
            for operator_id in (1, 2)
        },
        "task_demands": {
            task_id: 0.50 for task_id in range(1, 13)
        },
    }

    source_bytes = source.read_bytes()
    smoke_raw = yaml.safe_load(source_bytes.decode("utf-8-sig"))
    if smoke_raw != approved:
        raise ValueError(
            "Smoke configuration differs from the approved baseline; "
            "no output files were written."
        )

    header = (
        "# APPROVED SYNTHETIC BENCHMARK FATIGUE BASELINE.\n"
        "# Researcher-selected; not physiologically calibrated or paper-derived.\n"
        "# Approved in conversation on 2026-11-24.\n"
        "# See fatigue_synthetic_benchmark_provenance.md.\n"
    )
    benchmark_text = header + yaml.safe_dump(approved, sort_keys=False)
    benchmark_bytes = benchmark_text.encode("utf-8")

    parsed = yaml.safe_load(benchmark_text)
    adapter = FatigueAdapter(
        parsed,
        operator_ids=(1, 2),
        task_ids=range(1, 13),
    )
    if len(adapter.parameters.operators) != 2:
        raise ValueError("Unexpected bound operator count")
    if len(adapter.parameters.task_demands) != 12:
        raise ValueError("Unexpected bound task count")

    existing = [str(p) for p in (target, provenance) if p.exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite: " + ", ".join(existing)
        )

    source_hash = hashlib.sha256(source_bytes).hexdigest()
    benchmark_hash = hashlib.sha256(benchmark_bytes).hexdigest()
    created = datetime.now(timezone.utc).isoformat()

    provenance_text = f"""# Synthetic benchmark fatigue baseline

Approval date: 2026-11-24
File creation time (UTC): {created}

## Status and provenance

The user explicitly approved these numerical fatigue values.
They are synthetic design choices, not physiologically calibrated,
not paper-derived, and not a validated model of real workers.

The values match the earlier smoke configuration, but benchmark use
was approved separately. The smoke file was not modified.

Source file: {source.as_posix()}
Source SHA-256: {source_hash}
Benchmark file: {target.as_posix()}
Benchmark SHA-256: {benchmark_hash}

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
"""

    with target.open("xb") as handle:
        handle.write(benchmark_bytes)
    with provenance.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(provenance_text)

    print("PASS: benchmark YAML accepted by FatigueAdapter.")
    print("Created:", target)
    print("Created:", provenance)
    print("Benchmark SHA-256:", benchmark_hash)
    print("Smoke file unchanged:", source.read_bytes() == source_bytes)
    print("No simulation executed.")


if __name__ == "__main__":
    main()