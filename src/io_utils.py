import csv
import json
import os
from typing import Dict, List

import yaml


def load_yaml(file_path: str) -> Dict:
    with open(file_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_seeds(file_path: str) -> List[Dict]:
    seeds = []

    with open(file_path, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            seeds.append(
                {
                    "arm": row["arm"],
                    "replicate": int(row["replicate"]),
                    "scenario_seed": int(row["scenario_seed"]),
                    "search_seed": int(row["search_seed"]),
                }
            )

    return seeds


def ensure_directory(directory_path: str) -> None:
    os.makedirs(directory_path, exist_ok=True)


def save_json(
    data: Dict,
    file_path: str,
) -> None:
    ensure_directory(os.path.dirname(file_path))

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, default=str)


def save_csv(
    rows: List[Dict],
    file_path: str,
) -> None:
    if not rows:
        raise ValueError("No rows provided")

    ensure_directory(os.path.dirname(file_path))

    fieldnames = list(rows[0].keys())

    with open(file_path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_csv_row(
    row: Dict,
    file_path: str,
) -> None:
    ensure_directory(os.path.dirname(file_path))

    file_exists = os.path.exists(file_path)

    fieldnames = list(row.keys())

    with open(file_path, "a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)


def save_text(
    text: str,
    file_path: str,
) -> None:
    ensure_directory(os.path.dirname(file_path))

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(text)