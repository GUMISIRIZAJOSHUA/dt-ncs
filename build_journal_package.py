from pathlib import Path
from datetime import datetime
import csv
import hashlib
import io
import zipfile

ROOT = Path(__file__).resolve().parent
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
PREFIX = "dt_ncs_reproducibility"
OUTPUT = ROOT / f"{PREFIX}_{STAMP}.zip"

ALLOWED_SUFFIXES = {
    ".py", ".yaml", ".yml", ".csv", ".json",
    ".png", ".pdf", ".ttt", ".ttm", ".md", ".txt",
}
EXCLUDED_PARTS = {
    "venv", ".venv", ".git", "__pycache__",
    ".pytest_cache", ".mypy_cache",
}

REQUIRED = [
    "python_version.txt",
    "requirements_frozen.txt",
    "configs/experiment.yaml",
    "configs/tasks.yaml",
    "configs/arms.yaml",
    "configs/seeds.csv",
    "src/scheduler.py",
    "run_experiment.py",
    "run_solver_comparison.py",
    "run_solver_comparison_seeds.py",
    "analyze_solver_comparison.py",
    "validation/create_hrc_scene.py",
    "validation/hrc_validation_scene.ttt",
    "validation/validate_full_shift.py",
    "validation/network_emulated_client.py",
    "validation/validate_network_emulation.py",
    "validation/validate_network_sweep.py",
]

missing = [
    name for name in REQUIRED
    if not (ROOT / name).is_file()
    or (ROOT / name).stat().st_size == 0
]
if missing:
    raise SystemExit(
        "Archive not created. Missing or empty required files:\n"
        + "\n".join(missing)
    )

files = {}


def add_file(path, archive_name):
    if path.is_symlink():
        raise RuntimeError(f"Refusing symbolic link: {path}")
    files[archive_name] = path.read_bytes()


def add_tree(folder, destination):
    base = ROOT / folder
    if not base.is_dir():
        return

    for path in sorted(base.rglob("*")):
        relative = path.relative_to(base)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.is_file() and path.suffix.lower() in ALLOWED_SUFFIXES:
            add_file(
                path,
                (Path(destination) / relative).as_posix(),
            )


for folder in ["configs", "src", "results", "validation"]:
    add_tree(folder, folder)

backup_name = "backup_2026-11-21_statistics"
add_tree(
    backup_name,
    f"historical_snapshot/{backup_name}",
)

for path in sorted(ROOT.glob("*.py")):
    if path.name not in {
        "build_journal_package.py",
        "inspect_submission.py",
    }:
        add_file(path, path.name)

for name in [
    "python_version.txt",
    "requirements_frozen.txt",
    "project_inventory.txt",
]:
    path = ROOT / name
    if path.is_file():
        add_file(path, name)

add_file(
    Path(__file__).resolve(),
    "packaging/build_journal_package.py",
)

readme = r"""# DT-NCS experiment reproducibility archive

## Status
This archive preserves the current project source, configurations,
available result files, figures, and regenerated CoppeliaSim scene.
It is not a certification that historical results reproduce with
the current scheduler. Read PROVENANCE.md before interpreting results.

CoppeliaSim version and edition: NOT YET RECORDED.
CoppeliaSim is an external prerequisite and is not bundled.

## Environment
The reported Python version is 3.13.7.
The included python_version.txt and requirements_frozen.txt record
the captured environment; clean-install compatibility has not
been independently tested.

In an extracted WORKING COPY, from its project root:

    python -m venv .venv
    .venv\Scripts\activate
    python -m pip install -r requirements_frozen.txt

## Preservation warning
Keep an untouched extraction as the reference archive.
Run experiments only in a separate working copy.
Scripts may overwrite the included result CSVs and figures.

## Main experiment
From the extracted project root:

    python run_experiment.py

Reads configs/experiment.yaml, tasks.yaml, arms.yaml, and seeds.csv.
Writes shift_metrics.csv, summary_statistics.json,
paired_comparisons.csv, and plots under results/.

## Solver comparison
Run:

    python run_solver_comparison_seeds.py
    python analyze_solver_comparison.py

The multi-seed wrapper defaults to seeds 101 through 110 and
explicitly passes configs/experiment.yaml to the single-seed runner.
It writes results/solver_comparison_seeds.csv.
Analysis defaults to reference B3.

For a single-seed run, specify the configuration explicitly:

    python run_solver_comparison.py --config configs/experiment.yaml --seed 101 --output results/single_seed_101.csv

Do not use the single-seed runner's default configuration blindly:
its default is configs/base.yaml, which was absent from the supplied
project inventory.

The common-objective, outcomes, and runtime CSVs present in results/
are retained historical artifacts. Their exact generation commands
have not been established from the inspected entry points.

## CoppeliaSim
Save unrelated work before running validation scripts, which load
or close scenes. Keep the working directory at this project root.

The included validation/hrc_validation_scene.ttt was regenerated
from validation/create_hrc_scene.py during archive preparation.
Regenerating it again is optional and replaces the scene artifact:

    python validation\create_hrc_scene.py

With CoppeliaSim running and its remote API available:

    python validation\validate_full_shift.py
    python validation\validate_network_emulation.py

The full-shift script uses B3, scenario seed 1, and search seed 1.
The network test uses up to the first 12 assignments, 50 +/- 10 ms
injected delay, drop probability 0.02, and maximum_retries=3.

The current sweep is a separate optional run:

    python validation\validate_network_sweep.py

It currently contains only 100 +/- 20 ms and 0.03 drop probability,
with maximum_retries=10. It is not the earlier low/moderate sweep.

## Figures
Included figure scripts:
- make_figure2.py
- make_figure3.py
- validation/create_figure6.py

Scripts and existing figures are preserved. Figure regeneration
and correspondence to historical input data have not been verified.

## Integrity
MANIFEST_SHA256.csv lists the size and SHA-256 digest of every
other file in this archive. The manifest excludes itself.
ZIP integrity testing checks archive corruption, not scientific validity.
"""

