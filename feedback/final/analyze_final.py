"""Final tables and figures: Batches A, B and D on seeds 301 to 320 (FREEZE_v6.2.md, catsim/final.py).

    python3 feedback/final/analyze_final.py      -> feedback/final/tables/*.csv, feedback/final/figures/*, feedback/final.md

Rules of the analysis (fixed at the freezes, applied without exception):
  * deadline success = frames answered within the deadline / all frames generated after the warm-up;
    a frame dropped at the ingress, discarded at a site or answered late is a miss;
  * differences paired by seed, 95% interval from Student's t on n - 1 = 19 degrees of freedom;
  * every scenario reported, losses included, with the rejected share next to success; nothing removed.
Seeds 311 to 320 were added after the freeze of v6.1 (catsim/final.py). Nothing here reads or changes catsim/ rules.
"""
import gzip
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "batches"))
import analyze_batches as ab  # noqa: E402  (paired, pooled, md_table, kind_of, names)

TABLES, FIGS = os.path.join(HERE, "tables"), os.path.join(HERE, "figures")
NOTE = os.path.join(os.path.dirname(HERE), "final.md")
V62, V61, V6, TUNED, FROZEN, RR = "ours_v62", "ours_v61", "ours_v6", "wrr+adm61@U=0.9,EWMA=1", "wrr+adm61", "wrr"
NAMES = {V62: "v6.2", V61: "v6.1", V6: "v6", TUNED: "RR + adm. (tuned)", FROZEN: "RR + adm. (frozen)", RR: "Round-robin",
         "wrr+adm61@U=0.9": "RR + adm. at 0.90", "static_deadline+adm61": "Static + adm.",
         "ours_v61@KAPPA=0": "v6.1 no penalty", "ours_v61@allow_drop=False": "v6.1 no drop", "wrr+adm": "RR + adm. (own share)"}
