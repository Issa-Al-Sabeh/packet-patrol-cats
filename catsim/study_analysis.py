"""Analysis of the staleness-aware CATS study: every run, aggregates with 95% confidence intervals, the main comparison,
oracle gaps, telemetry efficiency, admission fairness, ablation, sensitivity tables (study_results/tables/*.csv).

Only completed runs are used; every table says how many seeds and scenario points it is based on.
Definitions (identical for every algorithm):
  success   = frames answered on time / all frames generated after the warm-up (rejected and expired count as failures)
  late      = answered after the deadline; expired = discarded by a deadline-aware site before service;
  rejected  = dropped at the ingress; the four add up to 1 for every run (checked by the engine)
  oracle gap (percentage points) = success(fresh-state oracle) - success(algorithm), per scenario, then averaged
  95% CI    = Student t over the 10 evaluation seeds (paired by seed for differences)
  recovery  = after an event ends, the first second from which the 3-s rolling success is back within 5 points of
              its level in the 5 s before the event started (censored at the next event or the end of the run)
"""
import json
import math
import os

import numpy as np
import pandas as pd
from scipy import stats

from . import study as st
from .experiments import run_path

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "study_results")
RUNS = os.path.join(OUT, "runs")
TAB = os.path.join(OUT, "tables")

SCALARS = ["success", "late_completed", "expired", "rejected", "admitted", "miss", "mean_ms", "p50_ms", "p95_ms",
           "p99_ms", "wait_ms", "wait_p95_ms", "offered_load", "offered_rate", "completed_rate", "goodput",
           "util_mean", "imbalance", "avg_queue_mean", "max_queue_max", "bytes_per_s", "bytes_per_s_per_ingress",
           "report_bytes_per_s", "probe_bytes_per_s", "report_msgs", "probe_msgs", "msgs_per_s",
           "report_rounds_sent", "aoi_mean_s", "aoi_p95_s", "est_err_mean", "est_err_p95", "decisions",
           "switch_rate", "frames", "runtime_s"]
PCT = ["success", "late_completed", "expired", "rejected", "admitted", "miss"]


def ci95(x):
    x = np.asarray([v for v in x if v == v], float)
    if len(x) == 0:
        return float("nan"), float("nan"), 0
    if len(x) < 2:
        return float(x.mean()), float("nan"), len(x)
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x))
    return float(x.mean()), float(h), len(x)


def _recovery(ts, t0, t1, t_next):
    """Seconds after t1 until the 3-s rolling success is within 5 points of the 5 s before t0 (censored)."""
    base0 = ts["t0"]
    fr = np.array(ts["frames"], float)
    sc = np.array(ts["success"], float)
    rate = np.where(fr > 0, sc / np.maximum(fr, 1), np.nan)

    def at(t):
        return int(t) - base0

    pre = rate[max(0, at(t0 - 5)):at(t0)]
    if len(pre) == 0 or np.all(np.isnan(pre)):
        return float("nan"), float("nan"), False
    b = float(np.nanmean(pre))
    end = min(len(rate), at(t_next))
    dur = rate[at(t0):min(end, at(t1) + 5)]
    impact = float(np.nanmean(dur)) - b if len(dur) else float("nan")
    for k in range(at(t1), end - 2):
        if np.nanmean(rate[k:k + 3]) >= b - 0.05:
            return float(k - at(t1)), impact, False
    return float(end - at(t1)), impact, True


def event_list(meta):
    if meta["tag"] in st.EVENT_TIMES:
        t0, t1 = st.EVENT_TIMES[meta["tag"]]
        return [(t0, t1, st.SIM_TIME)]
    if meta["pattern"] == "bursty":
        b = list(st.BURSTS)
        return [(t, t + st.BURST_LEN, (b[k + 1] if k + 1 < len(b) else st.SIM_TIME)) for k, t in enumerate(b)]
    return []


