from pathlib import Path
import json
import math
import random
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

BASE = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/HITS_materials")
OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/hits_results")
OUT.mkdir(parents=True, exist_ok=True)

qd = pd.read_excel(BASE / "qd4s.xlsx")
ret = pd.read_excel(BASE / "retired_batteries_per_model.xlsx")

store_id_col = qd.columns[0]
brand_cols = [qd.columns[i] for i in range(5, 8)]
ret_brand_col = ret.columns[0]
ret_model_col = ret.columns[1]
qty_col = ret.columns[3]

ret["brand_model"] = ret[ret_brand_col].astype(str) + "_" + ret[ret_model_col].astype(str)
ret["brand_model"] = ret["brand_model"].str.replace("_nan", "", regex=False)
q_by_bm = ret.groupby("brand_model", as_index=False)[qty_col].sum()
q_by_bm = q_by_bm[q_by_bm[qty_col] > 0].sort_values(qty_col, ascending=False).reset_index(drop=True)
q_dict = dict(zip(q_by_bm["brand_model"], q_by_bm[qty_col]))


def norm_brand(s):
    s = str(s).strip().lower()
    for ch in ["·", "·", "（", "）", "(", ")", " ", "-", "_"]:
        s = s.replace(ch, "")
    return s


store_brand_sets = {}
for _, row in qd.iterrows():
    sid = str(row[store_id_col])
    brands = set()
    for c in brand_cols:
        v = row[c]
        if pd.isna(v):
            continue
        s = str(v).strip()
        if s and s.lower() != "nan":
            brands.add(s)
    store_brand_sets[sid] = brands

store_norm = {sid: {norm_brand(b) for b in bs} for sid, bs in store_brand_sets.items()}

brand_models = list(q_dict.keys())
stores = list(store_brand_sets.keys())
nb, ns = len(brand_models), len(stores)

edges = []
for bi, bm in enumerate(brand_models):
    brand = bm.split("_", 1)[0]
    nbrand = norm_brand(brand)
    for si, sid in enumerate(stores):
        if any(nbrand in sb or sb in nbrand for sb in store_norm[sid]):
            edges.append((bi, si, 1.0))