COLOR = {V62: "#2a78d6", V61: "#eb6834", TUNED: "#1baf7a", V6: "#eda100"}       # validated (dataviz), fixed per rule
MARKER = {V62: "o", V61: "s", TUNED: "D", V6: "^"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
EVENTS = {("beirut", "O_burst"): (60, 80.5), ("new", "N_burst"): (60, 80.5), ("beirut", "O_surge"): (50, 100),
          ("beirut", "server_fail_recover"): (50, 100), ("beirut", "O_dc_half"): (50, 110), ("new", "N_fail"): (50, 100)}
D_SHORT = {"D_onoff_95": "Fast on/off, load 95%", "D_onoff_115": "Fast on/off, load 115%",
           "D_dl200_95": "Deadline 200 ms, load 95%", "D_dl200_115": "Deadline 200 ms, load 115%"}


def load(b):
    df = pd.read_csv(os.path.join(HERE, f"batch_{b}.csv"), float_precision="round_trip")
    df["lost"] = df["expired"] + df["late"]
    return df


def label(df, net, key, batch):
    if batch == "D":
        return D_SHORT[key]
    return ab.name_of(df, net, key, "B" if batch == "B" else "A")


def cell(p):
    return ab.fmt_diff(p["diff"], p["half"], p["verdict"])


def get(P, net, key):
    return P[(P.net == net) & (P.scenario == key)].iloc[0]


def counts(P):
    c = P.verdict.value_counts()
    return int(c.get("ahead", 0)), int(c.get("behind", 0)), int(c.get("unclear", 0)) + int(c.get("same", 0))


# ------------------------------------------------------------------------------------------------- tables
def table_a(A, L):
    scs = ab.scenarios_of(A)
    mean = A.groupby(["net", "scenario", "rule"], sort=False)[["success", "rejected", "lost"]].mean()
    mean.reset_index().to_csv(os.path.join(TABLES, "A_success.csv"), index=False)
    cmp_ = [(V62, TUNED), (V61, TUNED), (V62, V61), (V61, FROZEN), (V62, FROZEN)]
    P = {c: ab.paired(A, *c) for c in cmp_}
    abl = [(V61, "ours_v61@KAPPA=0"), (V61, V6), ("ours_v61@allow_drop=False", RR), (V61, "static_deadline+adm61"),
           (V61, "wrr+adm61@U=0.9"), (V61, RR)]
    for c in abl:
        P[c] = ab.paired(A, *c)
    pd.concat(P.values()).to_csv(os.path.join(TABLES, "A_paired.csv"), index=False)

    L.append("## Batch A: where does the gain come from? (22 scenarios, 10 rules, 20 seeds = 4,400 runs)\n")
    L.append("**Table 1. Deadline success, % (rejected share in brackets), mean of 20 seeds.** \\* = pilot scenario "
             "(v6.1's settings were chosen on it, with other seeds).\n")
    cols = [V62, V61, TUNED, FROZEN, RR]
    rows = [[ab.NET[n], label(A, n, k, "A")] + [f"{mean.loc[(n, k, r)].success:.1f} ({mean.loc[(n, k, r)].rejected:.1f})"
                                                 for r in cols] for n, k in scs]
    L.append(ab.md_table(["Network", "Scenario"] + [NAMES[r] for r in cols], rows))
    L.append("\n- RR + adm. (tuned) = round-robin + admission at 0.90 of capacity, no smoothing: settings chosen on pilot "
             "seeds, added after the v6.1 freeze. RR + adm. (frozen) = the primary rival of the v6.1 freeze (0.95, "
             "smoothing 0.3).\n")
    L.append("**Table 2. Differences in success, points, paired by seed, 95% interval. Bold = the interval excludes 0.**\n")
    rows = [[ab.NET[n], label(A, n, k, "A")] + [cell(get(P[c], n, k)) for c in cmp_[:3]] for n, k in scs]
    L.append(ab.md_table(["Network", "Scenario", "v6.2 − tuned", "v6.1 − tuned", "v6.2 − v6.1"], rows))
    L.append("")
    kinds = [(name, [k for k in scs if ab.kind_of(*k) == name]) for name, _ in ab.KINDS]
    groups = [("All 22 scenarios", scs)] + [(ab.NET[n], [k for k in scs if k[0] == n]) for n in ab.NET] + kinds
    L.append("**Table 3. Mean difference over groups of scenarios, points (mean over the scenarios inside each seed, "
             "then the interval over the 20 seeds), and the count of scenarios clearly ahead / behind / neither.** "
             "The kinds of scenario were defined after the first results.\n")
    rows, out = [], []
    for g, keys in groups:
        ks = set(keys)
        row = [g, len(keys)]
        for c in cmp_:
            m, h, _ = ab.pooled(A, *c, ks)
            sub = P[c][[x in ks for x in zip(P[c].net, P[c].scenario)]]
            a, b, u = counts(sub)
            row.append(f"{m:+.1f} ± {h:.1f} ({a}/{b}/{u})")
            out.append(dict(group=g, comparison=f"{c[0]} - {c[1]}", mean=m, half=h, ahead=a, behind=b, neither=u))
        rows.append(row)
    pd.DataFrame(out).to_csv(os.path.join(TABLES, "A_groups.csv"), index=False)
    L.append(ab.md_table(["Scenarios", "n", "v6.2 − tuned", "v6.1 − tuned", "v6.2 − v6.1", "v6.1 − frozen rival",
                          "v6.2 − frozen rival"], rows))
    L.append("")
    L.append("**Table 4. What each part contributes (all 22 scenarios).**\n")
    what = {("ours_v61", "ours_v61@KAPPA=0"): "the backlog penalty",
            ("ours_v61", V6): "the three changes of v6.1 (estimate, rise test, 90% threshold)",
            ("ours_v61@allow_drop=False", RR): "routing alone (neither rule drops)",
            ("ours_v61", "static_deadline+adm61"): "against the static split (= the capacity split)",
            ("ours_v61", "wrr+adm61@U=0.9"): "against RR + admission at 0.90, smoothed",
            ("ours_v61", RR): "against plain round-robin (the floor)"}
    rows = []
    for c in abl:
        m, h, _ = ab.pooled(A, *c, set(scs))
        a, b, u = counts(P[c])
        rows.append([f"{NAMES[c[0]]} − {NAMES[c[1]]}", f"{m:+.1f} ± {h:.1f}", a, b, u, what[c]])
    L.append(ab.md_table(["Comparison", "Mean difference", "Clearly ahead", "Clearly behind", "Neither", "What it shows"],
                         rows))
    ms = A.groupby(["net", "scenario", "rule"]).success.mean().groupby("rule").mean()
    L.append("\n- Mean success over the 22 scenarios: " + ", ".join(
        f"{NAMES[r]} {ms[r]:.1f}%" for r in ms.sort_values(ascending=False).index) + ".\n")
    beh = P[(V62, TUNED)]
    beh = beh[beh.verdict == "behind"]
    L.append("**Where v6.2 is clearly behind the tuned rival (every case):** " + ("; ".join(
        f"{ab.NET[p['net']]}, {label(A, p['net'], p['scenario'], 'A')}: {p['diff']:+.1f} ± {p['half']:.1f}"
        for _, p in beh.iterrows()) or "none") + ".\n")
    return P, mean


def table_b(B, L):
    scs = ab.scenarios_of(B)
    rules = [V62, V61, V6, TUNED, FROZEN, "wrr+adm"]
    mean = B.groupby(["net", "scenario", "rule"], sort=False)[["success", "rejected", "est_min", "est_max", "share_min",
                                                                 "share_max", "admitted_over_capacity"]].mean()
    mean.reset_index().to_csv(os.path.join(TABLES, "B_measures.csv"), index=False)
    L.append("## Batch B: does the estimate hold when ingresses differ? (14 scenarios, 6 rules, 20 seeds = 1,680 runs)\n")
    L.append("**Table 5. Estimate of the offered traffic ÷ the truth, every ingress of every run.**\n")
    rows = []
    for r in rules:
        x = ab._ing_values(B[B.rule == r], "est_by_ingress")
        rows.append([NAMES[r], len(x), f"{x.min():.2f}", f"{np.median(x):.2f}", f"{x.max():.2f}",
                     f"{(abs(x - 1) <= .05).mean() * 100:.0f}%", f"{(abs(x - 1) > .25).mean() * 100:.0f}%"])
    L.append(ab.md_table(["Rule", "Values", "Lowest", "Median", "Highest", "Within 5%", "More than 25% off"], rows))
    L.append("\n- v6.1 and v6.2 use the drop counter; v6 and \"RR + adm. (own share)\" use each ingress's own drop share.\n")
    L.append("**Table 6. Per scenario: estimate ÷ truth (lowest to highest ingress), drop share of the ingresses "
             "(lowest to highest, %), and success, %. Mean of 20 seeds.**\n")
    rows = []
    for n, k in scs:
        a, b = mean.loc[(n, k, V62)], mean.loc[(n, k, V6)]
        rows.append([ab.NET[n], label(B, n, k, "B"), f"{a.est_min:.2f}–{a.est_max:.2f}", f"{b.est_min:.2f}–{b.est_max:.2f}",
                     f"{a.share_min:.1f}–{a.share_max:.1f}", f"{b.share_min:.1f}–{b.share_max:.1f}",
                     f"{a.success:.1f}", f"{b.success:.1f}", f"{mean.loc[(n, k, TUNED)].success:.1f}"])
    L.append(ab.md_table(["Network", "Scenario", "Estimate: v6.2", "Estimate: v6", "Drop share: v6.2", "Drop share: v6",
                          "Success: v6.2", "Success: v6", "Success: tuned rival"], rows))
    rows = []
    for c in [(V62, V61), (V61, V6), (V62, TUNED), (FROZEN, "wrr+adm")]:
        m, h, _ = ab.pooled(B, *c, set(scs))
        a, b, u = counts(ab.paired(B, *c))
        rows.append([f"{NAMES[c[0]]} − {NAMES[c[1]]}", f"{m:+.1f} ± {h:.1f}", a, b, u])
    L.append("\n" + ab.md_table(["Success difference (14 scenarios)", "Mean", "Clearly ahead", "Clearly behind", "Neither"],
                                rows))
    L.append("")


def table_d(D, L):
    scs = ab.scenarios_of(D)
    mean = D.groupby(["net", "scenario", "rule"], sort=False)[["success", "rejected"]].mean()
    mean.reset_index().to_csv(os.path.join(TABLES, "D_success.csv"), index=False)
    cmp_ = [(V62, TUNED), (V61, TUNED), (V62, V61), (V62, FROZEN)]
    P = {c: ab.paired(D, *c) for c in cmp_}
    pd.concat(P.values()).to_csv(os.path.join(TABLES, "D_paired.csv"), index=False)
    L.append("## Batch D: outside the design range (12 scenarios, 5 rules, 20 seeds = 1,200 runs)\n")
    L.append("- Fast on/off traffic: every 4 s, 2 s at 1.5 × and 2 s at 0.5 × the mean rate. Deadline 200 ms instead "
             "of 300 ms. Each at loads 95% and 115%, on the three networks. Fixed before any run (`catsim/final.py`).\n")
    L.append("**Table 7. Success, % (rejected, %), mean of 20 seeds; differences in points, paired by seed.**\n")
    cols = [V62, V61, TUNED, FROZEN, RR]
    rows = []
    for n, k in scs:
        rows.append([ab.NET[n], label(D, n, k, "D")] +
                    [f"{mean.loc[(n, k, r)].success:.1f} ({mean.loc[(n, k, r)].rejected:.1f})" for r in cols] +
                    [cell(get(P[c], n, k)) for c in cmp_[:3]])
    L.append(ab.md_table(["Network", "Scenario"] + [NAMES[r] for r in cols] + ["v6.2 − tuned", "v6.1 − tuned",
                                                                              "v6.2 − v6.1"], rows))
    rows = []
    for g, pref in (("Fast on/off (6)", "D_onoff"), ("Deadline 200 ms (6)", "D_dl200"), ("All 12", "D_")):
        ks = {k for k in scs if k[1].startswith(pref)}
        row = [g]
        for c in cmp_:
            m, h, _ = ab.pooled(D, *c, ks)
            a, b, u = counts(P[c][[x in ks for x in zip(P[c].net, P[c].scenario)]])
            row.append(f"{m:+.1f} ± {h:.1f} ({a}/{b}/{u})")
        rows.append(row)
    L.append("\n" + ab.md_table(["Scenarios", "v6.2 − tuned", "v6.1 − tuned", "v6.2 − v6.1", "v6.2 − frozen rival"], rows))
    L.append("\n- In brackets: scenarios clearly ahead / clearly behind / neither.\n")
    return P, mean


def recovery(L):
    det = {}
    with gzip.open(os.path.join(HERE, "batch_A_detail.jsonl.gz"), "rt") as f:
        for line in f:
            r = json.loads(line)
            _, net, sc, rule, seed = r["key"].split("|")
            if (net, sc) in EVENTS and rule in (V62, V61, TUNED):
                det[(net, sc, rule, int(seed))] = r["ts"]
    rows, out, series = [], [], {}
    for (net, sc), (a, b) in EVENTS.items():
        row = [ab.NET[net], ab.SHORT.get(sc, sc) + f" (ends at {b:g} s)"]
        for rule in (V62, V61, TUNED):
            n = s = rj = 0
            per_sec = []
            for seed in range(301, 321):
                ts = det[(net, sc, rule, seed)]
                fr, su, re = (np.asarray(ts[k], float) for k in ("frames", "success", "rejected"))
                sec = np.arange(len(fr)) + ts["t0"]
                m = (sec >= b) & (sec < b + 20)
                n += fr[m].sum(); s += su[m].sum(); rj += re[m].sum()
                per_sec.append(np.where(fr > 0, su / np.maximum(fr, 1), np.nan))
            row.append(f"{s / n * 100:.1f} / {rj / n * 100:.1f}")
            out.append(dict(net=net, scenario=sc, rule=rule, after_s=20, success=s / n * 100, rejected=rj / n * 100))
            series[(net, sc, rule)] = (np.arange(len(per_sec[0])) + det[(net, sc, rule, 301)]["t0"],
                                       np.nanmean(np.vstack(per_sec), axis=0) * 100)
        rows.append(row)
    pd.DataFrame(out).to_csv(os.path.join(TABLES, "recovery.csv"), index=False)
    L.append("## Recovery after an event (the 20 s after it ends, 20 seeds)\n")
    L.append("**Table 8. Success % / rejected %, all frames generated in the 20 s after the event ends.**\n")
    L.append(ab.md_table(["Network", "Event", "v6.2", "v6.1", "Tuned rival"], rows))
    L.append("\n- v6.2's change targets the first three rows (the estimate after a burst). The DC row is the capacity "
             "meter's slow return, which v6.2 does not change (a known limit).\n")
    return series


def telemetry(A, L):
    t = A[A.rule.isin([V62, V61, V6, TUNED, FROZEN, RR])].groupby(["net", "rule"]).bytes_per_s_per_ingress.mean().unstack()
    t.to_csv(os.path.join(TABLES, "telemetry.csv"))
    L.append("## Telemetry and denominators\n")
    L.append("**Table 9. Telemetry received, bytes per second per ingress (mean over the Batch A scenarios and seeds).**\n")
    rows = [[NAMES[r]] + [f"{t.loc[n, r]:.1f}" for n in ab.NET] for r in [V62, V61, V6, TUNED, FROZEN, RR]]
    L.append(ab.md_table(["Rule", "Beirut", "8 sites", "New"], rows))
    L.append("\n- Round-robin uses no telemetry. v6.1, v6.2 and both admission rivals receive the same reports and drop "
             "counter, so the same bytes.\n")
    fr = A.groupby("net").frames.agg(["mean", "min", "max"])
    L.append("**Denominators.** Each run counts every frame generated after the warm-up: " + "; ".join(
        f"{ab.NET[n]} {fr.loc[n, 'mean']:,.0f} frames per run on average ({fr.loc[n, 'min']:,} to {fr.loc[n, 'max']:,})"
        for n in ab.NET) + ". Every rule sees exactly the same frames in a given scenario and seed. In total: "
        f"{A.frames.sum() / 1e6:.1f} million frames simulated in Batch A (all rules and seeds); 7,280 runs over the "
        "three batches.\n")


# ------------------------------------------------------------------------------------------------- figures
def setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"],
                         "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titlesize": 10, "axes.titleweight": "bold", "legend.frameon": False,
                         "savefig.dpi": 300, "pdf.fonttype": 42})
    return plt