provenance = r"""# Provenance and limitations

## Source versions
The current scheduler and historical backup differ.
Neither file hash alone establishes which generated historical results.

Reported hashes at inspection:
- Current src/scheduler.py:
  90372be6ef181fcbdb8511f01204d09a696be20c12f1a10e0076271fd5de66a2
- Historical backup src/scheduler.py:
  79342afcdab54dacb983f4b4cb92ecd5e88fe7d03e74a8a0ca7a8c5773f69ff3

The historical_snapshot directory preserves the available backup;
it is not assumed to be the definitive primary-results source.
The manifest records the actual files packaged.

## Regenerated scene
The scene was regenerated during preparation, not recovered as
the original saved validation artifact.
The reported regenerated file size was 245982 bytes.
Its ten-step smoke test reached simulation time 0.500 s.

The scene uses box placeholders and task markers, not a physical
robot or a validated human model.

## Full-shift playback
The previously reported result was 12 assignments:
scheduler makespan 358.019 s; simulator makespan 358.050 s;
difference 0.031 s; scheduler-reported safety violations 0;
scheduler veto events 183.
These figures came from the earlier run, not a new archive-build run.

The inspected playback executes assignments sequentially between
alternating marker pairs. It does not reproduce planned start-time
gaps or concurrent assignments.
The script assumes 0.05 s per step without explicitly checking
or setting the simulator timestep.

executed_duration_s copies the planned assignment duration.
executed_start_s is reconstructed from the observed end time minus
the planned duration, rather than measured independently.

Safety violations and veto totals originate in the scheduler.
These results do not establish physical robot safety.

## Network-emulation measurement
The wrapper injects a sleep before each attempt and simulates
drops before invoking the remote function.
This is application-level command-attempt emulation, not a
measurement of real network packet loss.

The recorded RTT timer begins after injected delay and simulated
drops/retries. RTT therefore excludes those emulation costs.

commands_sent increments once per logical wrapper call.
commands_dropped counts simulated dropped attempts.
commands_retried counts dropped attempts followed by another attempt.
These are not interchangeable denominators for a packet-loss rate.

No wall-clock deadline guarantee follows from successful playback
in stepped simulation.

## Network result provenance
The earlier standalone run reportedly completed 12 assignments,
with 14378 successful commands and 289 drops/retries.
Earlier low/moderate sweep console records reported:
- 10 +/- 5 ms, 0.5%: 12 assignments, 14367 successful commands,
  69 drops/retries, no unrecoverable failure reported.
- 50 +/- 10 ms, 2%: 12 assignments, 14367 successful commands,
  289 drops/retries, no unrecoverable failure reported.

network_condition_sweep_partial_results.csv was manually reconstructed
from console output. It is not an untouched raw instrument output.
Its makespan values came from the separate full-shift run and must
not be presented as measurements from those network trials.

The 150 +/- 40 ms, 5% attempt failed initially after three retries.
Completion of subsequent attempts is unverified.
Completion of the 100 +/- 20 ms, 3% attempt is also unverified.

The current standalone script uses three retries; the current sweep
uses ten. Historical retry settings must not be inferred solely
from current source.

The sweep writes its CSV only after its condition loop completes.
An uncaught failure can terminate it before new results are saved.
The presence of a sweep CSV does not prove that all attempted
conditions completed, or that it came from the current source.

## Remaining verification
- Record CoppeliaSim version and edition.
- Inspect result contents and verify their run provenance.
- Establish pre/post scheduler-fix provenance for primary results.
- Test environment installation and reproduction in a clean copy.
- Verify figure-to-data correspondence.
- Review archive contents for sensitive or unrelated information.

Archive creation does not perform these scientific checks.
"""

files["README.md"] = readme.encode("utf-8")
files["PROVENANCE.md"] = provenance.encode("utf-8")

inventory = "\n".join(sorted(files)) + "\n"
files["PACKAGED_INVENTORY.txt"] = inventory.encode("utf-8")

manifest_buffer = io.StringIO(newline="")
writer = csv.writer(manifest_buffer)
writer.writerow(["path", "size_bytes", "sha256"])
for name, data in sorted(files.items()):
    writer.writerow([
        name,
        len(data),
        hashlib.sha256(data).hexdigest(),
    ])
files["MANIFEST_SHA256.csv"] = manifest_buffer.getvalue().encode("utf-8")

with zipfile.ZipFile(
    OUTPUT,
    mode="x",
    compression=zipfile.ZIP_DEFLATED,
) as archive:
    for name, data in sorted(files.items()):
        archive.writestr(f"{PREFIX}/{name}", data)

with zipfile.ZipFile(OUTPUT, "r") as archive:
    bad_file = archive.testzip()
    if bad_file is not None:
        raise RuntimeError(f"ZIP integrity check failed: {bad_file}")

archive_hash = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
hash_file = OUTPUT.with_suffix(".zip.sha256")
hash_file.write_text(
    f"{archive_hash}  {OUTPUT.name}\n",
    encoding="ascii",
)

print("Archive created:", OUTPUT)
print("Files included:", len(files))
print("Archive size:", OUTPUT.stat().st_size, "bytes")
print("ZIP integrity check: PASSED")
print("SHA-256:", archive_hash)
print("Checksum file:", hash_file)
print("Scientific reproduction: NOT TESTED")
print("Review archive contents before submission.")