from pathlib import Path

import pandas as pd

p = Path("exports/export-2025-12-20/meta/master_documents_index.csv")
df = pd.read_csv(p, dtype=str).fillna("")
missing = df[(df["file_source"] == "File") & (df["local_path"] == "")]
print("remaining missing:", len(missing))