def forest(plt, df, P, comps, title, fname, batch, height):
    scs = ab.scenarios_of(df)
    if batch == "A":
        groups = [(name, [k for k in scs if ab.kind_of(*k) == name]) for name, _ in ab.KINDS]
    else:
        groups = [("Fast on/off traffic", [k for k in scs if k[1].startswith("D_onoff")]),
                  ("Deadline 200 ms", [k for k in scs if k[1].startswith("D_dl200")])]
    fig, ax = plt.subplots(figsize=(7.0, height))
    y, ticks, labels, heads = 0, [], [], []
    for g, keys in groups:
        heads.append((y, g))
        y += 1
        for k in keys:
            for j, (a, b) in enumerate(comps):
                p = get(P[(a, b)], *k)
                yy = y + (j - (len(comps) - 1) / 2) * 0.28
                ax.plot([p["lo"], p["hi"]], [yy, yy], color=COLOR[a], lw=1.6, solid_capstyle="round")
                ax.plot(p["diff"], yy, MARKER[a], color=COLOR[a], ms=4.5, mec="white", mew=0.6)
            ticks.append(y)
            labels.append(f"{ab.NET[k[0]]} · " + label(df, k[0], k[1], batch).replace(" *", ""))
            y += 1
        y += 0.4
    ax.axvline(0, color=INK2, lw=0.9)
    ax.set_yticks(ticks, labels)
    for yy, g in heads:
        ax.text(-0.01, yy, g, transform=ax.get_yaxis_transform(), ha="right", va="center", fontweight="bold",
                fontsize=9, color=INK)
    ax.invert_yaxis()
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.set_xlabel("Difference in deadline success, points (right of 0: the first rule is ahead)")
    for j, (a, b) in enumerate(comps):
        ax.plot([], [], MARKER[a], color=COLOR[a], label=f"{NAMES[a]} − {NAMES[b]}", ms=5)
    ax.legend(loc="lower right", fontsize=8)
    fig.suptitle(title, x=0.01, ha="left", fontsize=10, fontweight="bold")
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIGS, f"{fname}.{ext}"), bbox_inches="tight")
    plt.close(fig)


