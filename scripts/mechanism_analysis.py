from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import RepeatedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
import json

RES = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/hits_results")
TYPE = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/store_type_analysis")
OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/mechanism_analysis")
OUT.mkdir(parents=True, exist_ok=True)

stores = pd.read_csv(RES / "store_results.csv")
type_df = pd.read_csv(TYPE / "store_type_analysis.csv")
df = stores.merge(type_df[["store_id", "new_energy_related"]], on="store_id", how="left")
df["new_energy_related"] = df["new_energy_related"].fillna(0).astype(int)

# Connected stores only, using store-level structural features.
df = df[df["degree"] > 0].copy()
features = ["new_energy_related", "degree", "component_stores"]
X = df[features].copy()
y = np.log1p(df["brand_volume"].values)
Xz = (X - X.mean()) / (X.std() + 1e-8)

ols = LinearRegression().fit(Xz, y)
y_pred = ols.predict(Xz)
ss_res = np.sum((y - y_pred) ** 2)
ss_tot = np.sum((y - y.mean()) ** 2)
ols_r2 = 1 - ss_res / ss_tot

rf = RandomForestRegressor(n_estimators=300, random_state=2026, oob_score=True)
rf.fit(X, y)
rf_oob = rf.oob_score_
rkf = RepeatedKFold(n_splits=5, n_repeats=10, random_state=2026)
cv = cross_val_score(rf, X, y, cv=rkf, scoring="r2")

summary = {
    "n_connected_stores": int(len(df)),
    "ols_r2": float(ols_r2),
    "rf_oob_r2": float(rf_oob),
    "rf_cv_r2_mean": float(cv.mean()),
    "rf_cv_r2_std": float(cv.std()),
    
    "standardized_coefficients": dict(zip(features, [float(x) for x in ols.coef_])),
    "rf_feature_importance": dict(zip(features, [float(x) for x in rf.feature_importances_])),
}
with open(OUT / "mechanism_analysis_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(summary)
