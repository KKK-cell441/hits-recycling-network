from pathlib import Path
import json
import math
import random
import numpy as np
import pandas as pd
import networkx as nx
from scipy.stats import spearmanr

BASE = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/HITS_materials")
OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/ablation_permutation")
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
    for ch in ["\u00b7", "\uff08", "\uff09", "(", ")", " ", "-", "_"]:
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

s_degree = {s: 0 for s in stores}
b_degree = {b: 0 for b in brand_models}
for bi, si, _ in edges:
    b_degree[brand_models[bi]] += 1
    s_degree[stores[si]] += 1

max_q = max(q_dict.values())


def make_weighted_edges(edge_list):
    out = []
    for bi, si, _ in edge_list:
        bm = brand_models[bi]
        sid = stores[si]
        q = q_dict[bm]
        qn = float(np.log1p(q) / np.log1p(max_q))
        out.append((bi, si, qn / max(b_degree[bm], 1) / max(s_degree[sid], 1)))
    return out


def run_hits(weighted_edges, nb, ns, max_iter=150, tol=1e-10):
    a = np.ones(nb)
    h = np.ones(ns)
    for _ in range(max_iter):
        a_new = np.zeros(nb)
        h_new = np.zeros(ns)
        for bi, si, w in weighted_edges:
            a_new[bi] += h[si] * w
            h_new[si] += a[bi] * w
        na = np.linalg.norm(a_new)
        nh = np.linalg.norm(h_new)
        a_new = a_new / na if na > 0 else a_new
        h_new = h_new / nh if nh > 0 else h_new
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


def component_hits(edge_list, supply_map=None):
    if supply_map is None:
        supply_map = q_dict
    dsu = DSU(nb + ns)
    for bi, si, _ in edge_list:
        dsu.union(bi, nb + si)
    comp_map = {}
    for i in range(nb + ns):
        root = dsu.find(i)
        comp_map.setdefault(root, []).append(i)
    hub = np.zeros(ns)
    comp_volume = {}
    for root, nodes in comp_map.items():
        brand_nodes = {n for n in nodes if n < nb}
        store_nodes = {n - nb for n in nodes if n >= nb}
        if not brand_nodes or not store_nodes:
            continue
        comp_edges = [(bi, si, w) for bi, si, w in edge_list if bi in brand_nodes and si in store_nodes]
        if not comp_edges:
            continue
        vol = sum(supply_map[brand_models[bi]] for bi, _, _ in comp_edges)
        a, h = run_hits(comp_edges, nb, ns)
        for bi, si, _ in comp_edges:
            hub[si] = h[si]
            comp_volume[si] = vol
    return hub, comp_volume


def target_scores():
    target = {}
    for sid in stores:
        val = 0.0
        for bm in brand_models:
            if (bm, sid) in {(brand_models[bi], stores[si]) for bi, si, _ in edges}:
                val += q_dict[bm] / max(b_degree[bm], 1)
        target[sid] = np.log1p(val)
    return np.array([target[s] for s in stores])


target_arr = target_scores()
weighted_edges = make_weighted_edges(edges)
hub, comp_volume = component_hits(weighted_edges)
log_comp = np.array([np.log1p(comp_volume.get(si, 0)) for si in range(ns)])
hub_global = hub * log_comp
degree_arr = np.array([s_degree[s] for s in stores], dtype=float)
brand_volume_arr = np.array([sum(q_dict[brand_models[bi]] / max(b_degree[brand_models[bi]], 1) for bi, si, _ in edges if si == idx) for idx in range(ns)])


def rho(a, b):
    r, _ = spearmanr(a, b)
    return float(r)


# Unweighted HITS variants.
unweighted_edges = [(bi, si, 1.0) for bi, si, _ in edges]
hub_un, comp_volume_un = component_hits(unweighted_edges)
log_comp_un = np.array([np.log1p(comp_volume_un.get(si, 0)) for si in range(ns)])
hub_un_global = hub_un * log_comp_un