def fig_recovery(plt, series):
    panels = [(("beirut", "O_burst"), "Beirut: burst to 140%, 60–80 s"),
              (("beirut", "O_dc_half"), "Beirut: DC loses 4 of 8 servers, 50–110 s")]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6), sharey=True)
    for ax, ((net, sc), title) in zip(axes, panels):
        a, b = EVENTS[(net, sc)]
        ax.axvspan(a, b, color="#f0efec", lw=0)
        for r in (TUNED, V61, V62):
            t, s = series[(net, sc, r)]
            m = (t >= 30) & (t <= 148)
            k = np.ones(3) / 3
            ax.plot(t[m], np.convolve(s, k, "same")[m], color=COLOR[r], lw=1.6, label=NAMES[r],
                    ls={V62: "-", V61: "--", TUNED: ":"}[r])
        ax.set_title(title, loc="left", fontsize=9)
        ax.set_xlabel("Time, s")
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_ylim(0, 100)
    axes[0].set_ylabel("Deadline success, %\n(per second, mean of 20 seeds)")
    axes[1].legend(loc="lower right", fontsize=8)
    fig.suptitle("After a burst v6.2 recovers as fast as the rival; after servers return v6.1 and v6.2 recover slowly",
                 x=0.01, ha="left", fontsize=10, fontweight="bold")
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIGS, f"fig_recovery.{ext}"), bbox_inches="tight")
    plt.close(fig)


