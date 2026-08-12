from pathlib import Path
import pandas as pd

BASE = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/HITS_materials")
RES = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/hits_results")
OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/store_type_analysis")
OUT.mkdir(parents=True, exist_ok=True)

qd = pd.read_excel(BASE / "qd4s.xlsx")
ret = pd.read_excel(BASE / "retired_batteries_per_model.xlsx")
stores = pd.read_csv(RES / "store_results.csv")

store_id_col = qd.columns[0]
brand_cols = [qd.columns[i] for i in range(5, 8)]
ev_brands = set(str(b).strip() for b in ret[ret.columns[0]].dropna())


def norm(s):
    s = str(s).strip().lower()
    for ch in ["\u00b7", "\uff08", "\uff09", "(", ")", " ", "-", "_"]:
        s = s.replace(ch, "")
    return s


ev_norm = {norm(b) for b in ev_brands}
rows = []
for _, r in qd.iterrows():
    sid = str(r[store_id_col])
    brands = []
    for c in brand_cols:
        if pd.notna(r[c]):
            b = str(r[c]).strip()
            if b and b.lower() != "nan":
                brands.append(b)
    nb = norm(b)
    has_ev = any(ev in nb or nb in ev for ev in ev_norm for b in brands)
    rows.append({"store_id": sid, "store_brands": "|".join(brands), "new_energy_related": has_ev})

type_df = pd.DataFrame(rows)
type_df["store_id"] = type_df["store_id"].astype(str)
stores["store_id"] = stores["store_id"].astype(str)
merged = stores.merge(type_df, on="store_id", how="left")
merged["new_energy_related"] = merged["new_energy_related"].fillna(False)

summary = {
    "total_stores": int(len(merged)),
    "new_energy_related": int(merged["new_energy_related"].sum()),
    "fuel_only": int((~merged["new_energy_related"]).sum()),
    "connected_total": int((merged["degree"] > 0).sum()),
    "connected_new_energy": int(((merged["degree"] > 0) & merged["new_energy_related"]).sum()),
    "connected_fuel_only": int(((merged["degree"] > 0) & ~merged["new_energy_related"]).sum()),
    "new_energy_share_of_hub_top20": float(merged.sort_values("hub_global", ascending=False).head(20)["new_energy_related"].mean()),
    "new_energy_mean_hub": float(merged.loc[merged["new_energy_related"], "hub_global"].mean()),
    "fuel_only_mean_hub": float(merged.loc[~merged["new_energy_related"], "hub_global"].mean()),
    "new_energy_mean_volume": float(merged.loc[merged["new_energy_related"], "brand_volume"].mean()),
    "fuel_only_mean_volume": float(merged.loc[~merged["new_energy_related"], "brand_volume"].mean()),
}
merged.to_csv(OUT / "store_type_analysis.csv", index=False)
pd.DataFrame([summary]).to_csv(OUT / "store_type_summary.csv", index=False)
import json
with open(OUT / "store_type_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(summary)