def load_runs():
    frozen = st.load_frozen()
    rows, seen, series = [], set(), {}
    for eid, _, lst in st.experiments(frozen):
        for sc, alias in lst:
            meta = st.meta_of(sc)
            rule = st.resolved(alias, frozen)
            for sd in st.SEEDS_FINAL:
                key = (sc.key, alias, sd)
                if key in seen:
                    continue
                p = run_path(RUNS, sc, rule, sd)
                if not os.path.exists(p):
                    continue
                with open(p) as f:
                    o = json.load(f)
                seen.add(key)
                row = dict(experiment=eid, scenario=sc.key, alias=alias, rule=rule, seed=sd, **meta)
                for k in SCALARS:
                    row[k] = o.get(k, float("nan"))
                for k in PCT:
                    row[k] = row[k] * 100.0
                ev = event_list(meta)
                if ev:
                    rec = [_recovery(o["ts"], *e) for e in ev]
                    row["recovery_s"] = float(np.nanmean([r[0] for r in rec]))
                    row["impact_pp"] = float(np.nanmean([r[1] for r in rec])) * 100.0
                    row["recovery_censored"] = int(sum(r[2] for r in rec))
                    series[key] = o["ts"]
                rows.append(row)
    return pd.DataFrame(rows), series


def aggregate(df, by, metrics):
    out = []
    for keys, g in df.groupby(by, sort=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(by, keys))
        for m in metrics:
            mu, h, n = ci95(g[m])
            row[m] = mu
            row[m + "_ci95"] = h
        row["n_seeds"] = int(g["seed"].nunique())
        out.append(row)
    return pd.DataFrame(out)


def paired(df, scen_keys, a, b, metric="success"):
    """Mean and CI of (a - b) paired by seed, over the given scenarios pooled."""
    d = []
    for sk in scen_keys:
        ga = df[(df.scenario == sk) & (df.alias == a)].set_index("seed")[metric]
        gb = df[(df.scenario == sk) & (df.alias == b)].set_index("seed")[metric]
        common = ga.index.intersection(gb.index)
        d += list(ga[common] - gb[common])
    return ci95(d)


def verdict(mu, h):
    if mu != mu or h != h:
        return "n/a"
    return "better" if mu - h > 0 else ("worse" if mu + h < 0 else "same")


def run_status():
    """Completed vs pending runs per experiment (seeds 201-210), written to run_status.csv."""
    frozen = st.load_frozen()
    rows = []
    for eid, desc, lst in st.experiments(frozen):
        n = d = 0
        for sc, alias in lst:
            rule = st.resolved(alias, frozen)
            for sd in st.SEEDS_FINAL:
                n += 1
                d += os.path.exists(run_path(RUNS, sc, rule, sd))
        rows.append({"experiment": eid, "description": desc, "runs_done": d, "runs_planned": n,
                     "status": "complete" if d == n else ("pending" if d == 0 else "partial")})
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(TAB, "run_status.csv"), index=False)
    return out