def fig_estimate(plt, B):
    rules = [V6, V61, V62]
    fig, ax = plt.subplots(figsize=(7.0, 2.2))
    rng = np.random.default_rng(0)
    for i, r in enumerate(rules):
        x = ab._ing_values(B[B.rule == r], "est_by_ingress")
        ax.scatter(x, i + rng.uniform(-0.25, 0.25, len(x)), s=5, color=COLOR[r], alpha=0.35, lw=0, marker=MARKER[r])
        ax.text(x.max() * 1.04, i, f"{(abs(x - 1) <= .05).mean() * 100:.0f}% within 5%", va="center", fontsize=8,
                color=INK2)
    ax.axvline(1, color=INK2, lw=0.9)
    ax.set_xscale("log")
    ax.set_xticks([0.5, 0.75, 1, 1.5, 2, 3, 5], ["0.5", "0.75", "1", "1.5", "2", "3", "5"])
    ax.set_xticks([], minor=True)
    ax.set_yticks(range(len(rules)), [f"{NAMES[r]} ({'own drop share' if r == V6 else 'drop counter'})" for r in rules])
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0.5, 9)
    ax.set_xlabel("Estimate of the offered traffic ÷ the truth (log scale; one dot per ingress and run)")
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title("With the drop counter every ingress estimates the offered traffic within a few percent", loc="left")
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIGS, f"fig_estimate.{ext}"), bbox_inches="tight")
    plt.close(fig)