ablation = {
    "Weighted HITS + component adjustment": rho(hub_global, target_arr),
    "Weighted HITS without component adjustment": rho(hub, target_arr),
    "Unweighted HITS + component adjustment": rho(hub_un_global, target_arr),
    "Unweighted HITS without component adjustment": rho(hub_un, target_arr),
    "Degree centrality": rho(degree_arr, target_arr),
    "Equal-share brand volume": rho(brand_volume_arr, target_arr),
}
ablation_df = pd.DataFrame([{"variant": k, "spearman_rho": round(v, 4)} for k, v in ablation.items()])
ablation_df.to_csv(OUT / "ablation_table.csv", index=False)

# Permutation nulls.
rng = random.Random(2026)
obs_rho = rho(hub_global, target_arr)
n_target = 1000
n_volume = 1000
n_rewire = 500
null_target = []
null_volume = []
null_rewire = []

for _ in range(n_target):
    shuffled = target_arr.copy()
    rng.shuffle(shuffled)
    null_target.append(rho(hub_global, shuffled))

for _ in range(n_volume):
    perm_vol = dict(zip(brand_models, rng.sample(list(q_dict.values()), len(brand_models))))
    h_perm, comp_perm = component_hits(weighted_edges, perm_vol)
    log_perm = np.array([np.log1p(comp_perm.get(si, 0)) for si in range(ns)])
    null_volume.append(rho(h_perm * log_perm, target_arr))

# Degree-preserving bipartite edge rewiring.
G = nx.Graph()
G.add_nodes_from([("B", bi) for bi in range(nb)], bipartite=0)
G.add_nodes_from([("S", si) for si in range(ns)], bipartite=1)
for bi, si, _ in edges:
    G.add_edge(("B", bi), ("S", si))
for _ in range(n_rewire):
    G2 = G.copy()
    nx.double_edge_swap(G2, nswap=max(100, len(edges) * 2), max_tries=5000, seed=random.Random(1000 + _))
    edge_list2 = []
    for b, s in G2.edges():
        if b[0] == "B" and s[0] == "S":
            edge_list2.append((int(b[1]), int(s[1]), 1.0))
        elif b[0] == "S" and s[0] == "B":
            edge_list2.append((int(s[1]), int(b[1]), 1.0))
    if not edge_list2:
        null_rewire.append(0.0)
        continue
    hub_r, comp_r = component_hits(edge_list2)
    log_r = np.array([np.log1p(comp_r.get(si, 0)) for si in range(ns)])
    null_rewire.append(rho(hub_r * log_r, target_arr))

nulls = {
    "target_permutation": np.array(null_target),
    "volume_permutation": np.array(null_volume),
    "edge_rewiring": np.array(null_rewire),
}
rows = []
for name, null in nulls.items():
    p_raw = float((np.abs(null) >= abs(obs_rho)).mean())
    z = float((obs_rho - null.mean()) / (null.std(ddof=1) if null.std(ddof=1) > 0 else 1e-12))
    rows.append({
        "test": name,
        "n_permutations": len(null),
        "observed_rho": round(obs_rho, 4),
        "null_mean": round(float(null.mean()), 4),
        "null_sd": round(float(null.std(ddof=1)), 4),
        "raw_p_value": p_raw,
        "z_score": round(z, 3),
    })
perm_df = pd.DataFrame(rows)
# Holm correction over the three permutation tests.
pvals = perm_df["raw_p_value"].to_numpy()
order = np.argsort(pvals)
m = len(pvals)
holm = np.ones_like(pvals)
prev = 0.0
for rank, idx in enumerate(order):
    holm[idx] = max(prev, (m - rank) * pvals[idx])
    prev = holm[idx]
perm_df["holm_adjusted_p"] = holm
perm_df.to_csv(OUT / "permutation_tests.csv", index=False)

summary = {
    "ablation": ablation,
    "observed_rho": round(obs_rho, 4),
    "permutation_tests": perm_df.to_dict(orient="records"),
}
with open(OUT / "ablation_permutation_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(json.dumps(summary, ensure_ascii=False, indent=2))
prev = 0.0
