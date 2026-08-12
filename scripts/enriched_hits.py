from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import json

BASE = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/HITS_materials")
OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/enriched_hits")
OUT.mkdir(parents=True, exist_ok=True)

qd = pd.read_excel(BASE / "qd4s.xlsx")
ret = pd.read_excel(BASE / "retired_batteries_per_model.xlsx")
sales = pd.read_excel(BASE / "forecasted_sales_2025_2035.xlsx")

store_id_col = qd.columns[0]
brand_cols = [qd.columns[i] for i in range(5, 8)]
ret_brand = ret.columns[0]
ret_model = ret.columns[1]
ret_qty = ret.columns[3]


def norm_brand(s):
    s = str(s).strip().lower()
    for ch in ["\u00b7", "\uff08", "\uff09", "(", ")", " ", "-", "_"]:
        s = s.replace(ch, "")
    return s


store_brands = {}
for _, row in qd.iterrows():
    sid = str(row[store_id_col])
    brands = set()
    for c in brand_cols:
        if pd.notna(row[c]):
            b = str(row[c]).strip()
            if b and b.lower() != "nan":
                brands.add(b)
    store_brands[sid] = brands
store_norm = {sid: {norm_brand(b) for b in bs} for sid, bs in store_brands.items()}

ret["brand_model"] = ret[ret_brand].astype(str) + "_" + ret[ret_model].astype(str)
ret["brand_model"] = ret["brand_model"].str.replace("_nan", "", regex=False)
q_by_bm = ret.groupby("brand_model")[ret_qty].sum()
q_by_bm = q_by_bm[q_by_bm > 0]
brand_models = list(q_by_bm.index)
bm_volume = q_by_bm.to_dict()

# Forecasted annual shipment by brand-model.
sales["brand_model"] = sales[sales.columns[1]].astype(str) + "_" + sales[sales.columns[0]].astype(str)
ship_by_bm = sales.groupby("brand_model")[sales.columns[3]].sum()
ship_map = {b: float(ship_by_bm.get(b, 0)) for b in brand_models}

stores = list(store_brands.keys())
edges = []
for bm in brand_models:
    nbrand = norm_brand(bm.split("_", 1)[0])
    for sid, nbs in store_norm.items():
        if any(nbrand in nb or nb in nbrand for nb in nbs):
            edges.append((bm, sid))

b_degree = {b: 0 for b in brand_models}
s_degree = {s: 0 for s in stores}
for b, s in edges:
    b_degree[b] += 1
    s_degree[s] += 1

store_bm = {s: set() for s in stores}
for b, s in edges:
    store_bm[s].add(b)

# Target: equal-share retirement volume.
store_target = {}
for sid in stores:
    target = 0.0
    for b in store_bm[sid]:
        target += bm_volume[b] / max(b_degree[b], 1)
    store_target[sid] = np.log1p(target)
target_arr = np.array([store_target[s] for s in stores])
store_index = {s: i for i, s in enumerate(stores)}


def component_hits_with_weight(edge_list, weight_fn):
    nb = len(brand_models)
    ns = len(stores)
    parent = list(range(nb + ns))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for b, s in edge_list:
        union(brand_models.index(b), nb + store_index[s])
    comps = {}
    for i in range(nb + ns):
        comps.setdefault(find(i), []).append(i)

    hub = np.zeros(ns)
    vol_store = {}
    for nodes in comps.values():
        bnodes = {n for n in nodes if n < nb}
        snodes = {n - nb for n in nodes if n >= nb}
        if not bnodes or not snodes:
            continue
        comp_edges = [(brand_models[bi], stores[si]) for bi in bnodes for si in snodes if (brand_models[bi], stores[si]) in edge_list]
        if not comp_edges:
            continue
        vol = sum(weight_fn(b) for b, _ in comp_edges)
        a = np.ones(nb)
        h = np.ones(ns)
        bdeg = {b: sum(1 for bb, _ in comp_edges if bb == b) for b in brand_models}
        sdeg = {s: sum(1 for _, ss in comp_edges if ss == s) for s in stores}
        w_edges = []
        max_w = max(weight_fn(b) for b, _ in comp_edges)
        for b, s in comp_edges:
            w = (weight_fn(b) / max_w) / max(bdeg[b], 1) / max(sdeg[s], 1)
            w_edges.append((brand_models.index(b), store_index[s], w))
        for _ in range(300):
            na = np.zeros(nb)
            nh = np.zeros(ns)
            for bi, si, w in w_edges:
                na[bi] += h[si] * w
                nh[si] += a[bi] * w
            na = na / np.linalg.norm(na) if np.linalg.norm(na) else na
            nh = nh / np.linalg.norm(nh) if np.linalg.norm(nh) else nh
            if np.max(np.abs(na - a)) < 1e-8 and np.max(np.abs(nh - h)) < 1e-8:
                a, h = na, nh
                break
            a, h = na, nh
        for si in snodes:
            hub[si] = h[si]
            vol_store[si] = np.log1p(vol)
    return np.array([hub[i] * vol_store.get(i, 1.0) for i in range(ns)])


max_q = max(bm_volume.values())
max_ship = max(ship_map.values()) if max(ship_map.values()) > 0 else 1.0
max_b = max(s_degree.values())

# Original weight: retirement volume only.
def orig_weight(b):
    return np.log1p(bm_volume.get(b, 0)) / np.log1p(max_q)

# Enriched weight: retirement volume x forecast shipment x store breadth factor.
def enriched_weight(b):
    q_part = np.log1p(bm_volume.get(b, 0)) / np.log1p(max_q)
    ship_part = np.log1p(ship_map.get(b, 0)) / np.log1p(max_ship)
    return q_part * ship_part

orig_score = component_hits_with_weight(edges, orig_weight)
enriched_score = component_hits_with_weight(edges, enriched_weight)

orig_rho, _ = spearmanr(orig_score, target_arr)
enriched_rho, _ = spearmanr(enriched_score, target_arr)
summary = {
    "orig_hits_rho": float(orig_rho),
    "enriched_hits_rho": float(enriched_rho),
    "n_stores": len(stores),
    "n_edges": len(edges),
    "n_brands_with_shipment": int(sum(ship_map.get(b, 0) > 0 for b in brand_models)),
}
with open(OUT / "enriched_hits_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(summary)