def main():
    os.makedirs(TABLES, exist_ok=True)
    os.makedirs(FIGS, exist_ok=True)
    A, B, D = load("A"), load("B"), load("D")
    L = ["# Final evaluation: Batches A, B and D on seeds 301 to 320\n",
         "- Ours v6.1 (frozen 15 Nov 2026) and ours v6.2 (v6.1 + one change, frozen 21 Nov 2026, `FREEZE_v6.2.md`).",
         "- Seeds 301 to 310: evaluation seeds of the v6.1 freeze. Seeds 311 to 320: added after that freeze, never "
         "used before. Settings of v6.2 and of the tuned rival were chosen on pilot seeds 101 to 105 only.",
         "- Written by `feedback/final/analyze_final.py` from `feedback/final/batch_{A,B,D}.csv`; checks in "
         "`feedback/final/check_final.py`.",
         "- Deadline success = frames answered within the deadline ÷ all frames generated after the warm-up. "
         "Differences paired by seed; 95% interval, Student's t, 19 degrees of freedom. Nothing removed.\n"]
    PA, _ = table_a(A, L)
    table_b(B, L)
    PD, _ = table_d(D, L)
    series = recovery(L)
    telemetry(A, L)
    n_int = sum(len(PA[c]) for c in [(V62, TUNED), (V61, TUNED), (V62, V61)]) + sum(len(PD[c]) for c in PD)
    L.append(f"- Caution: the main tables hold about {n_int} intervals at 95%; about {round(n_int * 0.05)} would "
             "exclude 0 by chance alone. No correction for multiple comparisons is applied.\n")
    L.append("## Figures (`feedback/final/figures/`, PDF and PNG)\n")
    L.append("- `fig_forest_A`: v6.2 and v6.1 against the tuned rival, every Batch A scenario.")
    L.append("- `fig_forest_D`: the same for Batch D.")
    L.append("- `fig_recovery`: success second by second around a burst and around a server's return.")
    L.append("- `fig_estimate`: estimate ÷ truth for every ingress and run, v6, v6.1, v6.2.")
    with open(NOTE, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    plt = setup()
    forest(plt, A, PA, [(V62, TUNED), (V61, TUNED)],
           "v6.2 beats the tuned rival where capacity changes and in bursts; level in steady load",
           "fig_forest_A", "A", 6.4)
    forest(plt, D, PD, [(V62, TUNED), (V61, TUNED)],
           "Outside the design range: far ahead of the rival on fast on/off traffic (v6.1 more than v6.2); level or behind at 200 ms",
           "fig_forest_D", "D", 3.8)
    fig_recovery(plt, series)
    fig_estimate(plt, B)
    print(f"note -> {os.path.relpath(NOTE, ROOT)}; tables -> {os.path.relpath(TABLES, ROOT)}; "
          f"figures -> {os.path.relpath(FIGS, ROOT)}")


if __name__ == "__main__":
    main()
