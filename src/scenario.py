from dataclasses import dataclass, field
from typing import Dict, List
import random

from src.jobs import JobInstance, build_backlog


@dataclass
class Task:
    task_id: int
    name: str
    manual_time_s: float
    robot_time_s: float
    fatigue_coefficient: float
    cognitive_load: float
    robot_energy_kj: float
    defect_risk: float


@dataclass
class Operator:
    operator_id: int
    name: str
    base_skill: float
    fatigue_capacity: float
    fatigue_level: float = 0.0
    completed_tasks: List[int] = field(default_factory=list)


@dataclass
class Robot:
    robot_id: int
    name: str
    base_speed: float
    energy_capacity_kj: float
    energy_used_kj: float = 0.0
    completed_tasks: List[int] = field(default_factory=list)


@dataclass
class Scenario:
    scenario_id: int
    shift_duration_s: float
    tasks: List[Task]
    operators: List[Operator]
    robots: List[Robot]
    disturbance_events: List[Dict] = field(default_factory=list)
    completed_task_ids: set = field(default_factory=set)
    jobs: List[JobInstance] = field(default_factory=list)
    completed_job_ids: set = field(default_factory=set)


def load_tasks(config: Dict) -> List[Task]:
    tasks = []
    for raw in config["tasks"]:
        tasks.append(
            Task(
                task_id=int(raw["id"]),
                name=raw["name"],
                manual_time_s=float(raw["manual_time_s"]),
                robot_time_s=float(raw["robot_time_s"]),
                fatigue_coefficient=float(raw["fatigue_coefficient"]),
                cognitive_load=float(raw["cognitive_load"]),
                robot_energy_kj=float(raw["robot_energy_kj"]),
                defect_risk=float(raw["defect_risk"]),
            )
        )
    return tasks


def build_operators(config: Dict, scenario_seed: int) -> List[Operator]:
    rng = random.Random(scenario_seed)
    operators = []

    for operator_id in range(1, 3):
        base_skill = rng.uniform(0.75, 1.05)
        fatigue_capacity = rng.uniform(0.85, 1.15)

        operators.append(
            Operator(
                operator_id=operator_id,
                name=f"Operator-{operator_id}",
                base_skill=base_skill,
                fatigue_capacity=fatigue_capacity,
            )
        )

    return operators


def build_robots(config: Dict, scenario_seed: int) -> List[Robot]:
    rng = random.Random(scenario_seed + 1000)
    robots = []

    for robot_id in range(1, 3):
        base_speed = rng.uniform(0.85, 1.15)
        energy_capacity_kj = rng.uniform(900.0, 1100.0)

        robots.append(
            Robot(
                robot_id=robot_id,
                name=f"Robot-{robot_id}",
                base_speed=base_speed,
                energy_capacity_kj=energy_capacity_kj,
            )
        )

    return robots


def build_scenario(
    config: Dict,
    scenario_seed: int,
    scenario_id: int,
    disturbance_events: List[Dict],
) -> Scenario:
    tasks = load_tasks(config)
    operators = build_operators(config, scenario_seed)
    robots = build_robots(config, scenario_seed)

    return Scenario(
        scenario_id=scenario_id,
        shift_duration_s=float(config["shift_duration_s"]),
        tasks=tasks,
        jobs=build_backlog([task.task_id for task in tasks], config['job_quantities']),
        operators=operators,
        robots=robots,
        disturbance_events=disturbance_events,
    )