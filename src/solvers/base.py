from dataclasses import dataclass, field


@dataclass
class SolverResult:
    solver: str
    layout: str
    tasks: int
    seed: int
    objective: float
    runtime_s: float
    feasible: bool
    timeout: bool
    safety_violations: int
    veto_events: int
    completed_tasks: int
    common_objective: float
    wellbeing: float = 0.0
    productivity: float = 0.0
    assignments: dict = field(default_factory=dict)

class BaseSolver:
    def __init__(self, time_budget_s: float):
        self.time_budget_s = time_budget_s

    def solve(self, scenario, config, seed):
        raise NotImplementedError("Solver must implement solve().")