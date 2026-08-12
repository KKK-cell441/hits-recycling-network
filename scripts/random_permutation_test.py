from pathlib import Path
import numpy as np
import pandas as pd
import random
from scipy.stats import spearmanr
import json
import networkx as nx

BASE = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/HITS_materials")
OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/algorithm_comparison")

qd = pd.read_excel(BASE / "qd4s.xlsx")
ret = pd.read_excel(BASE / "retired_batteries_per_model.xlsx")
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
q_by_bm = ret.groupby("brand_model")[ret_qty].sum()
q_by_bm = q_by_bm[q_by_bm > 0]
brand_models = list(q_by_bm.index)
bm_brand = {bm: bm.split("_", 1)[0] for bm in brand_models}
bm_volume = q_by_bm.to_dict()

stores = list(store_brands.keys())
edges = []
for bm in brand_models:
    nbrand = norm_brand(bm_brand[bm])
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

# Target.
store_target = {}
for sid in stores:
    target = 0.0
    for b in store_bm[sid]:
        target += bm_volume[b] / max(b_degree[b], 1)
    store_target[sid] = np.log1p(target)
target_arr = np.array([store_target[s] for s in stores])
store_index = {s: i for i, s in enumerate(stores)}

def component_hits(edge_list, supply_map=None):
    if supply_map is None:
        supply_map = bm_volume
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
    vol_map = {}
    for nodes in comps.values():
        bnodes = {n for n in nodes if n < nb}
        snodes = {n - nb for n in nodes if n >= nb}
        if not bnodes or not snodes:
            continue
        comp_edges = [(brand_models[bi], stores[si]) for bi in bnodes for si in snodes if (brand_models[bi], stores[si]) in edge_list]
        if not comp_edges:
            continue
        vol = sum(supply_map.get(b, 0) for b, _ in comp_edges)
        a = np.ones(nb); h = np.ones(ns)
        bdeg = {b: sum(1 for bb, _ in comp_edges if bb == b) for b in brand_models}
        sdeg = {s: sum(1 for _, ss in comp_edges if ss == s) for s in stores}
        w_edges = []
        max_q = max(supply_map.values())
        for b, s in comp_edges:
            w = (np.log1p(supply_map.get(b, 0)) / np.log1p(max_q)) / max(bdeg[b],1) / max(sdeg[s],1)
            w_edges.append((brand_models.index(b), store_index[s], w))
        for _ in range(300):
            na = np.zeros(nb); nh = np.zeros(ns)
            for bi, si, w in w_edges:
                na[bi] += h[si] * w
                nh[si] += a[bi] * w
            na = na / np.linalg.norm(na) if np.linalg.norm(na) else na
            nh = nh / np.linalg.norm(nh) if np.linalg.norm(nh) else nh
            if np.max(np.abs(na-a)) < 1e-8 and np.max(np.abs(nh-h)) < 1e-8:
                a, h = na, nh
                break
            a, h = na, nh
        for si in snodes:
            hub[si] = h[si]
            vol_map[si] = np.log1p(vol)
    hub_global = np.array([hub[i] * vol_map.get(i, 1.0) for i in range(ns)])
    return hub_global

obs = component_hits(edges)
obs_rho, _ = spearmanr(obs, target_arr)

# Raw HITS observed for edge-rewiring control.
def raw_hits_scores(edge_list):
    G = nx.Graph()
    G.add_nodes_from(brand_models)
    G.add_nodes_from(stores)
    bdeg = {b: sum(1 for bb,_ in edge_list if bb==b) for b in brand_models}
    sdeg = {s: sum(1 for _,ss in edge_list if ss==s) for s in stores}
    max_q = max(bm_volume.values())
    for b,s in edge_list:
        w = (np.log1p(bm_volume[b]) / np.log1p(max_q)) / max(bdeg[b],1) / max(sdeg[s],1)
        G.add_edge(b,s,weight=w)
    hubs, _ = nx.hits(G, max_iter=1000, tol=1e-10)
    return np.array([hubs[s] for s in stores], dtype=float)

rng = random.Random(2026)
null = []
null_target = []
for trial in range(200):
    # Target permutation control.
    shuffled_target = target_arr.copy()
    rng.shuffle(shuffled_target)
    rho_t, _ = spearmanr(obs, shuffled_target)
    null_target.append(rho_t)
    # Supply-volume permutation on the fixed network.
    vol_perm = dict(zip(brand_models, rng.sample(list(bm_volume.values()), len(brand_models))))
    h_perm = component_hits(edges, vol_perm)
    rho_e, _ = spearmanr(h_perm, target_arr)
    null.append(rho_e)
null = np.array(null)
null_target = np.array(null_target)
p_edge = float((np.abs(null) >= abs(obs_rho)).mean())
p_target = float((np.abs(null_target) >= abs(obs_rho)).mean())
summary = {
    "observed_rho": float(obs_rho),
    "volume_permutation_null_mean": float(null.mean()),
    "volume_permutation_null_std": float(null.std()),
    "volume_permutation_p_value": p_edge,
    "target_permutation_null_mean": float(null_target.mean()),
    "target_permutation_p_value": p_target,
    "n_permutations": 200,
}
with open(OUT / "random_permutation_test.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(summary)
