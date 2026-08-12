from pathlib import Path
import numpy as np
import pandas as pd
import networkx as nx
from scipy.stats import spearmanr
from scipy.optimize import minimize
import json

BASE = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/HITS_materials")
OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/algorithm_comparison")
OUT.mkdir(parents=True, exist_ok=True)

qd = pd.read_excel(BASE / "qd4s.xlsx")
ret = pd.read_excel(BASE / "retired_batteries_per_model.xlsx")
store_id_col = qd.columns[0]
brand_cols = [qd.columns[i] for i in range(5, 8)]
ret_brand = ret.columns[0]
ret_model = ret.columns[1]
ret_time = ret.columns[2]
ret_qty = ret.columns[3]


def norm_brand(s):
    s = str(s).strip().lower()
    for ch in ["·", "·", "（", "）", "(", ")", " ", "-", "_"]:
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
bm_brand = {bm: bm.split("_", 1)[0] for bm in brand_models}
bm_volume = q_by_bm.to_dict()

# Monthly series per brand-model.
monthly = ret.groupby(["brand_model", ret_time])[ret_qty].sum().unstack(fill_value=0)
monthly = monthly.reindex(columns=sorted(monthly.columns, key=str)).fillna(0)

stores = list(store_brands.keys())
s_index = {s: i for i, s in enumerate(stores)}

# Edges and store degree.
edges = []
for bm in brand_models:
    nbrand = norm_brand(bm_brand[bm])
    for sid, nbs in store_norm.items():
        if any(nbrand in nb or nb in nbrand for nb in nbs):
            edges.append((bm, sid))

s_degree = {s: 0 for s in stores}
b_degree = {b: 0 for b in brand_models}
for b, s in edges:
    b_degree[b] += 1
    s_degree[s] += 1

# Store brand-model sets.
store_bm = {s: set() for s in stores}
for b, s in edges:
    store_bm[s].add(b)

# Store equal-share target and monthly sequence.
store_target = {}
store_seq = np.zeros((len(stores), monthly.shape[1]))
max_q = max(bm_volume.values())
for b in brand_models:
    sb = max(b_degree[b], 1)
    for s in edges:
        pass
for s_idx, sid in enumerate(stores):
    target = 0.0
    for b in store_bm[sid]:
        target += bm_volume[b] / max(b_degree[b], 1)
        store_seq[s_idx] += monthly.loc[b].values / max(b_degree[b], 1)
    store_target[sid] = np.log1p(target)

# Graph objects.
G = nx.Graph()
G.add_nodes_from(brand_models, bipartite="brand")
G.add_nodes_from(stores, bipartite="store")
for b, s in edges:
    G.add_edge(b, s)

# Store-level co-occurrence adjacency for GNNs.
A = np.zeros((len(stores), len(stores)))
for i, si in enumerate(stores):
    for j in range(i + 1, len(stores)):
        shared = store_bm[si] & store_bm[stores[j]]
        if shared:
            A[i, j] = len(shared)
            A[j, i] = len(shared)
np.fill_diagonal(A, 1)
D = np.diag(np.asarray(A.sum(axis=1)).ravel() ** -0.5)
A_hat = D @ A @ D

# Node features for GCN/GAT.
feat_raw = np.column_stack([
    [s_degree[s] for s in stores],
    [len(store_bm[s]) for s in stores],
    [float(qd[qd[store_id_col] == int(s)]["lon"].iloc[0]) if qd[qd[store_id_col] == int(s)].shape[0] else 0 for s in stores],
    [float(qd[qd[store_id_col] == int(s)]["lan"].iloc[0]) if qd[qd[store_id_col] == int(s)].shape[0] else 0 for s in stores],
])
X = (feat_raw - feat_raw.mean(axis=0)) / (feat_raw.std(axis=0) + 1e-8)
T = len(monthly.columns)
X_seq = (store_seq - store_seq.mean(axis=0)) / (store_seq.std(axis=0) + 1e-8)
y = np.array([store_target[s] for s in stores])


def spearman(a, b):
    rho, _ = spearmanr(a, b)
    return rho


def gcn_predict(params, A_hat, X):
    d = X.shape[1]
    h = 8
    W1 = params[:d * h].reshape(d, h)
    b1 = params[d * h:d * h + h]
    W2 = params[d * h + h:d * h + h + h].reshape(h, 1)
    b2 = params[-1]
    H = A_hat @ X @ W1 + b1
    H = np.maximum(0, H)
    return (A_hat @ H) @ W2 + b2


