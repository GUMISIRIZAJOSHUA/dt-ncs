import pandas as pd

s = pd.read_csv(r"results\stage_a_full_20261125_145934_824098\selected_seeds.csv")
per = s.groupby("replicate")["scenario_seed"].nunique()
print("replicates:", s["replicate"].nunique())
print("replicates with more than one scenario_seed:", int((per > 1).sum()))
print("distinct scenario seeds:", s["scenario_seed"].nunique())
print("duplicate search seeds:", int(s["search_seed"].duplicated().sum()))