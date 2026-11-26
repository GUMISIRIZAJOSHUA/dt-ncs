from pathlib import Path


scenario_path = Path("src/scenario.py")
scheduler_path = Path("src/scheduler.py")

scenario_text = scenario_path.read_text(encoding="utf-8")
scheduler_text = scheduler_path.read_text(encoding="utf-8")

scenario_old = (
    "    disturbance_events: List[Dict] = field(default_factory=list)\n"
)

scenario_new = (
    "    disturbance_events: List[Dict] = field(default_factory=list)\n"
    "    completed_task_ids: set = field(default_factory=set)\n"
)

if scenario_old not in scenario_text:
    raise RuntimeError("Could not find the Scenario field insertion point.")

if "completed_task_ids" in scenario_text:
    print("Scenario already contains completed_task_ids; skipping.")
else:
    scenario_text = scenario_text.replace(scenario_old, scenario_new)
    scenario_path.write_text(scenario_text, encoding="utf-8")
    print("Added completed_task_ids to Scenario.")

scheduler_old = (
    "    for task in scenario.tasks:\n"
    "        for operator in scenario.operators:\n"
)

scheduler_new = (
    "    for task in scenario.tasks:\n"
    "        if task.task_id in scenario.completed_task_ids:\n"
    "            continue\n"
    "        for operator in scenario.operators:\n"
)

if scheduler_old not in scheduler_text:
    raise RuntimeError(
        "Could not find the task-selection loop insertion point."
    )

if "if task.task_id in scenario.completed_task_ids:" in scheduler_text:
    print("Scheduler already excludes completed tasks; skipping.")
else:
    scheduler_text = scheduler_text.replace(scheduler_old, scheduler_new)
    print("Added completed-task exclusion to select_assignment().")

execution_old = (
    "    robot.completed_tasks.append(task.task_id)\n"
)

execution_new = (
    "    robot.completed_tasks.append(task.task_id)\n"
    "    scenario.completed_task_ids.add(task.task_id)\n"
)

if execution_old not in scheduler_text:
    raise RuntimeError(
        "Could not find the task-completion registration point."
    )

if "scenario.completed_task_ids.add(task.task_id)" not in scheduler_text:
    scheduler_text = scheduler_text.replace(
        execution_old,
        execution_new,
    )
    print("Added completed-task registration to execute_assignment().")

scheduler_path.write_text(scheduler_text, encoding="utf-8")

print("Completed-task tracking patch applied successfully.")