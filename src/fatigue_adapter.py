from src.fatigue_kernel import advance_recovery, advance_work
from src.fatigue_feasibility import find_work_feasible_rest_delay
from src.fatigue_parameters import bind_fatigue_parameters

class FatigueAdapter:
    def __init__(self, raw, *, operator_ids, task_ids):
        self.parameters = bind_fatigue_parameters(raw, operator_ids=operator_ids, task_ids=task_ids)

    def initialize(self, operators):
        operators = list(operators)
        ids = [o.operator_id for o in operators]
        if len(ids) != len(set(ids)) or set(ids) != set(self.parameters.operators):
            raise ValueError("Initialization requires exact operator coverage")
        for o in operators:
            o.fatigue_level = self.parameters.operators[o.operator_id].initial_fatigue

    def _work_parameters(self, operator_id, task_id):
        p = self.parameters.operators[operator_id]
        return dict(alpha_per_s=p.alpha_per_s, beta=p.beta, demand=self.parameters.task_demands[task_id], step_size_s=self.parameters.step_size_s)

    def project_work(self, operator, task_id, duration_s):
        return advance_work(operator.fatigue_level, duration_s, **self._work_parameters(operator.operator_id, task_id))

    def is_work_feasible(self, operator, task_id, duration_s):
        projection = self.project_work(operator, task_id, duration_s)
        return projection.maximum_fatigue <= self.parameters.operators[operator.operator_id].fatigue_limit

    def apply_work(self, operator, task_id, duration_s):
        projection = self.project_work(operator, task_id, duration_s)
        operator.fatigue_level = projection.final_fatigue
        return projection

    def apply_recovery(self, operator, duration_s):
        p = self.parameters.operators[operator.operator_id]
        final = advance_recovery(operator.fatigue_level, duration_s, rho_per_s=p.rho_per_s)
        operator.fatigue_level = final
        return final

    def find_rest_delay(self, operator, task_id, duration_s, max_delay_s):
        p = self.parameters.operators[operator.operator_id]
        return find_work_feasible_rest_delay(operator.fatigue_level, duration_s, fatigue_limit=p.fatigue_limit, rho_per_s=p.rho_per_s, max_delay_s=max_delay_s, **self._work_parameters(operator.operator_id, task_id))