def haversine(lon1, lat1, lon2, lat2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


coords = {str(r[store_id_col]): (float(r["lon"]), float(r["lan"])) for _, r in qd.iterrows()}

s_degree = {s: 0 for s in stores}
b_degree = {b: 0 for b in brand_models}
for bi, si, _ in edges:
    b_degree[brand_models[bi]] += 1
    s_degree[stores[si]] += 1


def make_weighted_edges(edge_list):
    out = []
    for bi, si, _ in edge_list:
        bm = brand_models[bi]
        sid = stores[si]
        q = q_dict[bm]
        sb = max(b_degree[bm], 1)
        bs = max(s_degree[sid], 1)
        qn = float(np.log1p(q) / np.log1p(max(q_dict.values())))
        out.append((bi, si, (qn / sb) * (1.0 / bs)))
    return out


def run_hits(weighted_edges, nb, ns, max_iter=1000, tol=1e-12):
    a = np.ones(nb)
    h = np.ones(ns)
    for _ in range(max_iter):
        a_new = np.zeros(nb)
        h_new = np.zeros(ns)
        for bi, si, w in weighted_edges:
            a_new[bi] += h[si] * w
            h_new[si] += a[bi] * w
        a_norm = np.linalg.norm(a_new)
        h_norm = np.linalg.norm(h_new)
        a_new = a_new / a_norm if a_norm > 0 else a_new
        h_new = h_new / h_norm if h_norm > 0 else h_new
        if np.max(np.abs(a_new - a)) < tol and np.max(np.abs(h_new - h)) < tol:
            a, h = a_new, h_new
            break
        a, h = a_new, h_new
    return a, h


class DSU:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def component_hits(edge_list):
    dsu = DSU(nb + ns)
    for bi, si, _ in edge_list:
        dsu.union(bi, nb + si)
    comp_map = {}
    for i in range(nb + ns):
        root = dsu.find(i)
        comp_map.setdefault(root, []).append(i)
    hub = np.zeros(ns)
    auth = np.zeros(nb)
    comp_volume = {}
    comp_store_count = {}
    for root, nodes in comp_map.items():
        # only connected components with at least one edge
        comp_edges = []
        brand_nodes = {n for n in nodes if n < nb}
        store_nodes = {n - nb for n in nodes if n >= nb}
        if not brand_nodes or not store_nodes:
            continue
        for bi, si, _ in edge_list:
            if bi in brand_nodes and si in store_nodes:
                comp_edges.append((bi, si, _))
        if not comp_edges:
            continue
        vol = sum(q_dict[brand_models[bi]] for bi, _, _ in comp_edges)
        a, h = run_hits(comp_edges, nb, ns)
        for bi, si, _ in comp_edges:
            auth[bi] = a[bi]
            hub[si] = h[si]
            comp_volume[si] = vol
            comp_store_count[si] = len(store_nodes)
    return hub, auth, comp_volume, comp_store_count


weighted_edges = make_weighted_edges(edges)
hub, auth, comp_volume, comp_store_count = component_hits(weighted_edges)

# Component-volume adjusted global score.
log_comp_volume = {si: float(np.log1p(comp_volume.get(si, 0))) for si in range(ns)}
hub_global = np.array([hub[si] * log_comp_volume.get(si, 1.0) for si in range(ns)])

store_q = {s: 0.0 for s in stores}
for bi, si, _ in weighted_edges:
    bm = brand_models[bi]
    sid = stores[si]
    store_q[sid] += q_dict[bm] / max(b_degree[bm], 1)

store_q_hits = {s: 0.0 for s in stores}
for bi in range(nb):
    bm = brand_models[bi]
    neighbors = [si for b2, si, _ in weighted_edges if b2 == bi]
    if not neighbors:
        continue
    hsum = sum(hub[si] for si in neighbors)
    if hsum <= 0:
        continue
    for si in neighbors:
        store_q_hits[stores[si]] += q_dict[bm] * hub[si] / hsum

rows = []
for si, sid in enumerate(stores):
    rows.append({
        "store_id": sid,
        "hub": float(hub[si]),
        "hub_global": float(hub_global[si]),
        "degree": int(s_degree[sid]),
        "brand_volume": float(store_q[sid]),
        "volume_hits": float(store_q_hits[sid]),
        "component_volume": float(comp_volume.get(si, 0)),
        "component_stores": int(comp_store_count.get(si, 0)),
        "lon": coords[sid][0],
        "lat": coords[sid][1],
    })
store_df = pd.DataFrame(rows).sort_values("hub_global", ascending=False).reset_index(drop=True)

brand_rows = []
for bi, bm in enumerate(brand_models):
    brand_rows.append({
        "brand_model": bm,
        "authority": float(auth[bi]),
        "volume": float(q_dict[bm]),
        "store_degree": int(b_degree[bm]),
    })
brand_df = pd.DataFrame(brand_rows).sort_values("authority", ascending=False).reset_index(drop=True)


def spearman_cols(df, cols):
    res = {}
    for i, a in enumerate(cols):
        for b in cols[i:]:
            rho, p = spearmanr(df[a], df[b])
            res[f"{a}|{b}"] = {"rho": round(float(rho), 4), "p": float(p)}
    return res


corr_cols = ["hub_global", "hub", "degree", "brand_volume", "volume_hits"]
corr = spearman_cols(store_df, corr_cols)

mask_levels = [0.10, 0.20, 0.30, 0.40, 0.50]
robust_rows = []
for mask in mask_levels:
    rhos = []
    for seed in range(5):
        rng = random.Random(seed)
        keep = [1 if rng.random() >= mask else 0 for _ in range(len(weighted_edges))]
        masked = [e for e, k in zip(weighted_edges, keep) if k]
        if not masked:
            rhos.append(np.nan)
            continue
        h2, a2, cv2, cs2 = component_hits(masked)
        log2 = {si: float(np.log1p(cv2.get(si, 0))) for si in range(ns)}
        hg2 = np.array([h2[si] * log2.get(si, 1.0) for si in range(ns)])
        rho, _ = spearmanr(hub_global, hg2)
        rhos.append(rho)
    robust_rows.append({
        "mask": mask,
        "mean_rho": round(float(np.nanmean(rhos)), 4),
        "min_rho": round(float(np.nanmin(rhos)), 4),
        "max_rho": round(float(np.nanmax(rhos)), 4),
    })
robust_df = pd.DataFrame(robust_rows)

store_df["tier"] = pd.qcut(store_df["hub_global"].rank(method="first"), 3, labels=["T3", "T2", "T1"])
tier_summary = store_df.groupby("tier", observed=True).agg(
    n=("store_id", "count"),
    median_hub=("hub_global", "median"),
    mean_volume=("volume_hits", "mean"),
    total_volume=("volume_hits", "sum"),
).reset_index()

store_df.to_csv(OUT / "store_results.csv", index=False)
brand_df.to_csv(OUT / "brand_results.csv", index=False)
robust_df.to_csv(OUT / "robustness.csv", index=False)
tier_summary.to_csv(OUT / "tier_summary.csv", index=False)

summary = {
    "n_stores": ns,
    "n_brand_models": nb,
    "n_edges": len(weighted_edges),
    "n_connected_stores": int((store_df["degree"] > 0).sum()),
    "n_connected_brand_models": int((brand_df["store_degree"] > 0).sum()),
    "total_retired_2025_2035": float(ret[qty_col].sum()),
    "correlations": corr,
    "robustness": robust_df.to_dict(orient="records"),
    "tier_summary": tier_summary.to_dict(orient="records"),
    "top_stores": store_df.head(10).to_dict(orient="records"),
    "top_brand_models": brand_df.head(10).to_dict(orient="records"),
}
with open(OUT / "summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

print("n_stores", ns, "n_brand_models", nb, "n_edges", len(weighted_edges))
print("connected", int((store_df["degree"] > 0).sum()), int((brand_df["store_degree"] > 0).sum()))
print("corr", json.dumps(corr, ensure_ascii=False, indent=2))
print("robust", robust_df.to_string(index=False))
print("tiers", tier_summary.to_string(index=False))
print("top stores")
print(store_df.head(10).to_string(index=False))
print("top brand models")
print(brand_df.head(10).to_string(index=False))
