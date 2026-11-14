"""Diagnostics that explain two results of the study (they do not change any rule; the runs are identical to normal
runs, with counters added). python3 -m catsim.study_diagnostics -> study_results/tables/diag_*.csv

1. Prequal at the telemetry budget: probes per query, share of fallback decisions (fewer than 2 probes in the pool),
   and the planned uses per probe (b_reuse) at the low / medium / high budgets.
2. LSQ with shared reports vs LSQ-Sample (and WRR for scale), with 1 and 4 ingresses: success and how bursty the
   traffic each site receives is (herding), at the three budgets.
3. ours v6 around traffic bursts (90% load, bursty): its planned drop share and its estimate of the offered traffic
   (over the configured capacity) before, during and after each burst.
Seeds 201-205, load 90%, steady, 50 ms telemetry delay, frozen parameters.
"""
import os

import numpy as np
import pandas as pd

from . import study as st
from .baselines import resolve_rule
from .engine import run
from .rules import RULE_CLASSES

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAB = os.path.join(HERE, "study_results", "tables")
SEEDS = (201, 202, 203, 204, 205)


class _CountingRng:
    """The same generator (same random numbers); counts Prequal's fallback draws (the only call with p=...)."""

    def __init__(self, rng):
        self._r = rng
        self.fallback = 0

    def choice(self, *a, **k):
        if "p" in k:
            self.fallback += 1
        return self._r.choice(*a, **k)

    def __getattr__(self, name):
        return getattr(self._r, name)


def _prequal_diag_class(base):
    class Diag(base):
        def __init__(self, ctx, i):
            super().__init__(ctx, i)
            self.rng = _CountingRng(self.rng)
            self.d_queries = 0
            self.d_b = []

        def on_probe_x(self, now, s, rif, t_meas, lat):
            super().on_probe_x(now, s, rif, t_meas, lat)
            self.d_b.append(self.pool[-1][5])

        def choose(self, now):
            out = super().choose(now)
            self.d_queries += 1
            return out
    return Diag


def prequal(frozen):
    RULE_CLASSES["_diag_prequal"] = _prequal_diag_class(resolve_rule(st.resolved("prequal_hcl", frozen)))
    rows = []
    for name, W in (("low (10 s)", 10.0), ("medium (2 s)", 2.0), ("high (0.5 s)", 0.5)):
        sc = st.make(0.9, 0.05, "steady", W=W)
        for sd in SEEDS:
            box = {}
            o = run(sc, "_diag_prequal", sd, hook=lambda d: box.update(d))
            rs = box["rules"]
            q = sum(r.d_queries for r in rs)
            rows.append({"budget": name, "seed": sd, "success_pct": o["success"] * 100,
                         "probes_per_query": sum(r.n_p for r in rs) / q,
                         "fallback_share_pct": sum(r.rng.fallback for r in rs) / q * 100,
                         "planned_uses_per_probe": float(np.mean([b for r in rs for b in r.d_b])),
                         "bytes_per_s_per_ingress": o["bytes_per_s_per_ingress"]})
    del RULE_CLASSES["_diag_prequal"]
    d = pd.DataFrame(rows)
    return d.groupby("budget", sort=False).mean(numeric_only=True).drop(columns="seed").reset_index()


def lsq_herding():
    """Herding check for LSQ: success and how bursty the traffic each site receives is (coefficient of variation of
    its arrivals per 0.1 s, averaged over sites), with 1 and 4 ingresses, at the three budgets. Several dispatchers
    acting on the same fresh report pile onto the same sites, which shows up as burstier arrivals."""
    rows = []
    for R in (1, 4):
        for name, W in (("low (10 s)", 10.0), ("medium (2 s)", 2.0), ("high (0.5 s)", 0.5)):
            sc = st.make(0.9, 0.05, "steady", W=W, R=R)
            for rule in ("wrr", "lsq", "lsq_sample"):
                for sd in SEEDS:
                    box = {}
                    o = run(sc, rule, sd, hook=lambda d: box.update(d))
                    cr, so = np.asarray(box["created"]), np.asarray(box["site_of"])
                    m = (cr >= box["warm"]) & (so >= 0)
                    b = np.floor(cr[m] / 0.1).astype(int)
                    b -= b.min()
                    cv = []
                    for s_ in range(len(st.SERVERS_HET)):
                        c = np.bincount(b[so[m] == s_], minlength=b.max() + 1)
                        cv.append(c.std() / c.mean() if c.mean() > 0 else np.nan)
                    rows.append({"ingresses": R, "budget": name, "rule": rule, "seed": sd,
                                 "success_pct": o["success"] * 100, "arrival_cv_per_0.1s": float(np.nanmean(cv)),
                                 "bytes_per_s_per_ingress": o["bytes_per_s_per_ingress"],
                                 "aoi_mean_s": o["aoi_mean_s"]})
    d = pd.DataFrame(rows)
    return d.groupby(["ingresses", "budget", "rule"], sort=False).mean(numeric_only=True).drop(
        columns="seed").reset_index()


def v6_bursts():
    base = resolve_rule("ours_v6")

    class Rec(base):
        def choose(self, now):
            out = super().choose(now)
            self.rec.append((now, float(self.p_drop), float(np.sum(self.rate_off))))
            return out

        def __init__(self, ctx, i):
            super().__init__(ctx, i)
            self.rec = []
    RULE_CLASSES["_diag_v6"] = Rec
    cap = float(sum(st.SERVERS_HET)) * float(st.CFG["service_rate_per_gpu"])
    wins = (("5 s before", -5.0, 0.0), ("during (5 s)", 0.0, st.BURST_LEN), ("0-2 s after", st.BURST_LEN,
            st.BURST_LEN + 2), ("2-5 s after", st.BURST_LEN + 2, st.BURST_LEN + 5),
            ("5-10 s after", st.BURST_LEN + 5, st.BURST_LEN + 10))
    rows = []
    sc = st.make(0.9, 0.05, "bursty")
    for sd in SEEDS:
        box = {}
        run(sc, "_diag_v6", sd, hook=lambda d: box.update(d))
        for r in box["rules"]:
            rec = np.array(r.rec)
            for name, a, b in wins:
                m = np.zeros(len(rec), bool)
                for b0 in st.BURSTS:
                    m |= (rec[:, 0] >= b0 + a) & (rec[:, 0] < b0 + b)
                if m.any():
                    rows.append({"window": name, "seed": sd, "ingress": r.i, "drop_share_pct": rec[m, 1].mean() * 100,
                                 "offered_estimate_over_capacity": rec[m, 2].mean() / cap})
    del RULE_CLASSES["_diag_v6"]
    d = pd.DataFrame(rows)
    return d.groupby("window", sort=False)[["drop_share_pct", "offered_estimate_over_capacity"]].mean().reset_index()


def main():
    os.makedirs(TAB, exist_ok=True)
    frozen = st.load_frozen()
    p = prequal(frozen)
    p.to_csv(os.path.join(TAB, "diag_prequal_budget.csv"), index=False)
    h = lsq_herding()
    h.to_csv(os.path.join(TAB, "diag_lsq_herding.csv"), index=False)
    b = v6_bursts()
    b.to_csv(os.path.join(TAB, "diag_v6_bursts.csv"), index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(p.round(3).to_string(index=False))
        print(h.round(3).to_string(index=False))
        print(b.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
