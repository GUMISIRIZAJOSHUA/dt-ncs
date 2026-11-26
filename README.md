# DT-NCS: event-triggered digital-twin scheduling for human-robot collaborative assembly

Release **v1.0.0**. Code and data supporting the manuscript.

## Contents
- `src/`, `configs/`, `tests/`: scheduler, policies (B1, B2, B3a, B3b, B3), configurations, tests
- root `*.py`: experiment, statistics, sensitivity and figure scripts
- `results/`: the four full benchmark runs (original, baseline, low and high alpha),
  sensitivity tables, CoppeliaSim run records
- `validation/`: CoppeliaSim scene, validation scripts and results
- `MANIFEST.sha256`: SHA-256 checksum of every released file

## Experiment summary
- Policies: B1 (productivity, no veto), B2 (weighted sum, no veto), B3a (weighted sum + veto),
  B3b (multiplicative synergy + veto), B3 (well-being first, synergy on exact ties, + veto)
- 30 matched scenarios per policy; 1,200-job backlog; 28,800 s shift; serial execution
- Fatigue-accumulation sensitivity: 0.00075, 0.001, 0.00125 s^-1
- Collision and safe-zone values are identifier-based proxies (no spatial layout)

## Requirements
- Python 3.13.7; see `requirements.txt`
- CoppeliaSim V4.10.0 rev0 (only for the execution tests)

## Verify
`python verify_manifest.py` checks file integrity against `MANIFEST.sha256`.

## Licence
MIT. See `LICENSE`.
