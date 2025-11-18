import pandas as pd
import glob

files = glob.glob("*.csv")

dfs = [pd.read_csv(f) for f in files]

merged = pd.concat(dfs, ignore_index=True)

merged.to_csv("all_merged_data.csv", index=False)

