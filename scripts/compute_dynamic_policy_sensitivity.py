import json
import numpy as np
from pathlib import Path

OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/dynamic_policy_sensitivity")
OUT.mkdir(parents=True, exist_ok=True)

rng = np.random.default_rng(2026)
n_draws = 5000

# Base tier counts.
n1, n2, n3 = 4, 5, 27
total = n1 + n2 + n3
u_cost = 100.0
u_gain = 5.0
base_costs = np.array([40.0, 70.0, 130.0])
base_gains = np.array([2.0, 8.0, 15.0])

# Sample independent uniform +/-20% ranges.
costs = rng.uniform(base_costs * 0.8, base_costs * 1.2, size=(n_draws, 3))
gains = rng.uniform(base_gains * 0.8, base_gains * 1.2, size=(n_draws, 3))
r_t3 = rng.uniform(0.0, 0.4, size=n_draws)
r_t2 = 0.5 * r_t3


def dynamic_ratio(c, g, r3, r2, years=3):
    n1c, n2c, n3c = n1, n2, n3
    cum_d_gain = 0.0
    cum_d_cost = 0.0
    for y in range(years):
        d_gain = (n1c * g[0] + n2c * g[1] + n3c * g[2]) / total
        d_cost = n1c * c[0] + n2c * c[1] + n3c * c[2]
        cum_d_gain += d_gain
        cum_d_cost += d_cost
        if y < years - 1:
            move_t3 = n3c * r3
            move_t2 = n2c * r2
            n1c = n1c + move_t2
            n2c = n2c - move_t2 + move_t3
            n3c = n3c - move_t3
    return cum_d_gain, cum_d_cost


single = []
three = []
net_gain = []
for i in range(n_draws):
    g1 = (n1 * gains[i, 0] + n2 * gains[i, 1] + n3 * gains[i, 2]) / total
    c1 = n1 * costs[i, 0] + n2 * costs[i, 1] + n3 * costs[i, 2]
    single.append((g1 / u_gain) / (c1 / (total * u_cost)))
    dg, dc = dynamic_ratio(costs[i], gains[i], r_t3[i], r_t2[i], years=3)
    three.append((dg / (u_gain * 3)) / (dc / (total * u_cost * 3)))
    net_gain.append(dg - u_gain * 3)

single = np.array(single)
three = np.array(three)
net_gain = np.array(net_gain)


def summarize(a, nd=3):
    return {
        "median": round(float(np.median(a)), nd),
        "p5": round(float(np.percentile(a, 5)), nd),
        "p95": round(float(np.percentile(a, 95)), nd),
        "min": round(float(a.min()), nd),
        "max": round(float(a.max()), nd),
    }


summary = {
    "n_draws": n_draws,
    "single_year_ratio": summarize(single),
    "three_year_dynamic_ratio": summarize(three),
    "three_year_net_gain_pp": summarize(net_gain),
    "assumptions": {
        "tier_costs": "uniform +/-20% around 40/70/130",
        "tier_gains": "uniform +/-20% around 2/8/15 percentage points",
        "t3_to_t2_rate": "uniform 0-0.4 per year",
        "t2_to_t1_rate": "half of t3_to_t2 rate",
        "years": 3,
    },
}
with open(OUT / "dynamic_policy_sensitivity_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

np.save(OUT / "single_year_ratio.npy", single)
np.save(OUT / "three_year_ratio.npy", three)
np.save(OUT / "net_gain_pp.npy", net_gain)
print(json.dumps(summary, ensure_ascii=False, indent=2))