def main():
    os.makedirs(TAB, exist_ok=True)
    run_status()
    df, series = load_runs()
    if df.empty:
        print("No completed runs yet.")
        return
    df.to_csv(os.path.join(TAB, "runs_all.csv"), index=False)
    metrics = ["success", "late_completed", "expired", "rejected", "p50_ms", "p95_ms", "p99_ms", "mean_ms", "wait_ms",
               "util_mean", "imbalance", "avg_queue_mean", "max_queue_max", "bytes_per_s_per_ingress", "msgs_per_s",
               "aoi_mean_s", "aoi_p95_s", "est_err_mean", "switch_rate", "offered_load", "goodput",
               "completed_rate"]
    if "recovery_s" in df:
        metrics += ["recovery_s", "impact_pp"]
    meta_cols = ["scenario", "load", "delay_ms", "pattern", "W", "R", "cap", "deadline", "tag", "alias"]
    agg = aggregate(df, meta_cols, metrics)
    agg.to_csv(os.path.join(TAB, "agg_by_scenario.csv"), index=False)

    # ---------------- main comparison over the main grid (R = 4, W = 2 s, heterogeneous, 300 ms, no events)
    grid = agg[(agg.R == 4) & (agg.W == 2.0) & (agg.cap == "het") & (agg.deadline == 300) & (agg.tag == "")]
    grid = grid[grid.alias.isin(st.MAIN_RULES)]
    complete = grid.groupby("scenario").alias.nunique()
    full_sc = complete[complete == len(st.MAIN_RULES)].index
    grid = grid[grid.scenario.isin(full_sc)]
    orc = grid[grid.alias == "oracle"].set_index("scenario")["success"]
    # supplementary reference: the same oracle behind the common rejection wrapper (only where those runs exist)
    oadm_rows = agg[(agg.alias == "oracle+adm") & agg.scenario.isin(full_sc)]
    oadm = oadm_rows.set_index("scenario")["success"]
    supp_rows = agg[agg.alias.isin(st.SUPP_RULES) & agg.scenario.isin(full_sc)]          # supplementary rivals
    grid = pd.concat([grid, supp_rows, oadm_rows], ignore_index=True)
    grid = grid.assign(oracle_gap_pp=grid.apply(lambda r: orc.get(r.scenario, np.nan) - r.success, axis=1),
                       gap_vs_oracle_wrapped_pp=grid.apply(lambda r: oadm.get(r.scenario, np.nan) - r.success, axis=1))
    rows = []
    for regime, sel in (("all", grid), ("below capacity (60%, 90%)", grid[grid.load < 1.0]),
                        ("overload (110%, 130%)", grid[grid.load > 1.0])):
        for alias in st.MAIN_RULES + st.SUPP_RULES + ["oracle+adm"]:
            g = sel[sel.alias == alias]
            if g.empty:
                continue
            ga = g.dropna(subset=["gap_vs_oracle_wrapped_pp"])
            rows.append({"regime": regime, "algorithm": st.LABELS[alias] + (" (reference)" if alias == "oracle+adm"
                                                                             else ""), "alias": alias,
                         "deadline_success_pct": g.success.mean(), "oracle_gap_pp": g.oracle_gap_pp.mean(),
                         "gap_vs_oracle_wrapped_pp": ga.gap_vs_oracle_wrapped_pp.mean() if len(ga) else np.nan,
                         "p99_latency_ms": g.p99_ms.mean(), "drop_rate_pct": g.rejected.mean(),
                         "expired_pct": g.expired.mean(), "late_pct": g.late_completed.mean(),
                         "telemetry_Bps_per_ingress": g.bytes_per_s_per_ingress.mean(),
                         "aoi_mean_s": g.aoi_mean_s.mean(), "n_scenarios": g.scenario.nunique(),
                         "n_scenarios_oracle_wrapped": ga.scenario.nunique()})
    main_tab = pd.DataFrame(rows)
    main_tab.to_csv(os.path.join(TAB, "main_comparison.csv"), index=False)
    grid[["scenario", "load", "delay_ms", "pattern", "alias", "success", "success_ci95", "oracle_gap_pp",
          "gap_vs_oracle_wrapped_pp"]].to_csv(os.path.join(TAB, "oracle_gap.csv"), index=False)

    # ---------------- per-load averages over the main grid (4 delays x 3 patterns)
    bl = []
    for L in st.LOADS:
        sel = grid[grid.load == L]
        for alias in st.MAIN_RULES + st.SUPP_RULES + ["oracle+adm"]:
            g = sel[sel.alias == alias]
            if len(g):
                bl.append({"load": L, "alias": alias, "algorithm": st.LABELS[alias], "success": g.success.mean(),
                           "rejected": g.rejected.mean(), "expired": g.expired.mean(), "late": g.late_completed.mean(),
                           "p99_ms": g.p99_ms.mean(), "n_scenarios": g.scenario.nunique()})
    pd.DataFrame(bl).to_csv(os.path.join(TAB, "by_load.csv"), index=False)

    # ---------------- effect of telemetry delay (1000 ms minus 0 ms), paired by seed, pooled over the three patterns
    de = []
    for L in st.LOADS:
        for alias in st.MAIN_RULES + st.SUPP_RULES:
            d = []
            for pat in st.PATTERNS:
                k0, k1 = st.make(L, 0.0, pat).key, st.make(L, 1.0, pat).key
                g0 = df[(df.scenario == k0) & (df.alias == alias)].set_index("seed").success
                g1 = df[(df.scenario == k1) & (df.alias == alias)].set_index("seed").success
                c = g0.index.intersection(g1.index)
                d += list(g1[c] - g0[c])
            if d:
                mu, h, n = ci95(d)
                de.append({"load": L, "alias": alias, "algorithm": st.LABELS[alias], "delay_1000_minus_0_pp": mu,
                           "ci95": h, "verdict": {"better": "improves", "worse": "degrades", "same": "no change"}
                           .get(verdict(mu, h), "n/a"), "n_pairs": n})
    pd.DataFrame(de).to_csv(os.path.join(TAB, "delay_effect.csv"), index=False)

    # ---------------- paired comparison against ours v6 (per grid scenario; better / same / worse)
    pv = []
    for alias in st.MAIN_RULES + st.SUPP_RULES:
        if alias == "ours_v6":
            continue
        for regime, loads in (("below", (0.6, 0.9)), ("overload", (1.1, 1.3))):
            cnt = {"better": 0, "same": 0, "worse": 0, "n/a": 0}
            diffs = []
            for sk in full_sc:
                L = float(agg[agg.scenario == sk].load.iloc[0])
                if L not in loads:
                    continue
                mu, h, n = paired(df, [sk], "ours_v6", alias)
                if not n:                                   # supplementary rival not run in this scenario
                    continue
                cnt[verdict(mu, h)] += 1
                diffs.append(mu)
            pv.append({"rival": st.LABELS[alias], "regime": regime, "v6_minus_rival_pp_mean": float(np.mean(diffs))
                       if diffs else np.nan, "v6_better": cnt["better"], "same": cnt["same"],
                       "v6_worse": cnt["worse"], "n_scenarios": len(diffs)})
    pd.DataFrame(pv).to_csv(os.path.join(TAB, "paired_vs_v6.csv"), index=False)

    # ---------------- where does v6 lose? best practical rival in every scenario of every experiment
    practical = [a for a in st.MAIN_RULES + st.SUPP_RULES if a != "oracle"] + [a + "+adm" for a in st.ADM_RULES
                                                                              if a != "oracle"]
    wc = []
    for sk, g in agg.groupby("scenario"):
        if "ours_v6" not in set(g.alias):
            continue
        riv = g[g.alias.isin([a for a in practical if a != "ours_v6"])]
        if riv.empty:
            continue
        best = riv.loc[riv.success.idxmax()]
        mu, h, n = paired(df, [sk], "ours_v6", best.alias)
        r0 = g.iloc[0]
        wc.append({"scenario": sk, "load": r0.load, "delay_ms": r0.delay_ms, "pattern": r0.pattern, "W": r0.W,
                   "R": r0.R, "cap": r0.cap, "deadline": r0.deadline, "tag": r0.tag,
                   "v6_success": float(g[g.alias == "ours_v6"].success.iloc[0]), "best_rival": best.alias,
                   "best_rival_success": best.success, "v6_minus_best_pp": mu, "ci95": h,
                   "verdict": verdict(mu, h), "n_seeds": n})
    pd.DataFrame(wc).sort_values("v6_minus_best_pp").to_csv(os.path.join(TAB, "v6_vs_best_rival.csv"), index=False)

    # ---------------- telemetry delay sensitivity (steady, R=4, W=2, het, 300 ms)
    dl = agg[(agg.pattern == "steady") & (agg.R == 4) & (agg.W == 2.0) & (agg.cap == "het") & (agg.deadline == 300)
             & (agg.tag == "") & agg.alias.isin(st.MAIN_RULES + st.SUPP_RULES)]
    dl[["load", "delay_ms", "alias", "success", "success_ci95", "aoi_mean_s", "est_err_mean", "n_seeds"]].sort_values(
        ["load", "alias", "delay_ms"]).to_csv(os.path.join(TAB, "delay_sensitivity.csv"), index=False)

    # ---------------- traffic patterns
    pt = agg[(agg.delay_ms == 50) & (agg.R == 4) & (agg.W == 2.0) & (agg.cap == "het") & (agg.deadline == 300)
             & (agg.tag == "") & agg.alias.isin(st.MAIN_RULES + st.SUPP_RULES)]
    cols = ["load", "pattern", "alias", "success", "success_ci95", "p99_ms", "rejected", "switch_rate", "n_seeds"]
    if "recovery_s" in pt:
        cols += ["recovery_s", "impact_pp"]
    pt[cols].sort_values(["load", "pattern", "alias"]).to_csv(os.path.join(TAB, "traffic_patterns.csv"), index=False)

    # ---------------- telemetry budget efficiency
    bud = agg[(agg.pattern == "steady") & (agg.delay_ms == 50) & (agg.R == 4) & (agg.cap == "het")
              & (agg.deadline == 300) & agg.tag.isin(["", "thr"])]
    bud = bud.assign(budget=bud.apply(lambda r: "threshold (0.5 s checks)" if r.tag == "thr" else
                                      {10.0: "low (10 s)", 2.0: "medium (2 s)", 0.5: "high (0.5 s)"}.get(r.W, "?"),
                                      axis=1))
    bud = bud[bud.alias.isin(st.MAIN_RULES + st.SUPP_RULES + ["prequal_native"])]
    no_tel = {"nearest", "wrr", "oracle"}
    bud = bud.assign(configured_budget_Bps_per_ingress=bud.apply(
        lambda r: 0.0 if r.alias in no_tel else (float("inf") if r.alias == "prequal_native" else
                                                 len(st.SERVERS_HET) * 66.0 / (2.0 if r.tag == "thr" else r.W)),
        axis=1))
    bud[["load", "budget", "alias", "success", "success_ci95", "configured_budget_Bps_per_ingress",
         "bytes_per_s_per_ingress", "msgs_per_s", "aoi_mean_s", "est_err_mean", "n_seeds"]].sort_values(
        ["load", "alias", "budget"]).to_csv(os.path.join(TAB, "telemetry_efficiency.csv"), index=False)

    # ---------------- admission-control fairness
    ad = agg[(agg.pattern == "steady") & (agg.delay_ms == 50) & (agg.R == 4) & (agg.W == 2.0) & (agg.cap == "het")
             & (agg.deadline == 300) & (agg.tag == "")]
    arows = []
    for L in st.LOADS:
        a = ad[ad.load == L].set_index("alias")
        for base in st.ADM_RULES:
            if base in a.index and base + "+adm" in a.index:
                n, w = a.loc[base], a.loc[base + "+adm"]
                mu, h, _ = paired(df, [st.make(L, 0.05, "steady").key], "ours_v6", base + "+adm")
                arows.append({"load": L, "algorithm": st.LABELS[base], "kind": "routing + common wrapper",
                              "native_success": n.success, "wrapped_success": w.success,
                              "wrapped_success_ci95": w.success_ci95, "gain_pp": w.success - n.success,
                              "native_rejected": n.rejected, "wrapped_rejected": w.rejected,
                              "wrapped_p99_ms": w.p99_ms, "v6_minus_wrapped_pp": mu, "v6_minus_wrapped_ci95": h,
                              "v6_vs_wrapped": verdict(mu, h)})
        for nat in st.NATIVE_DROPPERS:
            if nat in a.index:
                r = a.loc[nat]
                mu, h, _ = paired(df, [st.make(L, 0.05, "steady").key], "ours_v6", nat) if nat != "ours_v6" \
                    else (np.nan, np.nan, 0)
                arows.append({"load": L, "algorithm": st.LABELS[nat], "kind": "native admission control",
                              "native_success": r.success, "wrapped_success": np.nan, "wrapped_success_ci95": np.nan,
                              "gain_pp": np.nan, "native_rejected": r.rejected, "wrapped_rejected": np.nan,
                              "wrapped_p99_ms": r.p99_ms, "native_success_ci95": r.success_ci95,
                              "v6_minus_wrapped_pp": mu, "v6_minus_wrapped_ci95": h,
                              "v6_vs_wrapped": verdict(mu, h) if nat != "ours_v6" else ""})
    pd.DataFrame(arows).to_csv(os.path.join(TAB, "admission_comparison.csv"), index=False)

    # ---------------- ablation of v6 (paired by seed)
    ab = []
    for pat in ("steady", "bursty"):
        for L in st.LOADS:
            sk = st.make(L, 0.05, pat).key
            for a in st.ABLATIONS:
                mu, h, n = paired(df, [sk], "ours_v6", a)
                if n:
                    ab.append({"pattern": pat, "load": L, "ablation": st.LABELS[a], "alias": a,
                               "v6_minus_ablation_pp": mu, "ci95": h, "verdict": verdict(mu, h), "n_seeds": n})
    pd.DataFrame(ab).to_csv(os.path.join(TAB, "ablation.csv"), index=False)

    # ---------------- scalability, failures, capacity, deadline
    sc_ = agg[(agg.pattern == "steady") & (agg.delay_ms == 50) & (agg.W == 2.0) & (agg.cap == "het")
              & (agg.deadline == 300) & (agg.tag == "") & agg.load.isin([0.9, 1.3]) & agg.alias.isin(st.MAIN_RULES + st.SUPP_RULES)]
    sc_[["load", "R", "alias", "success", "success_ci95", "rejected", "aoi_mean_s", "n_seeds"]].sort_values(
        ["load", "alias", "R"]).to_csv(os.path.join(TAB, "scalability.csv"), index=False)
    fl = agg[agg.tag.isin(["fail", "slow", "congest"])]
    cols = ["tag", "alias", "success", "success_ci95", "p99_ms", "n_seeds"] + (
        ["recovery_s", "recovery_s_ci95", "impact_pp"] if "recovery_s" in fl else [])
    fl[cols].to_csv(os.path.join(TAB, "failures.csv"), index=False)
    cap = agg[(agg.pattern == "steady") & (agg.delay_ms == 50) & (agg.W == 2.0) & (agg.R == 4) & (agg.tag == "")
              & agg.load.isin([0.9, 1.3]) & agg.alias.isin(st.MAIN_RULES + st.SUPP_RULES)]
    cap[["load", "cap", "deadline", "alias", "success", "success_ci95", "rejected", "p99_ms", "n_seeds"]].sort_values(
        ["load", "deadline", "cap", "alias"]).to_csv(os.path.join(TAB, "capacity_deadline.csv"), index=False)

    # ---------------- parameters
    fz = st.load_frozen()
    prow = [{"item": k, "value": v} for k, v in fz.items()]
    for alias in st.MAIN_RULES + st.ABLATIONS + ["oracle_adm", "prequal_native"]:
        prow.append({"item": f"run as: {alias}", "value": st.resolved(alias, fz)})
    prow += [{"item": "seeds_final", "value": " ".join(map(str, st.SEEDS_FINAL))},
             {"item": "seeds_pilot", "value": " ".join(map(str, st.SEEDS_PILOT))},
             {"item": "servers (GPUs per site)", "value": str(st.SERVERS_HET)},
             {"item": "servers homogeneous", "value": str(st.SERVERS_HOM)},
             {"item": "delay matrix 4 ingresses (ms)", "value": json.dumps(st.delay_matrix(4))},
             {"item": "service", "value": "100 ms mean per frame, gamma, SCV 0.25"},
             {"item": "deadline strict / relaxed", "value": "300 ms / 500 ms"},
             {"item": "report interval (low/medium/high budget)", "value": json.dumps(st.BUDGET_W)},
             {"item": "telemetry delays (s)", "value": json.dumps(st.DELAYS)},
             {"item": "loads", "value": json.dumps(st.LOADS)},
             {"item": "sim time / warm-up (s)", "value": f"{st.SIM_TIME} / {st.WARMUP}"},
             {"item": "bursts", "value": f"x{st.BURST_X} for {st.BURST_LEN} s at {st.BURSTS}"},
             {"item": "shifting", "value": f"ingress shares rotate every {st.SHIFT_EVERY} s"}]
    pd.DataFrame(prow).to_csv(os.path.join(TAB, "parameters.csv"), index=False)

    # ---------------- report loss and measurement noise (supplementary), paired with the clean runs by seed
    tfr = []
    for L in (0.9, 1.3):
        k0 = st.make(L, 0.05, "steady").key
        for tag, lab in (("loss", "reports lost"), ("noise", "noisy reports")):
            ex = agg[(agg.tag == tag) & np.isclose(agg.load, L)]
            if not len(ex):
                continue
            k1 = ex.scenario.iloc[0]
            for alias in st.MAIN_RULES:
                g0 = df[(df.scenario == k0) & (df.alias == alias)].set_index("seed").success
                g1 = df[(df.scenario == k1) & (df.alias == alias)].set_index("seed").success
                c = g0.index.intersection(g1.index)
                if not len(c):
                    continue
                mu, h, n = ci95(list(g1[c] - g0[c]))
                tfr.append({"load": L, "condition": lab, "alias": alias, "success_clean": g0[c].mean(),
                            "success_fault": g1[c].mean(), "fault_minus_clean_pp": mu, "ci95": h, "n_seeds": n})
    if tfr:
        pd.DataFrame(tfr).to_csv(os.path.join(TAB, "telemetry_faults.csv"), index=False)

    # ---------------- outcome classes before / during / after each server or network event (per-second series)
    ew = []
    for (sk, alias, sd), ts in series.items():
        meta = df[(df.scenario == sk)].iloc[0]
        if meta.tag not in st.EVENT_TIMES:
            continue
        t0, t1 = st.EVENT_TIMES[meta.tag]
        fr = np.asarray(ts["frames"], float)
        tt = ts["t0"] + np.arange(len(fr))
        for win, lo, hi in (("before (10 s)", t0 - 10, t0), ("during", t0, t1), ("after, first 15 s", t1, t1 + 15),
                            ("after, last 15 s", t1 + 15, t1 + 30)):
            m = (tt >= lo) & (tt < hi)
            n = fr[m].sum()
            if n <= 0:
                continue
            row = {"tag": meta.tag, "alias": alias, "seed": sd, "window": win}
            for k in ("success", "rejected", "expired", "late"):
                row[k] = float(np.asarray(ts[k], float)[m].sum() / n * 100.0)
            ew.append(row)
    if ew:
        ew = pd.DataFrame(ew)
        ewa = aggregate(ew, ["tag", "window", "alias"], ["success", "rejected", "expired", "late"])
        ewa.to_csv(os.path.join(TAB, "event_windows.csv"), index=False)

    # ---------------- outcome classes during bursts, in the 5 s after each burst, and the rest (main grid, 50 ms)
    bw = []
    meta_by = df.drop_duplicates("scenario").set_index("scenario")
    for (sk, alias, sd), ts in series.items():
        m0 = meta_by.loc[sk]
        if not (m0.pattern == "bursty" and m0.tag == "" and m0.delay_ms == 50 and m0.R == 4 and m0.W == 2.0
                and m0.cap == "het" and m0.deadline == 300):
            continue
        fr = np.asarray(ts["frames"], float)
        tt = ts["t0"] + np.arange(len(fr))
        dur = np.zeros(len(fr), bool)
        aft = np.zeros(len(fr), bool)
        for b0 in st.BURSTS:
            dur |= (tt >= b0) & (tt < b0 + st.BURST_LEN)
            aft |= (tt >= b0 + st.BURST_LEN) & (tt < b0 + st.BURST_LEN + 5)
        for win, m in (("during bursts", dur), ("5 s after each burst", aft), ("rest", ~dur & ~aft)):
            n = fr[m].sum()
            if n <= 0:
                continue
            row = {"load": m0.load, "alias": alias, "seed": sd, "window": win}
            for k in ("success", "rejected", "expired", "late"):
                row[k] = float(np.asarray(ts[k], float)[m].sum() / n * 100.0)
            bw.append(row)
    if bw:
        aggregate(pd.DataFrame(bw), ["load", "window", "alias"], ["success", "rejected", "expired", "late"]).to_csv(
            os.path.join(TAB, "burst_windows.csv"), index=False)

    with open(os.path.join(TAB, "_series.json"), "w") as f:
        json.dump({"|".join(map(str, k)): v for k, v in series.items()}, f)
    n_runs = len(df)
    print(f"{n_runs} completed runs; {len(full_sc)} complete main-grid scenarios -> study_results/tables/")
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(main_tab.round(2).to_string(index=False))
