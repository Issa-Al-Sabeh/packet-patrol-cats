"""Markdown tables for RESULTS.md, rendered straight from study_results/tables/*.csv (no number is typed by hand).
python3 -m catsim.study_report > study_results/tables/report_tables.md"""
import os

import numpy as np
import pandas as pd

from . import study as st

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAB = os.path.join(HERE, "study_results", "tables")


def _r(path):
    p = os.path.join(TAB, path)
    return pd.read_csv(p, keep_default_na=False, na_values=[""]) if os.path.exists(p) and os.path.getsize(p) > 5 \
        else pd.DataFrame()


def fmt(x, d=1, sign=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x:+.{d}f}" if sign else f"{x:.{d}f}"


def md(df, cols, heads):
    lines = ["| " + " | ".join(heads) + " |", "|" + "|".join("---" for _ in heads) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(c(r)) if callable(c) else str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def main():
    out = []
    mt = _r("main_comparison.csv")
    if len(mt):
        for reg in ("all", "below capacity (60%, 90%)", "overload (110%, 130%)"):
            d = mt[mt.regime == reg].sort_values("deadline_success_pct", ascending=False)
            out.append(f"### Main comparison: {reg} ({int(d.n_scenarios.max())} grid scenarios x 10 seeds)\n")
            out.append(md(d, ["algorithm", lambda r: fmt(r.deadline_success_pct), lambda r: fmt(r.oracle_gap_pp, 1, True),
                              lambda r: fmt(r.get("gap_vs_oracle_wrapped_pp", np.nan), 1, True),
                              lambda r: fmt(r.p99_latency_ms, 0), lambda r: fmt(r.drop_rate_pct),
                              lambda r: fmt(r.expired_pct), lambda r: fmt(r.late_pct),
                              lambda r: fmt(r.telemetry_Bps_per_ingress, 0)],
                          ["Algorithm", "Deadline success (%)", "Oracle gap (pp)", "Gap to oracle + wrapper (pp)",
                           "p99 latency (ms)", "Drop rate (%)", "Expired (%)", "Late (%)",
                           "Telemetry B/s per ingress"]))
            out.append("")
    pv = _r("paired_vs_v6.csv")
    if len(pv):
        out.append("### v6 against each rival, scenario by scenario (paired 95% CI over seeds)\n")
        out.append(md(pv, ["rival", "regime", lambda r: fmt(r.v6_minus_rival_pp_mean, 1, True), "v6_better", "same",
                           "v6_worse", "n_scenarios"],
                      ["Rival", "Regime", "v6 − rival (pp, mean)", "v6 better", "same", "v6 worse", "scenarios"]))
        out.append("")
    dl = _r("delay_sensitivity.csv")
    if len(dl):
        out.append("### Telemetry delay: deadline success (%) at 0 / 50 / 200 / 1000 ms (steady)\n")
        rows = []
        for L in sorted(set(dl.load)):
            for a in st.MAIN_RULES:
                g = dl[(dl.load == L) & (dl.alias == a)].set_index("delay_ms")
                if not len(g):
                    continue
                vals = [g.success.get(v, np.nan) for v in (0, 50, 200, 1000)]
                rows.append({"load": f"{int(L * 100)}%", "alg": st.SHORT[a], **{f"d{v}": fmt(x) for v, x in
                                                                                 zip((0, 50, 200, 1000), vals)},
                             "drop": fmt(vals[3] - vals[0], 1, True) if not np.isnan(vals[0]) else "–"})
        out.append(md(pd.DataFrame(rows), ["load", "alg", "d0", "d50", "d200", "d1000", "drop"],
                      ["Load", "Algorithm", "0 ms", "50 ms", "200 ms", "1000 ms", "1000 − 0 ms (pp)"]))
        out.append("")
    pt = _r("traffic_patterns.csv")
    if len(pt):
        out.append("### Traffic patterns: deadline success (%) (50 ms telemetry delay)\n")
        rows = []
        for L in sorted(set(pt.load)):
            for a in st.MAIN_RULES:
                g = pt[(pt.load == L) & (pt.alias == a)].set_index("pattern")
                if not len(g):
                    continue
                rec = g.recovery_s.get("bursty", np.nan) if "recovery_s" in g else np.nan
                rows.append({"load": f"{int(L * 100)}%", "alg": st.SHORT[a],
                             **{p: fmt(g.success.get(p, np.nan)) for p in st.PATTERNS}, "rec": fmt(rec)})
        out.append(md(pd.DataFrame(rows), ["load", "alg", "steady", "bursty", "shifting", "rec"],
                      ["Load", "Algorithm", "Steady", "Bursty", "Shifting", "Recovery after a burst (s)"]))
        out.append("")
    te = _r("telemetry_efficiency.csv")
    if len(te):
        out.append("### Telemetry budget: deadline success (%) and realized bytes/s per ingress\n")
        rows = []
        for _, r in te.sort_values(["load", "alias", "bytes_per_s_per_ingress"]).iterrows():
            rows.append({"load": f"{int(r.load * 100)}%", "alg": st.SHORT.get(r.alias, r.alias), "budget": r.budget,
                         "succ": fmt(r.success), "ci": fmt(r.success_ci95), "bps": fmt(r.bytes_per_s_per_ingress, 0),
                         "aoi": fmt(r.aoi_mean_s, 2)})
        out.append(md(pd.DataFrame(rows), ["load", "alg", "budget", "succ", "ci", "bps", "aoi"],
                      ["Load", "Algorithm", "Budget", "Success (%)", "± 95% CI", "B/s per ingress",
                       "Mean info age (s)"]))
        out.append("")
    ad = _r("admission_comparison.csv")
    if len(ad):
        out.append("### Admission fairness: native vs the common rejection wrapper\n")
        rows = []
        for _, r in ad.iterrows():
            rows.append({"load": f"{int(r.load * 100)}%", "alg": r.algorithm, "kind": r.kind,
                         "nat": fmt(r.native_success), "wr": fmt(r.wrapped_success), "gain": fmt(r.gain_pp, 1, True),
                         "rej": fmt(r.wrapped_rejected if r.kind.startswith("routing") else r.native_rejected)})
        out.append(md(pd.DataFrame(rows), ["load", "alg", "kind", "nat", "wr", "gain", "rej"],
                      ["Load", "Algorithm", "Kind", "Native success (%)", "With wrapper (%)", "Gain (pp)",
                       "Rejected (%)"]))
        out.append("")
    ab = _r("ablation.csv")
    if len(ab):
        out.append("### Ablation: v6 minus v6-without-mechanism (pp; > 0 means the mechanism helps)\n")
        out.append(md(ab, ["pattern", lambda r: f"{int(r.load * 100)}%", "ablation",
                           lambda r: fmt(r.v6_minus_ablation_pp, 2, True), lambda r: fmt(r.ci95, 2), "verdict"],
                      ["Pattern", "Load", "Mechanism switched off", "v6 − ablation (pp)", "± 95% CI", "Verdict"]))
        out.append("")
    sc = _r("scalability.csv")
    if len(sc):
        out.append("### Scalability: deadline success (%) with 1 / 4 / 16 ingresses\n")
        rows = []
        for L in sorted(set(sc.load)):
            for a in st.MAIN_RULES:
                g = sc[(sc.load == L) & (sc.alias == a)].set_index("R")
                if len(g):
                    rows.append({"load": f"{int(L * 100)}%", "alg": st.SHORT[a],
                                 **{f"r{k}": fmt(g.success.get(k, np.nan)) for k in (1, 4, 16)}})
        out.append(md(pd.DataFrame(rows), ["load", "alg", "r1", "r4", "r16"],
                      ["Load", "Algorithm", "1 ingress", "4 ingresses", "16 ingresses"]))
        out.append("")
    fl = _r("failures.csv")
    if len(fl):
        out.append("### Failures and slowdowns (load 90%): success over the run, recovery after the event\n")
        out.append(md(fl, ["tag", lambda r: st.SHORT.get(r.alias, r.alias), lambda r: fmt(r.success),
                           lambda r: fmt(r.success_ci95), lambda r: fmt(r.get("recovery_s", np.nan)),
                           lambda r: fmt(r.get("impact_pp", np.nan), 1, True)],
                      ["Event", "Algorithm", "Success (%)", "± 95% CI", "Recovery (s)", "Impact during event (pp)"]))
        out.append("")
    cd = _r("capacity_deadline.csv")
    if len(cd):
        out.append("### Homogeneous sites and the relaxed deadline: deadline success (%)\n")
        rows = []
        for L in sorted(set(cd.load)):
            for a in st.MAIN_RULES:
                g = cd[(cd.load == L) & (cd.alias == a)]
                if not len(g):
                    continue
                def get(cap, dl):
                    x = g[(g.cap == cap) & (g.deadline == dl)].success
                    return fmt(x.iloc[0]) if len(x) else "–"
                rows.append({"load": f"{int(L * 100)}%", "alg": st.SHORT[a], "het": get("het", 300),
                             "hom": get("hom", 300), "rel": get("het", 500)})
        out.append(md(pd.DataFrame(rows), ["load", "alg", "het", "hom", "rel"],
                      ["Load", "Algorithm", "Heterogeneous, 300 ms", "Homogeneous, 300 ms", "Heterogeneous, 500 ms"]))
        out.append("")
    print("\n".join(out))


if __name__ == "__main__":
    main()
