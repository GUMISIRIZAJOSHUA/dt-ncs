import os
import pandas as pd

root = r"results\stage_a_full_20261125_145934_824098"
sm = pd.read_csv(os.path.join(root, "shift_metrics.csv"))
pc = pd.read_csv(os.path.join(root, "paired_comparisons.csv"))

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 50)
pd.set_option("display.max_rows", 200)

print("ARMS:", sm["arm"].value_counts().to_dict())

metrics = ["completed_tasks", "throughput_tasks_per_hour", "total_energy_kj",
           "energy_per_task_kj", "final_fatigue", "final_ergonomic_risk",
           "safety_violations", "veto_events", "well_being_score", "overall_score"]
print("\nMEAN (SD) BY ARM")
g = sm.groupby("arm")[metrics].agg(["mean", "std"]).round(3)
print(g.T.to_string())

print("\nTERMINATION REASONS")
print(sm.groupby(["arm", "termination_reason"]).size().to_string())

print("\nPAIRED COMPARISONS")
print(pc.round(4).to_string(index=False))