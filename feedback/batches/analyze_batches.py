"""Batches A and B of the evaluation of ours v6.1: the tables and the note.

    python3 feedback/batches/analyze_batches.py        batch_A.csv, batch_B.csv -> tables/*.csv and feedback/batches.md

Rules of the analysis, fixed at the freeze (FREEZE_v6.1.md) and applied here without exception:
  * deadline success = frames answered within the deadline / all frames generated after the warm-up
    (a frame dropped at the ingress, discarded at a site or answered late is a miss);
  * differences are paired by seed, with a 95% interval from Student's t (4 degrees of freedom on five seeds);
  * every scenario is reported, losses included, with the rejected share next to success;
  * no scenario, rule or seed is removed.
Nothing here reads or changes catsim/. The note is rebuilt from the result files each time.
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TABLES = os.path.join(HERE, "tables")
NOTE = os.path.join(os.path.dirname(HERE), "batches.md")

NET = {"beirut": "Beirut", "eight": "8 sites", "new": "New"}
OURS = "ours_v61"
A_RIVALS = [                                  # (rule, column title, what the comparison shows)
    ("wrr+adm61", "RR + matched adm.", "the gain over no steering, at equal telemetry and equal chance to drop"),
    ("static_deadline+adm61", "Static + matched adm.",
     "planned: the gain over the best split that needs no reports; in fact the capacity split again (see above)"),
    ("ours_v61@KAPPA=0", "v6.1 no penalty", "what the backlog penalty adds"),
    ("ours_v61@allow_drop=False", "v6.1 no drop", "what admission adds to v6.1's routing"),
    ("ours_v6", "v6 (frozen)", "what the three changes of v6.1 did"),
    ("wrr", "Round-robin", "the floor"),
]
NODROP, RR, RRADM, STATIC = "ours_v61@allow_drop=False", "wrr", "wrr+adm61", "static_deadline+adm61"
A_SUMMARY = [(OURS, r, f"v6.1 − {t}", w) for r, t, w in A_RIVALS] + [
    (NODROP, RR, "v6.1 no drop − Round-robin", "what v6.1's routing adds when nothing may be dropped")]
A_COLS = [(OURS, "v6.1")] + [(r, t) for r, t, _ in A_RIVALS]
B_COLS = [("ours_v61", "v6.1 (drop counter)"), ("ours_v6", "v6 (own share)"),
          ("wrr+adm61", "RR + adm. (drop counter)"), ("wrr+adm", "RR + adm. (own share)")]
B_PAIRS = [("ours_v61", "ours_v6", "v6.1 − v6"), ("wrr+adm61", "wrr+adm", "RR + adm.: drop counter − own share"),
           ("ours_v61", "wrr+adm61", "v6.1 − RR + matched adm.")]
SHORT = {
    "main": "Main scenario (load 85%)", "load=95": "Load 95%", "O_110": "Load 110%", "O_130": "Load 130%",
    "O_150": "Load 150%", "O_burst": "Burst: 85%, then 140% for 20 s", "O_surge": "Ingress A doubles for 50 s",
    "server_fail_recover": "Hamra loses 1 of 2 servers for 50 s", "O_dc_half": "DC loses 4 of 8 servers for 60 s",
    "wrong_weights": "Wrong weights (DC has 6, rules told 8)",
    "N_85": "Load 85%", "N_95": "Load 95%", "N_115": "Load 115%", "N_130": "Load 130%",
    "N_burst": "Burst: 85%, then 140% for 20 s", "N_fail": "Regional DC loses 2 of 6 servers for 50 s",
    "N_130_stagger": "Load 130%, staggered reports", "N_surge": "Load 95%, largest ingress doubles for 50 s",
    "B_130_equal": "Load 130%, equal shares", "B_130_stagger": "Load 130%, staggered reports",
    "B_130_loss": "Load 130%, 30% of reports lost", "O_130_W1": "Load 130%, reports every 1 s",
}
B_SHORT = {"O_130": "Load 130%, shares 40/30/20/10%"}
# Kind of scenario. This grouping was made AFTER the first results (it is descriptive, not part of the freeze).
KINDS = [
    ("Capacity is not what was configured (failures, wrong weights)",
     {"server_fail_recover", "O_dc_half", "wrong_weights", "N_fail"}),
    ("Bursts and a surge", {"O_burst", "O_surge", "N_burst"}),                      # + the bursty 8-site scenarios
    ("Steady load, 95% and above", {"load=95", "O_110", "O_130", "O_150", "N_95", "N_115", "N_130"}),
    ("Steady load below capacity (85% to 90%)", {"main", "N_85"}),
]


def kind_of(net, key):
    if net == "eight":
        m = key.split("_")                                     # L<load>_d50_<pattern>_...
        load, pattern = int(m[0][1:]), m[2]
        if pattern == "bursty":
            return KINDS[1][0]
        return KINDS[2][0] if load >= 95 else KINDS[3][0]
    for name, keys in KINDS:
        if key in keys:
            return name
    raise KeyError((net, key))


# ------------------------------------------------------------------------------------------- helpers
def load(batch):
    path = os.path.join(HERE, f"batch_{batch}.csv")
    if not os.path.exists(path):
        return None, None
    df = pd.read_csv(path, float_precision="round_trip")
    df["lost"] = df["expired"] + df["late"]                    # discarded at a site or answered late
    mpath = os.path.join(HERE, f"batch_{batch}_manifest.json")
    man = json.load(open(mpath, encoding="utf-8")) if os.path.exists(mpath) else {}
    return df, man


def scenarios_of(df):
    """[(net, scenario)] in the order of the plan."""
    return list(dict.fromkeys(zip(df["net"], df["scenario"])))


def name_of(df, net, key, batch):
    lab = (B_SHORT.get(key) if batch == "B" else None) or SHORT.get(key)
    if lab is None:
        lab = df[(df.net == net) & (df.scenario == key)]["label"].iloc[0]
        lab = lab.replace(", reports every 2 s", "")
    pilot = int(df[(df.net == net) & (df.scenario == key)]["pilot_scenario"].iloc[0])
    return lab + (" *" if pilot else "")


def t_half(d):
    d = np.asarray(d, float)
    n = len(d)
    if n < 2:
        return float("nan")
    return float(stats.t.ppf(0.975, n - 1) * d.std(ddof=1) / math.sqrt(n))


def paired(df, a, b, col="success"):
    """a − b, paired by seed, for every scenario: DataFrame(net, scenario, diff, half, lo, hi, n, verdict)."""
    idx = ["net", "scenario", "seed"]
    pa = df[df.rule == a].set_index(idx)[col].sort_index()
    pb = df[df.rule == b].set_index(idx)[col].sort_index()
    have = set(zip(pa.index.get_level_values(0), pa.index.get_level_values(1))) & set(
        zip(pb.index.get_level_values(0), pb.index.get_level_values(1)))
    rows = []
    for net, key in scenarios_of(df):
        if (net, key) not in have:
            continue
        xa, xb = pa.loc[(net, key)], pb.loc[(net, key)]
        assert list(xa.index) == list(xb.index), (net, key, a, b)          # the same seeds on both sides
        d = (xa - xb).to_numpy()
        m, h = float(d.mean()), t_half(d)
        if np.all(d == 0):
            verdict = "same"
        elif m - h > 0:
            verdict = "ahead"
        elif m + h < 0:
            verdict = "behind"
        else:
            verdict = "unclear"
        rows.append(dict(net=net, scenario=key, a=a, b=b, measure=col, diff=m, half=h, lo=m - h, hi=m + h, n=len(d),
                         verdict=verdict, by_seed=" ".join(f"{x:+.3f}" for x in d)))
    return pd.DataFrame(rows)


def pooled(df, a, b, keys, col="success"):
    """Mean over the given scenarios of a − b: per seed first (mean over scenarios), then the interval over seeds."""
    idx = ["net", "scenario", "seed"]
    pa = df[df.rule == a].set_index(idx)[col].sort_index()
    pb = df[df.rule == b].set_index(idx)[col].sort_index()
    d = (pa - pb).dropna().reset_index()
    d = d[[k in keys for k in zip(d["net"], d["scenario"])]]
    if d.empty:
        return float("nan"), float("nan"), 0
    per_seed = d.groupby("seed")[col].mean().to_numpy()
    return float(per_seed.mean()), t_half(per_seed), len(keys)


def fmt_diff(m, h, verdict=None):
    if verdict == "same":
        return "same runs"
    s = f"{m:+.1f} ± {h:.1f}"
    return f"**{s}**" if verdict in ("ahead", "behind") else s


def md_table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def checks(df, man, batch, expected_rules):
    """[(what, ok, detail)]"""
    out = []
    seeds = sorted(df.seed.unique())
    n_sc = len(scenarios_of(df))
    want = n_sc * len(expected_rules) * len(seeds)
    out.append((f"Batch {batch}: every run of the plan is there", len(df) == want and set(df.rule) == set(expected_rules),
                f"{len(df)} of {want} runs ({n_sc} scenarios × {len(expected_rules)} rules × {len(seeds)} seeds)"))
    per = df.groupby(["net", "scenario", "rule"]).seed.apply(lambda s: tuple(sorted(s)))
    out.append((f"Batch {batch}: every scenario and rule has the same seeds", per.nunique() == 1,
                f"seeds {seeds[0]} to {seeds[-1]}"))
    add = (df.n_success + df.n_late + df.n_expired + df.n_rejected == df.frames).all()
    out.append((f"Batch {batch}: every frame ends once (on time, late, discarded or rejected)", bool(add),
                f"{int(df.frames.sum()):,} frames in {len(df)} runs"))
    same = df.groupby(["net", "scenario", "seed"]).frames.nunique().max() == 1
    out.append((f"Batch {batch}: every rule saw the same frames (same scenario, same seed)", bool(same),
                "needed for paired differences"))
    bad = bool(df[["success", "rejected", "expired", "late"]].isna().any().any())
    out.append((f"Batch {batch}: no missing value", not bad, ""))
    if man:
        ok = man.get("frozen_files_changed") == [] and man.get("runs") == len(df)
        out.append((f"Batch {batch}: run on the frozen code", ok,
                    f"{man.get('frozen_files_checked')} frozen files match FREEZE_v6.1.md; Python {man.get('python')}, "
                    f"numpy {man.get('numpy')}, scipy {man.get('scipy')}; finished {man.get('finished')}"))
    return out


def overlap_check(A, B):
    cols = ["frames", "n_success", "n_late", "n_expired", "n_rejected", "success", "rejected", "expired", "late",
            "bytes_per_s_per_ingress"]
    idx = ["net", "scenario", "rule", "seed"]
    m = A.set_index(idx)[cols].join(B.set_index(idx)[cols], how="inner", lsuffix="_a", rsuffix="_b")
    equal = all((m[c + "_a"] == m[c + "_b"]).all() for c in cols)
    return ("Runs that Batch A and Batch B share give the same numbers (the recorder of Batch B changes nothing)",
            bool(equal) and len(m) > 0, f"{len(m)} shared runs")


# ------------------------------------------------------------------------------------------- Batch A
def batch_a(A):
    L = []
    scs = scenarios_of(A)
    seeds = sorted(A.seed.unique())
    mean = A.groupby(["net", "scenario", "rule"], sort=False)[["success", "rejected", "expired", "late"]].mean()
    mean.reset_index().to_csv(os.path.join(TABLES, "A_success.csv"), index=False)
    P = {r: paired(A, OURS, r) for r, _, _ in A_RIVALS}
    PR = {r: paired(A, OURS, r, "rejected") for r, _, _ in A_RIVALS}
    PL = {r: paired(A, OURS, r, "lost") for r, _, _ in A_RIVALS}
    P[(NODROP, RR)] = paired(A, NODROP, RR)                    # routing alone
    PS = paired(A, STATIC, RRADM)                              # is the static split a different baseline?
    pd.concat([P[r] for r, _, _ in A_RIVALS] + list(PR.values()) + list(PL.values()) + [P[(NODROP, RR)], PS]).to_csv(
        os.path.join(TABLES, "A_paired.csv"), index=False)

    L.append("## Batch A: where does the gain come from?\n")
    L.append(f"- {len(scs)} scenarios × {A.rule.nunique()} rules × {len(seeds)} seeds = {len(A)} runs.")
    L.append("- \\* = pilot scenario: v6.1's settings were chosen on it, with other seeds (101 to 105).")
    L.append("- Every other Beirut scenario, the 8-site network and the new network took no part in any choice.\n")
    L.append("**Table A1. Deadline success, % (rejected share, % in brackets). Mean of five seeds.**\n")
    rows = []
    for net, key in scs:
        row = [NET[net], name_of(A, net, key, "A")]
        for r, _ in A_COLS:
            v = mean.loc[(net, key, r)]
            row.append(f"{v.success:.1f} ({v.rejected:.1f})")
        rows.append(row)
    L.append(md_table(["Network", "Scenario"] + [t for _, t in A_COLS], rows))
    L.append("\n- Rejected = dropped at the ingress. Round-robin and \"v6.1 no drop\" never drop.")
    L.append("- The rest of the misses are frames discarded at a site or answered late (in `tables/A_success.csv`).\n")

    L.append("**Table A2. v6.1 minus each rule: difference in success, points, paired by seed, with the 95% "
             "interval. Bold = the interval does not contain 0.**\n")
    rows = []
    for net, key in scs:
        row = [NET[net], name_of(A, net, key, "A")]
        for r, _, _ in A_RIVALS:
            p = P[r][(P[r].net == net) & (P[r].scenario == key)].iloc[0]
            row.append(fmt_diff(p["diff"], p["half"], p["verdict"]))
        rows.append(row)
    L.append(md_table(["Network", "Scenario"] + ["− " + t for _, t, _ in A_RIVALS], rows))
    L.append("\n- Positive = v6.1 is ahead. \"same runs\" = the two rules gave the same result in every seed.\n")

    # ---- the static split is the capacity split
    L.append("**The static split is not a separate baseline (found after the runs).**\n")
    same_by_net = {n: (int((PS[PS.net == n].verdict == "same").sum()), int((PS.net == n).sum())) for n in NET
                   if (PS.net == n).any()}
    L.append("- \"Static + matched admission\" gave the same runs as \"RR + matched admission\" in " +
             ", ".join(f"{a} of {b} {NET[n]} scenarios" for n, (a, b) in same_by_net.items()) + ".")
    other = PS[PS.verdict != "same"]
    if len(other):
        L.append(f"- In the other {len(other)} scenarios the two differ by at most {other['diff'].abs().max():.1f} "
                 f"points of success, and never clearly ({int((other.verdict == 'unclear').sum())} of {len(other)} "
                 "intervals contain 0).")
    sp = os.path.join(TABLES, "static_shares.csv")
    if os.path.exists(sp):
        st = pd.read_csv(sp)
        if st.every_ingress_uses_capacity_shares.all():
            L.append("- Reason: on all three networks the frozen static split uses exactly the capacity shares, at "
                     "every ingress (`check_static.py`, `tables/static_shares.csv`).")
            L.append("- Its design load is 95% and no site may go above 95%: every site would have to sit at exactly "
                     "95%, which the 1% grid cannot do (" +
                     ", ".join(f"{NET[r.net]}: {r.pieces_that_fit} of {r.pieces_needed} pieces fit"
                               for r in st.itertuples()) + "), so the rule falls back to the capacity shares.")
    L.append("- So it is round-robin with another send order. The column is kept (it was frozen), but it does "
             "**not** show \"the gain over the best split that needs no reports\".")
    L.append("- On the new network, where the largest site is far, a static split that looks at the deadline was "
             "never tested.\n")

    # ---- the primary comparison in detail
    L.append("**Table A2b. The primary comparison in detail: v6.1 against RR + matched admission. Shares in % of "
             "all frames; differences in points, paired by seed.**\n")
    rows = []
    for net, key in scs:
        a, b = mean.loc[(net, key, OURS)], mean.loc[(net, key, RRADM)]
        ps, pr, pl = (x[RRADM][(x[RRADM].net == net) & (x[RRADM].scenario == key)].iloc[0] for x in (P, PR, PL))
        rows.append([NET[net], name_of(A, net, key, "A"), fmt_diff(ps["diff"], ps["half"], ps["verdict"]),
                     f"{a.rejected:.1f}", f"{b.rejected:.1f}", fmt_diff(pr["diff"], pr["half"], pr["verdict"]),
                     f"{a.expired + a.late:.1f}", f"{b.expired + b.late:.1f}",
                     fmt_diff(pl["diff"], pl["half"], pl["verdict"])])
    L.append(md_table(["Network", "Scenario", "Success: difference", "Rejected: v6.1", "Rejected: RR + adm.",
                       "Rejected: difference", "Late or discarded: v6.1", "Late or discarded: RR + adm.",
                       "Late or discarded: difference"], rows))
    L.append("\n- Late or discarded = admitted, then discarded at a site or answered after the deadline.")
    L.append("- Success difference = −(rejected difference + late-or-discarded difference).")
    L.append("- \"Matched\" admission = the same estimate from the same reports, and the same right to drop. It "
             "is **not** the same amount dropped: the wrapper drops what exceeds 95% of the configured capacity; "
             "v6.1 starts at 90% of the measured capacity and re-plans on a burst.\n")

    # ---- routing alone
    L.append("**Table A6. Routing alone: v6.1 without dropping against round-robin (neither drops). Success, %, and "
             "the paired difference.**\n")
    rows = []
    for net, key in scs:
        p = P[(NODROP, RR)]
        p = p[(p.net == net) & (p.scenario == key)].iloc[0]
        rows.append([NET[net], name_of(A, net, key, "A"), f"{mean.loc[(net, key, NODROP)].success:.1f}",
                     f"{mean.loc[(net, key, RR)].success:.1f}", fmt_diff(p["diff"], p["half"], p["verdict"])])
    L.append(md_table(["Network", "Scenario", "v6.1 no drop", "Round-robin", "Difference"], rows))
    L.append("")

    # ---- summary by comparison
    groups = [("All scenarios", scs), ("Pilot scenarios", [k for k in scs if int(
                  A[(A.net == k[0]) & (A.scenario == k[1])].pilot_scenario.iloc[0])]),
              ("Other scenarios", [k for k in scs if not int(
                  A[(A.net == k[0]) & (A.scenario == k[1])].pilot_scenario.iloc[0])])]
    groups += [(NET[n], [k for k in scs if k[0] == n]) for n in NET if any(k[0] == n for k in scs)]
    L.append("**Table A3. In how many scenarios is the first rule clearly ahead, clearly behind, or neither?**\n")
    rows, summ = [], []
    for a, r, title, what in A_SUMMARY:
        p = P[r] if a == OURS else P[(a, r)]
        cnt = p.verdict.value_counts()
        m, h, _ = pooled(A, a, r, set(scs))
        rows.append([title, int(cnt.get("ahead", 0)), int(cnt.get("behind", 0)), int(cnt.get("unclear", 0)),
                     int(cnt.get("same", 0)), f"{m:+.1f} ± {h:.1f}", what])
        for gname, keys in groups:
            pg = p[[k in set(keys) for k in zip(p.net, p.scenario)]]
            c = pg.verdict.value_counts()
            gm, gh, _ = pooled(A, a, r, set(keys))
            summ.append(dict(comparison=f"{a} - {r}", group=gname, scenarios=len(keys),
                             ahead=int(c.get("ahead", 0)), behind=int(c.get("behind", 0)),
                             unclear=int(c.get("unclear", 0)), same=int(c.get("same", 0)), mean_diff=gm, half=gh))
    summ = pd.DataFrame(summ)
    summ.to_csv(os.path.join(TABLES, "A_summary.csv"), index=False)
    L.append(md_table(["Comparison", "Clearly ahead", "Clearly behind", "No clear difference", "Same runs",
                       f"Mean difference over the {len(scs)} scenarios", "What it shows"], rows))
    L.append("\n- Mean difference: averaged over the scenarios inside each seed, then the 95% interval over the seeds.\n")

    L.append("**Table A4. The same mean difference (points), by group of scenarios.**\n")
    rows = []
    for a, r, title, _ in A_SUMMARY:
        row = [title]
        for gname, keys in groups:
            s = summ[(summ.comparison == f"{a} - {r}") & (summ.group == gname)].iloc[0]
            row.append(f"{s.mean_diff:+.1f} ± {s.half:.1f}")
        rows.append(row)
    L.append(md_table(["Comparison"] + [f"{g} ({len(k)})" for g, k in groups], rows))

    L.append("\n**Table A5. Mean deadline success, %, by group of scenarios (mean of the scenario means).**\n")
    rows = []
    for r, t in A_COLS:
        row = [t]
        for gname, keys in groups:
            row.append(f"{np.mean([mean.loc[(n, k, r)].success for n, k in keys]):.1f}")
        rows.append(row)
    L.append(md_table(["Rule"] + [f"{g} ({len(k)})" for g, k in groups], rows))
    L.append("")

    # ---- every scenario where v6.1 is clearly behind something
    lost = []
    for r, t, _ in A_RIVALS:
        for _, p in P[r].iterrows():
            if p["verdict"] == "behind":
                lost.append((NET[p["net"]], name_of(A, p["net"], p["scenario"], "A"), t, p["diff"], p["half"]))
    L.append("**Where v6.1 is clearly behind (every case, none left out).**\n")
    if lost:
        for net, sc, t, d, h in lost:
            L.append(f"- {net}, {sc}: {d:+.1f} ± {h:.1f} points against {t}.")
    else:
        L.append("- No scenario.")
    pr_ = P[(NODROP, RR)]
    for _, p in pr_[pr_.verdict == "behind"].iterrows():
        L.append(f"- Routing alone (v6.1 no drop) is clearly behind round-robin on {NET[p['net']]}, "
                 f"{name_of(A, p['net'], p['scenario'], 'A')}: {p['diff']:+.1f} ± {p['half']:.1f} points.")
    n_int = sum(len(P[r][P[r].verdict != "same"]) for r, _, _ in A_RIVALS)
    L.append(f"\n- Caution: Table A2 holds {n_int} intervals at 95%. About {0.05 * n_int:.0f} of them would leave out "
             "0 by chance alone, so a single bold cell is weak evidence. No correction was fixed at the freeze; "
             "none is applied.")
    L.append("- Five seeds give wide intervals. Seeds 306 to 310 are still unused.\n")
    return L, P, summ, mean


# ------------------------------------------------------------------------------------------- added after the freeze
def addendum(A):
    """Round-robin + admission with the settings chosen on pilot seeds (feedback/batches/addendum.py), against v6.1."""
    xp, sp = os.path.join(HERE, "batch_A_added.csv"), os.path.join(HERE, "addendum_settings.json")
    if not (os.path.exists(xp) and os.path.exists(sp)):
        return [], []
    X = pd.read_csv(xp, float_precision="round_trip")
    X["lost"] = X["expired"] + X["late"]
    st = json.load(open(sp, encoding="utf-8"))
    u = st["admission"]["chosen"]
    sm = st.get("smoothing", {})
    added = [(st["admission"]["rule"], f"RR + adm. at {u:.2f}")]
    if sm.get("added"):
        added.append((sm["rule"], f"RR + adm. at {u:.2f}, no smoothing" if sm["chosen"] == 1.0 else
                      f"RR + adm. at {u:.2f}, weight {sm['chosen']:g}"))
    final, final_name = added[-1]
    old = RRADM
    scs = scenarios_of(A)
    n_seeds = A.seed.nunique()
    ck = []
    ok = all(len(X[X.rule == r]) == len(scs) * n_seeds and set(X[X.rule == r].seed) == set(A.seed) for r, _ in added)
    ck.append(("Added runs: every scenario and seed is there", ok and set(X.rule) == {r for r, _ in added},
               f"{len(X)} runs: " + ", ".join(f"`{r}`" for r, _ in added)))
    fa = A[A.rule == OURS].set_index(["net", "scenario", "seed"]).frames.sort_index()
    same = all((fa == X[X.rule == r].set_index(["net", "scenario", "seed"]).frames.sort_index()).all() for r, _ in added)
    ck.append(("Added runs: the same frames as Batch A (same scenario, same seed)", bool(same), ""))
    ck.append(("Added runs: every frame ends once", bool(
        (X.n_success + X.n_late + X.n_expired + X.n_rejected == X.frames).all()), ""))
    D = pd.concat([A, X], ignore_index=True)
    mean = D.groupby(["net", "scenario", "rule"], sort=False)[
        ["success", "rejected", "lost", "bytes_per_s_per_ingress"]].mean()
    P = {r: paired(D, OURS, r) for r in [old] + [r for r, _ in added]}
    pd.concat(list(P.values()) + [paired(D, OURS, final, "rejected"), paired(D, OURS, final, "lost"),
                                  paired(D, final, old)]).to_csv(os.path.join(TABLES, "A_added_paired.csv"), index=False)
    nets = [n for n in NET if n in st["admission"]["by_network"]]

    L = ["## Added after the freeze: is the gain steering, or the way the baseline drops?\n"]
    L.append("- **Everything in this section was added after the freeze of 15 Nov 2026 and after the first results "
             "of Batch A.** The frozen comparisons above are unchanged.")
    L.append("- Why: \"RR + matched admission\" admits 95% of the configured capacity and smooths its estimate "
             "slowly. v6.1 admitted about 91% in steady overload, follows a clear rise at once and checks for bursts. "
             "So v6.1's lead could come from how the baseline drops, not from steering.")
    L.append("- What was added: the same wrapper with two of its own parameters changed (`wrr+adm61@U=u,EWMA=e`), "
             "and the static split at other design loads. The frozen code already has these parameters. No frozen "
             "file changed.")
    L.append("- How the settings were chosen: on pilot seeds 101 to 105 only, on the 22 scenarios of Batch A, by "
             "rules written (and committed) before the runs they decide (`feedback/batches/addendum.py`). v6.1 was "
             "not run and not looked at: each baseline was tuned for its own best result.")
    L.append("- Each chosen setting was then run once on seeds 301 to 305.\n")

    L.append("**Table F1. Pilot seeds: mean deadline success of round-robin + admission, %, by admission level "
             "(smoothing as frozen).**\n")
    rows = []
    for lev in st["admission"]["levels"]:
        mark = " (frozen)" if float(lev) == 0.95 else (" **(chosen)**" if float(lev) == u else "")
        rows.append([f"{float(lev):.2f}{mark}", f"{st['admission']['levels'][lev]:.1f}"] +
                    [f"{st['admission']['by_network'][n][lev]:.1f}" for n in nets])
    L.append(md_table(["Admission level", "All 22 scenarios"] + [NET[n] for n in nets], rows))
    L.append("\n- Rule: one level for all networks, the one with the highest mean over the 22 scenarios.\n")
    if sm:
        L.append(f"**Table F2. Pilot seeds: the same at level {u:.2f}, by the weight of the newest report in the "
                 "wrapper's estimate.**\n")
        rows = []
        for w in sm["weights"]:
            mark = " (frozen)" if float(w) == 0.3 else ""
            mark += " **(chosen)**" if float(w) == sm["chosen"] else ""
            rows.append([f"{float(w):.1f}{mark}", f"{sm['weights'][w]:.1f}"] +
                        [f"{sm['by_network'][n][w]:.1f}" for n in nets])
        L.append(md_table(["Weight of the newest report", "All 22 scenarios"] + [NET[n] for n in nets], rows))
        L.append("\n- Weight 1.0 = no smoothing: the wrapper follows each round of reports as it is.")
        L.append("- This second step was decided after the level 0.90 had been run on seeds 301 to 305, and before "
                 "any run with another smoothing.")
        b = "beirut"
        if b in nets and max(st["admission"]["by_network"][b], key=st["admission"]["by_network"][b].get) == f"{u:g}" \
                and max(sm["by_network"][b], key=sm["by_network"][b].get) == f"{sm['chosen']:g}":
            L.append("- The baseline was tuned on all three networks, v6.1 on Beirut only. Tuned on Beirut alone, "
                     "the same two settings win.")
        L.append("")
    L.append("**Table F3. Pilot seeds: mean deadline success of the static split + matched admission, %, by design "
             "load.**\n")
    loads = list(next(iter(st["static"].values()))["loads"])
    rows = [[f"{float(x):.2f}" + (" (frozen = capacity shares)" if float(x) == 0.95 else "")] +
            [f"{st['static'][n]['loads'][x]:.1f}" for n in nets] for x in loads]
    L.append(md_table(["Design load"] + [NET[n] for n in nets], rows))
    if all(not st["static"][n]["added"] for n in nets):
        L.append("\n- On all three networks the capacity shares are the best static split of this family. Nothing is "
                 "added. The frozen static baseline stays, and it is round-robin (see above).\n")
    else:
        L.append("\n- Chosen per network: " + ", ".join(f"{NET[n]} {st['static'][n]['chosen']:.2f}" for n in nets)
                 + ".\n")

    cols = [(old, "RR + adm. at 0.95 (frozen)")] + [(r, t + " (added)") for r, t in added]
    L.append(f"**Table F4. Seeds {A.seed.min()} to {A.seed.max()}: deadline success, % (rejected, %). Mean of "
             f"{n_seeds} seeds.**\n")
    rows = []
    for net, key in scs:
        rows.append([NET[net], name_of(A, net, key, "A")] +
                    [f"{mean.loc[(net, key, r)].success:.1f} ({mean.loc[(net, key, r)].rejected:.1f})"
                     for r in [OURS] + [c for c, _ in cols]])
    L.append(md_table(["Network", "Scenario", "v6.1"] + [t for _, t in cols], rows))
    L.append("")
    L.append("**Table F5. v6.1 minus each of them: difference in success, points, paired by seed, 95% interval. "
             "Bold = the interval does not contain 0.**\n")
    rows = []
    for net, key in scs:
        row = [NET[net], name_of(A, net, key, "A")]
        for r, _ in cols:
            g = P[r][(P[r].net == net) & (P[r].scenario == key)].iloc[0]
            row.append(fmt_diff(g["diff"], g["half"], g["verdict"]))
        rows.append(row)
    L.append(md_table(["Network", "Scenario"] + ["− " + t for _, t in cols], rows))
    L.append("")

    pil = lambda k: int(A[(A.net == k[0]) & (A.scenario == k[1])].pilot_scenario.iloc[0])
    groups = [("All scenarios", scs), ("Pilot scenarios", [k for k in scs if pil(k)]),
              ("Other scenarios", [k for k in scs if not pil(k)])]
    groups += [(NET[n], [k for k in scs if k[0] == n]) for n in NET if any(k[0] == n for k in scs)]
    kinds = [(name, [k for k in scs if kind_of(*k) == name]) for name, _ in KINDS]
    Pf = P[final]

    def table(gs, title):
        rows, out = [], []
        for gname, keys in gs:
            ks = set(keys)
            c = Pf[[k in ks for k in zip(Pf.net, Pf.scenario)]].verdict.value_counts()
            row = [gname, len(keys)]
            rec = dict(group=gname, scenarios=len(keys))
            for r, t in reversed(cols):
                m, h, _ = pooled(D, OURS, r, ks)
                row.append(f"{m:+.1f} ± {h:.1f}")
                rec[f"v61_minus[{r}]"], rec[f"half[{r}]"] = m, h
                if r == final:
                    row += [int(c.get("ahead", 0)), int(c.get("behind", 0)),
                            int(c.get("unclear", 0)) + int(c.get("same", 0))]
                    rec.update(ahead=int(c.get("ahead", 0)), behind=int(c.get("behind", 0)),
                               unclear_or_same=int(c.get("unclear", 0)) + int(c.get("same", 0)))
            rows.append(row)
            out.append(rec)
        head = ["Scenarios", "How many"]
        for r, t in reversed(cols):
            head.append("v6.1 − " + t)
            if r == final:
                head += ["v6.1 clearly ahead", "v6.1 clearly behind", "Not clear or same"]
        L.append(title + "\n")
        L.append(md_table(head, rows))
        L.append("")
        return out

    s1 = table(groups, "**Table F6. Mean differences in success, points, by group of scenarios. The counts are "
                       f"against {final_name}.**")
    s2 = table(kinds, "**Table F7. The same, by kind of scenario. The kinds were defined after the results: this "
                      "table describes, it was not planned.**")
    pd.DataFrame(s1 + s2).to_csv(os.path.join(TABLES, "A_added_summary.csv"), index=False)
    ms = lambda r: np.mean([mean.loc[(n, k, r)].success for n, k in scs])
    L.append(f"- Mean success over the {len(scs)} scenarios: v6.1 {ms(OURS):.1f}%; " +
             "; ".join(f"{t} {ms(r):.1f}%" for r, t in reversed(cols)) + f"; round-robin {ms(RR):.1f}%.")
    for _, p in Pf[Pf.verdict == "behind"].iterrows():
        L.append(f"- v6.1 is clearly behind {final_name} on {NET[p['net']]}, "
                 f"{name_of(A, p['net'], p['scenario'], 'A')}: {p['diff']:+.1f} ± {p['half']:.1f} points.")
    by = lambda r, n: np.mean([mean.loc[(nn, k, r)].bytes_per_s_per_ingress for nn, k in scs if nn == n])
    L.append("- Telemetry, bytes per second per ingress (v6.1 / " + final_name + "): " +
             ", ".join(f"{NET[n]} {by(OURS, n):.1f} / {by(final, n):.1f}" for n in nets) + ".")
    L.append("")
    return L, ck


# ------------------------------------------------------------------------------------------- Batch B
def _ing_values(df, col):
    """Every per-ingress value of a JSON list column, as one flat array."""
    return np.array([x for s in df[col] for x in json.loads(s)], float)


def batch_b(B):
    L = []
    scs = scenarios_of(B)
    seeds = sorted(B.seed.unique())
    cols = ["success", "rejected", "expired", "late", "est_min", "est_max", "share_min", "share_max", "spread_mean",
            "spread_max", "admitted_over_capacity", "bytes_per_s_per_ingress", "echo_bytes_per_s_per_ingress"]
    mean = B.groupby(["net", "scenario", "rule"], sort=False)[cols].mean()
    mean.reset_index().to_csv(os.path.join(TABLES, "B_measures.csv"), index=False)
    P = {(a, b): paired(B, a, b) for a, b, _ in B_PAIRS}
    pd.concat(list(P.values())).to_csv(os.path.join(TABLES, "B_paired.csv"), index=False)

    L.append("## Batch B: does the estimate hold when ingresses differ?\n")
    L.append(f"- {len(scs)} scenarios × {B.rule.nunique()} rules × {len(seeds)} seeds = {len(B)} runs.")
    L.append("- Every scenario is in overload for at least part of the run: the estimate only matters while frames "
             "are dropped.")
    L.append("- Two pairs differ only in the estimate: v6.1 against v6 (v6.1 also has changes 2 and 3), and "
             "round-robin + admission with the drop counter against the same wrapper with its own drop share "
             "(nothing else differs).\n")

    L.append("**Table B1. Estimate of the offered traffic ÷ the truth: lowest ingress to highest ingress "
             "(1.00 = right). Mean of five seeds.**\n")
    rows = []
    for net, key in scs:
        row = [NET[net], name_of(B, net, key, "B")]
        for r, _ in B_COLS:
            v = mean.loc[(net, key, r)]
            row.append(f"{v.est_min:.2f} to {v.est_max:.2f}")
        rows.append(row)
    L.append(md_table(["Network", "Scenario"] + [t for _, t in B_COLS], rows))
    L.append("\n- Estimate = what the rule believes the total offered traffic is, each time it updates it. Truth = "
             "the frames really created in the W seconds before. Averaged over time, after the warm-up.\n")

    L.append("**Table B2. All ingresses of all runs: how far is the estimate from the truth?**\n")
    rows = []
    for r, t in B_COLS:
        x = _ing_values(B[B.rule == r], "est_by_ingress")
        rows.append([t, len(x), f"{x.min():.2f}", f"{np.median(x):.2f}", f"{x.max():.2f}",
                     f"{(np.abs(x - 1) <= 0.05).mean() * 100:.0f}%", f"{(np.abs(x - 1) <= 0.10).mean() * 100:.0f}%",
                     f"{(np.abs(x - 1) > 0.25).mean() * 100:.0f}%"])
    L.append(md_table(["Rule", "Ingress × run values", "Lowest", "Median", "Highest", "Within 5% of the truth",
                       "Within 10%", "More than 25% off"], rows))
    L.append("")

    L.append("**Table B3. Deadline success, % (rejected share, % in brackets). Mean of five seeds.**\n")
    rows = []
    for net, key in scs:
        row = [NET[net], name_of(B, net, key, "B")]
        for r, _ in B_COLS:
            v = mean.loc[(net, key, r)]
            row.append(f"{v.success:.1f} ({v.rejected:.1f})")
        rows.append(row)
    L.append(md_table(["Network", "Scenario"] + [t for _, t in B_COLS], rows))
    L.append("")

    L.append("**Table B4. Differences in success, points, paired by seed, with the 95% interval. Bold = the interval "
             "does not contain 0.**\n")
    rows = []
    for net, key in scs:
        row = [NET[net], name_of(B, net, key, "B")]
        for a, b, _ in B_PAIRS:
            p = P[(a, b)]
            p = p[(p.net == net) & (p.scenario == key)].iloc[0]
            row.append(fmt_diff(p["diff"], p["half"], p["verdict"]))
        rows.append(row)
    L.append(md_table(["Network", "Scenario"] + [t for _, _, t in B_PAIRS], rows))
    rows = []
    for a, b, t in B_PAIRS:
        c = P[(a, b)].verdict.value_counts()
        m, h, _ = pooled(B, a, b, set(scs))
        rows.append([t, int(c.get("ahead", 0)), int(c.get("behind", 0)), int(c.get("unclear", 0)),
                     int(c.get("same", 0)), f"{m:+.1f} ± {h:.1f}"])
    L.append("\n" + md_table(["Comparison", "Clearly ahead", "Clearly behind", "No clear difference", "Same runs",
                              f"Mean difference over the {len(scs)} scenarios"], rows))
    L.append("")

    L.append("**Table B5. Drop share of the ingresses: lowest ingress to highest ingress, % of the frames each was "
             "offered. Mean of five seeds.**\n")
    rows = []
    for net, key in scs:
        row = [NET[net], name_of(B, net, key, "B")]
        for r, _ in B_COLS:
            v = mean.loc[(net, key, r)]
            row.append(f"{v.share_min:.1f} to {v.share_max:.1f}")
        rows.append(row)
    L.append(md_table(["Network", "Scenario"] + [t for _, t in B_COLS], rows))
    L.append("\n- Whole run. Inside 5-second windows the shares differ more (`spread_mean`, `spread_max` in "
             "`tables/B_measures.csv`).\n")

    L.append("**Table B6. Admitted traffic ÷ configured capacity, and telemetry bytes per second per ingress. Mean of "
             "five seeds.**\n")
    rows = []
    for net, key in scs:
        row = [NET[net], name_of(B, net, key, "B")]
        for r, _ in B_COLS:
            row.append(f"{mean.loc[(net, key, r)].admitted_over_capacity:.2f}")
        b61, b6 = mean.loc[(net, key, "ours_v61")], mean.loc[(net, key, "ours_v6")]
        row += [f"{b61.bytes_per_s_per_ingress:.1f}", f"{b6.bytes_per_s_per_ingress:.1f}",
                f"{(b61.bytes_per_s_per_ingress / b6.bytes_per_s_per_ingress - 1) * 100:+.1f}%"]
        rows.append(row)
    L.append(md_table(["Network", "Scenario"] + ["Admitted: " + t for _, t in B_COLS] +
                      ["Bytes: v6.1", "Bytes: v6", "v6.1 over v6"], rows))
    L.append("\n- The admission wrapper aims at 0.95 of the configured capacity. v6.1 and v6 plan no site above 0.95 "
             "of its measured capacity.")
    L.append("- Bytes: reports (62 + 4 bytes each, + 2 for the drop counter) and the drop counts sent by the "
             "ingresses (2 bytes each). The wrapper with the drop counter costs the same bytes as v6.1's reports.\n")
    return L, P, mean


# ------------------------------------------------------------------------------------------- the note
def main():
    os.makedirs(TABLES, exist_ok=True)
    A, manA = load("A")
    B, manB = load("B")
    if A is None and B is None:
        sys.exit("no batch_A.csv or batch_B.csv next to this script: run run_batches.py first")
    ck = []
    if A is not None:
        ck += checks(A, manA, "A", [r for r, _ in A_COLS])
    if B is not None:
        ck += checks(B, manB, "B", [r for r, _ in B_COLS])
    if A is not None and B is not None:
        ck.append(overlap_check(A, B))
    ref = A if A is not None else B
    seeds = sorted(ref.seed.unique())
    L = [f"# Batches A and B: first pass on the evaluation seeds ({seeds[0]} to {seeds[-1]})\n"]
    L.append("- Evaluation of ours v6.1 as frozen on 15 Nov 2026 (tag `v6.1-frozen`, `FREEZE_v6.1.md`).")
    L.append("- The scenarios, the rules, the seeds and the rules of the analysis were fixed before any of these "
             "runs (`catsim/v61.py`).")
    L.append(f"- These are the first results on seeds {seeds[0]} to {seeds[-1]}. Nothing was changed after seeing "
             "them.")
    L.append("- This file is written by `feedback/batches/analyze_batches.py` from `feedback/batches/batch_A.csv` "
             "and `batch_B.csv`. Runner: `feedback/batches/run_batches.py`.\n")
    L.append("## How to read the numbers\n")
    L.append("- **Deadline success** = frames answered within 300 ms ÷ all frames generated after the warm-up.")
    L.append("- A frame dropped at the ingress, discarded at a site or answered late is a miss.")
    L.append("- **Difference** = v6.1 minus the other rule, seed by seed (same frames for both), then the mean and "
             "its 95% interval (Student's t, 4 degrees of freedom on five seeds).")
    L.append("- \"Clearly ahead\" or \"clearly behind\" = the whole interval is on one side of 0.")
    L.append("- Every scenario is in the tables. No scenario, rule or seed was removed.\n")
    L.append("## Checks\n")
    L.append(md_table(["Check", "Result", "Detail"], [[w, "pass" if ok else "**FAIL**", d] for w, ok, d in ck]))
    L.append("")
    add_lines, add_checks = addendum(A) if A is not None else ([], [])
    if add_checks:                                              # the checks table is written above: insert the rows
        i = next(k for k, x in enumerate(L) if x.startswith("| Check | Result | Detail |"))
        extra = "\n".join("| " + " | ".join([w, "pass" if ok else "**FAIL**", d]) + " |" for w, ok, d in add_checks)
        L[i] = L[i] + "\n" + extra
        ck += add_checks
    if A is not None:
        L += batch_a(A)[0]
    L += add_lines
    if B is not None:
        L += batch_b(B)[0]
    L.append("## Reproduce\n")
    L.append("```")
    L.append("python3 feedback/batches/run_batches.py check")
    L.append("python3 feedback/batches/run_batches.py A --workers 2      # 770 runs")
    L.append("python3 feedback/batches/run_batches.py B --workers 2      # 280 runs")
    L.append("python3 feedback/batches/addendum.py pilot                 # added after the freeze: 880 pilot runs")
    L.append("python3 feedback/batches/addendum.py eval                  # the baseline the pilot chose, 110 runs")
    L.append("python3 feedback/batches/analyze_batches.py                # tables/*.csv and this file")
    L.append("python3 -m pytest feedback/batches/test_batches.py -q      # checks of the runner (pilot seed only)")
    L.append("```")
    with open(NOTE, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    bad = [w for w, ok, _ in ck if not ok]
    print(f"note -> {os.path.relpath(NOTE, ROOT)}; tables -> {os.path.relpath(TABLES, ROOT)}")
    print(f"checks: {len(ck) - len(bad)} of {len(ck)} pass" + ("; FAILED: " + "; ".join(bad) if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
