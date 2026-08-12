# HITS Battery Recycling Network Reproducibility Package

This package supports the manuscript:

**A Computational Decision-Support Framework for Battery Recycling Collection Networks Based on Weighted HITS**

It contains the analysis scripts, processed results, and public evidence files
used in the paper. Raw Gaode Map POI records are not redistributed because of
the Amap Open Platform Terms of Service; equivalent data can be collected
through the public API using the included collectors.

## Structure

- `scripts/`: analysis and search scripts used for the HITS pipeline,
  algorithm comparison, permutation tests, ablation, store-type analysis,
  mechanism analysis, western extension, LCA inputs, dynamic policy
  sensitivity, and public data search.
- `data/`: processed public validation records, official city-level battery
  figures, store-ledger search results, LCA indicator files, and processed
  throughput/forecast workbooks.
- `results/`: summary JSON/CSV outputs for the experiments reported in the
  manuscript, including the paper-reported synthetic recovery results.

## Core analysis scripts

| File | Purpose |
|---|---|
| `hits_analysis.py`, `hits_analysis2.py` | Bipartite HITS scoring and city-level coordination metrics |
| `algorithm_comparison.py` | Degree, Betweenness, PageRank, HITS, GCN, GAT, TCN comparison |
| `random_permutation_test.py` | Random target and network permutation tests |
| `compute_ablation_permutation.py` | Component ablation and multiple permutation nulls |
| `enriched_hits.py` | Enriched HITS variants and summary |
| `mechanism_analysis.py` | Store-level mechanism model |
| `classify_store_types.py` | Store-type decomposition |
| `compute_dynamic_policy_sensitivity.py` | Dynamic policy scenario sensitivity |
| `analyze_amap_western.py` | Western city spatial extension |
| `retirement_model.py`, `forecast_model.py` | Battery retirement and city throughput projection |
| `fetch_official_city_pages.py` | Official city-level recovery record collection |
| `search_all_sources.py` | Public and company annual-report evidence search |
| `browser_search_store_ledgers.py` | Store-level ledger availability search |

## Data boundaries

- The paper does not claim store-level real-ledger validation.
- City-level volumes for Wuxi, Changsha, and Wuhan are contextual anchors,
  not matched store-level tests.
- Store-level ledgers were not publicly available at the time of writing; the
  closest public evidence is documented in
  `data/Store_Ledger_Search_Report.md`.
- Synthetic recovery results are recorded in
  `results/synthetic_recovery_paper_results.json`; the original generation
  script was not retained in the local package and should be reconstructed
  before final submission if the repository is presented as fully runnable.

## Requirements

See `requirements.txt`. Some search scripts require network access or an
Amap API key.