def gat_predict(params, A, X):
    d = X.shape[1]
    h = 8
    W = params[:d * h].reshape(d, h)
    a1 = params[d * h:d * h + h]
    a2 = params[d * h + h:d * h + 2 * h]
    W2 = params[d * h + 2 * h:d * h + 2 * h + h].reshape(h, 1)
    b2 = params[-1]
    H = X @ W
    e = np.maximum(0, H[:, None, :] @ a1 + H[None, :, :] @ a2)
    mask = A > 0
    e[~mask] = -np.inf
    e = e - e.max(axis=1, keepdims=True)
    alpha = np.exp(e)
    alpha[~mask] = 0
    alpha /= alpha.sum(axis=1, keepdims=True)
    Z = alpha @ H
    return Z @ W2 + b2


def tcn_predict(params, X_seq):
    k0, k1, k2, b, w, b2 = params
    out = np.zeros_like(X_seq)
    T = X_seq.shape[1]
    out[:, 0] = k0 * X_seq[:, 0] + b
    out[:, 1] = k0 * X_seq[:, 1] + k1 * X_seq[:, 0] + b
    for t in range(2, T):
        out[:, t] = k0 * X_seq[:, t] + k1 * X_seq[:, t - 1] + k2 * X_seq[:, t - 2] + b
    out = np.maximum(0, out)
    return np.mean(out, axis=1) * w + b2


def fit_model(predict, init, train_idx, A=None, X=None, X_seq=None):
    def loss(p):
        if A is not None:
            pred = predict(p, A, X)
        elif X_seq is not None:
            pred = predict(p, X_seq)
        else:
            pred = predict(p, A_hat, X)
        return np.mean((pred[train_idx] - y[train_idx]) ** 2)

    res = minimize(loss, init, method="L-BFGS-B", options={"maxiter": 200})
    return res.x


# Classical scores.
degree_score = np.array([G.degree(s) for s in stores], dtype=float)
betweenness = nx.betweenness_centrality(G)
bet_score = np.array([betweenness[s] for s in stores], dtype=float)
pagerank = nx.pagerank(G, weight=None)
pr_score = np.array([pagerank[s] for s in stores], dtype=float)
store_res = pd.read_csv(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/hits_results/store_results.csv")
hub_map = dict(zip(store_res["store_id"].astype(str), store_res["hub_global"]))
hit_score = np.array([hub_map.get(s, 0.0) for s in stores], dtype=float)

# Repeated split comparison.
rng = np.random.default_rng(2026)
rows = []
for seed in range(5):
    idx = np.arange(len(stores))
    rng.shuffle(idx)
    train_idx = idx[:int(len(idx) * 0.7)]
    test_idx = idx[int(len(idx) * 0.7):]
    d = len(X[0]); h = 8
    gcn_init = np.concatenate([np.random.default_rng(seed).normal(0, 0.1, d * h + h), np.random.default_rng(seed + 1).normal(0, 0.1, h), [0.0]])
    gat_init = np.concatenate([np.random.default_rng(seed + 2).normal(0, 0.1, d * h + 2 * h), np.random.default_rng(seed + 3).normal(0, 0.1, h), [0.0]])
    tcn_init = np.array([0.5, 0.3, 0.2, 0.0, 1.0, 0.0])
    gcn_params = fit_model(gcn_predict, gcn_init, train_idx, A=A_hat, X=X)
    gat_params = fit_model(gat_predict, gat_init, train_idx, A=A, X=X)
    tcn_params = fit_model(tcn_predict, tcn_init, train_idx, X_seq=X_seq)

    scores = {
        "Degree": degree_score,
        "Betweenness": bet_score,
        "PageRank": pr_score,
        "HITS": hit_score,
        "GCN": gcn_predict(gcn_params, A_hat, X).ravel(),
        "GAT": gat_predict(gat_params, A, X).ravel(),
        "TCN": tcn_predict(tcn_params, X_seq).ravel(),
    }
    row = {"seed": seed}
    for name, score in scores.items():
        row[name] = round(float(spearman(score[test_idx], y[test_idx])), 4)
    rows.append(row)
    print(seed, row)

res_df = pd.DataFrame(rows)
summary = {}
for col in ["Degree", "Betweenness", "PageRank", "HITS", "GCN", "GAT", "TCN"]:
    summary[col] = {
        "mean_rho": round(float(res_df[col].mean()), 4),
        "std_rho": round(float(res_df[col].std()), 4),
    }
res_df.to_csv(OUT / "algorithm_comparison_seeds.csv", index=False)
with open(OUT / "algorithm_comparison_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print("summary", summary)
