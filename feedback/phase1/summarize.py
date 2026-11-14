"""Tables of Phase 1 from diagnose.csv and pilot.csv (python3 summarize.py)."""
import json
import os

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 200)
ORDER = ["ours_v6", "est_own_b1", "est_bound", "est_bound_b1", "est_echo", "est_echo_b1"]


def load(name):
    d = pd.read_csv(os.path.join(HERE, name))
    for c in ("est_by_ingress", "share_by_ingress", "plan_drop_by_ingress", "site_load", "belief_over_realized",
              "meter_changes"):
        d[c] = d[c].apply(json.loads)
    return d


def paired(d, col="success", base="ours_v6"):
    rows = []
    for sc in dict.fromkeys(d.scenario):
        b = d[(d.rule == base) & (d.scenario == sc)].set_index("seed")[col]
        r = {"scenario": sc}
        for ru in [x for x in ORDER if x != base and x in set(d.rule)]:
            x = (d[(d.rule == ru) & (d.scenario == sc)].set_index("seed")[col] - b).dropna().values
            h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
            r[ru] = f"{x.mean():+.2f} ±{h:.2f}"
        rows.append(r)
    return pd.DataFrame(rows)


def by_ingress(d, col):
    return {k: np.mean(np.array(x[col].tolist()), axis=0) for k, x in d.groupby(["scenario", "rule"], sort=False)
            if x.R.iloc[0] == 4}


if __name__ == "__main__":
    p = load("pilot.csv")
    scs = list(dict.fromkeys(p.scenario))
    for col, name in (("success", "SUCCESS %"), ("rejected", "REJECTED %"), ("expired", "EXPIRED %"), ("late", "LATE %"),
                      ("admitted_over_capacity", "ADMITTED / CAPACITY"),
                      ("spread_mean", "SPREAD of drop share between ingresses (points, 5-s windows with drops)"),
                      ("est_min", "ESTIMATE / TRUTH, lowest ingress"), ("est_max", "ESTIMATE / TRUTH, highest ingress"),
                      ("extra_bytes_per_s_per_ingress", "EXTRA BYTES/s per ingress")):
        print("\n" + name)
        print(p.pivot_table(index="scenario", columns="rule", values=col, sort=False)[ORDER].loc[scs].round(3).to_string())
    print("\nPAIRED difference in success vs ours_v6 (points, 95% half-width, 5 pilot seeds)")
    print(paired(p).to_string(index=False))
    sh, es = by_ingress(p, "share_by_ingress"), by_ingress(p, "est_by_ingress")
    print()
    for k in sh:
        print(f"{k[0]:16s} {k[1]:13s} drop share by ingress {np.round(sh[k], 1)}   estimate/truth {np.round(es[k], 3)}")
    print(p.groupby("rule").base_bytes_per_s_per_ingress.mean())
