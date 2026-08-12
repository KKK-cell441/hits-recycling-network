from pathlib import Path
import numpy as np
import pandas as pd
import json

BASE = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/HITS_materials")
AMAP = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/amap_western")
OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/western_extension")
OUT.mkdir(parents=True, exist_ok=True)

poi_df = pd.read_csv(AMAP / "amap_4s_western_2026.csv")
ret = pd.read_excel(BASE / "retired_batteries_per_model.xlsx")

ret["brand_model"] = ret[ret.columns[0]].astype(str) + "_" + ret[ret.columns[1]].astype(str)
q_by_bm = ret.groupby("brand_model")[ret.columns[3]].sum()
q_by_bm = q_by_bm[q_by_bm > 0]

ret_brands = sorted({str(b).strip() for b in ret[ret.columns[0]].dropna()})


def norm(s):
    s = str(s).strip().lower()
    for ch in ["·", "·", "（", "）", "(", ")", " ", "-", "_"]:
        s = s.replace(ch, "")
    return s


ret_norm = {norm(b): b for b in ret_brands}


def match_brands(text):
    if not text or text.lower() == "nan":
        return set()
    nt = norm(text)
    hits = set()
    for nb, b in ret_norm.items():
        if nb and (nb in nt or nt in nb):
            hits.add(b)
    return hits


poi_df["matched_brands"] = poi_df.apply(
    lambda r: match_brands(str(r["name"])) | match_brands(str(r["type"])), axis=1
)

brand_models = list(q_by_bm.index)
bm_brand = {bm: bm.split("_", 1)[0] for bm in brand_models}
bm_volume = q_by_bm.to_dict()
total_volume = float(q_by_bm.sum())

summary = []
city_rows = []
for city in sorted(poi_df["city"].unique()):
    cdf = poi_df[poi_df["city"] == city].reset_index(drop=True)
    matched = cdf[cdf["matched_brands"].apply(len) > 0]
    edges = []
    for idx, row in matched.iterrows():
        for bm in brand_models:
            if bm_brand[bm] in row["matched_brands"]:
                edges.append((bm, str(row["poi_id"])))

    connected_bm = set(b for b, _ in edges)
    connected_volume = sum(bm_volume[b] for b in connected_bm)
    coverage = connected_volume / total_volume if total_volume else 0

    # Weighted HITS per city using the same log-scaled supply weight.
    stores = sorted(set(s for _, s in edges))
    store_index = {s: i for i, s in enumerate(stores)}
    b_index = {b: i for i, b in enumerate(brand_models)}
    nb = len(brand_models)
    ns = len(stores)
    b_deg = {b: 0 for b in brand_models}
    s_deg = {s: 0 for s in stores}
    for b, s in edges:
        b_deg[b] += 1
        s_deg[s] += 1
    w_edges = []
    max_q = max(bm_volume.values())
    for b, s in edges:
        qn = float(np.log1p(bm_volume[b]) / np.log1p(max_q))
        w = qn / max(b_deg[b], 1) / max(s_deg[s], 1)
        w_edges.append((b_index[b], store_index[s], w))

    auth = np.ones(nb)
    hub = np.ones(ns)
    for _ in range(500):
        na = np.zeros(nb)
        nh = np.zeros(ns)
        for bi, si, w in w_edges:
            na[bi] += hub[si] * w
            nh[si] += auth[bi] * w
        na = na / np.linalg.norm(na) if np.linalg.norm(na) else na
        nh = nh / np.linalg.norm(nh) if np.linalg.norm(nh) else nh
        if np.max(np.abs(na - auth)) < 1e-10 and np.max(np.abs(nh - hub)) < 1e-10:
            auth, hub = na, nh
            break
        auth, hub = na, nh

    top_stores = sorted(zip(stores, hub), key=lambda x: -x[1])[:10]
    summary.append({
        "city": city,
        "poi_count": int(len(cdf)),
        "matched_poi_count": int(len(matched)),
        "connected_brand_models": len(connected_bm),
        "edges": len(edges),
        "connected_volume": round(connected_volume, 2),
        "coverage_ratio": round(coverage, 4),
    })
    for store, h in top_stores:
        row = cdf[cdf["poi_id"] == store].iloc[0]
        city_rows.append({
            "city": city,
            "store_id": store,
            "store_name": row["name"],
            "hub_score": float(h),
            "matched_brands": "|".join(sorted(row["matched_brands"])),
        })
    print(city, "POIs", len(cdf), "matched", len(matched), "edges", len(edges), "coverage", round(coverage, 4))

summary_df = pd.DataFrame(summary)
top_df = pd.DataFrame(city_rows)
summary_df.to_csv(OUT / "western_city_summary.csv", index=False)
top_df.to_csv(OUT / "western_top_stores.csv", index=False)

with open(OUT / "western_summary.json", "w", encoding="utf-8") as f:
    json.dump({
        "total_pois": int(len(poi_df)),
        "total_matched": int(summary_df["matched_poi_count"].sum()),
        "total_retired_volume": total_volume,
        "cities": summary_df.to_dict(orient="records"),
    }, f, ensure_ascii=False, indent=2)

print("total POIs", len(poi_df), "matched", summary_df["matched_poi_count"].sum())
print(summary_df.to_string(index=False))
