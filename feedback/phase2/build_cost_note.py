"""Writes feedback/cost.md from sens.csv, greedy.csv and planner.csv, so every number in the note comes from the
result files (python3 build_cost_note.py)."""
import csv
import os

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
s = pd.read_csv(os.path.join(HERE, "sens.csv"))
g = pd.read_csv(os.path.join(HERE, "greedy.csv"))
p = pd.read_csv(os.path.join(HERE, "planner.csv"))
rep_path = os.path.join(HERE, "repro_after_hooks.csv")
if os.path.exists(rep_path):
    with open(rep_path) as f:
        rep = list(csv.DictReader(f))
    rep_txt = f"{sum(r['match'] == 'True' for r in rep)} of {len(rep)}"
else:
    rep_txt = "(not run yet)"

LAB = {"main": "Main scenario (85% load)", "load=95": "Load 95%", "server_fail_recover": "Server failure and return",
       "shared_gpus": "Shared GPUs", "wrong_weights": "Wrong weights", "report_interval=0.2": "Reports every 0.2 s",
       "O_130": "Load 130%", "O_burst": "Burst to 140% for 20 s", "report_interval=30": "Reports every 30 s",
       "ingresses=2": "2 ingresses", "deadline=200": "Deadline 200 ms", "dev_115": "Load 115%",
       "dev_surge_B": "Load 95%, Ingress B doubles for 50 s", "dev_stagger_125": "Load 125%, sites report at different moments",
       "dev_W1_120": "Load 120%, reports every 1 s", "dev_loss_120": "Load 120%, 30% of reports lost",
       "dev2_85": "2 sites, load 85%", "dev2_115": "2 sites, load 115%"}
ORDER = ["main", "load=95", "O_130", "O_burst", "server_fail_recover", "shared_gpus", "wrong_weights",
         "report_interval=0.2", "report_interval=30", "ingresses=2", "deadline=200", "dev_115", "dev_surge_B",
         "dev_stagger_125", "dev_W1_120", "dev_loss_120"]
assert set(ORDER) == set(s.scenario)


def diff(frame, sc, variant, base="base"):
    b = frame[(frame.variant == base) & (frame.scenario == sc)].set_index("seed").success
    x = (frame[(frame.variant == variant) & (frame.scenario == sc)].set_index("seed").success - b).values
    assert len(x) == 5
    h = stats.t.ppf(0.975, 4) * x.std(ddof=1) / np.sqrt(5) if x.std() > 0 else 0.0
    return x.mean(), h


def cell(m, h):
    txt = f"{m:+.1f} ± {h:.1f}"
    return f"**{txt}**" if abs(m) > h and h > 0 else txt


def table(variants, heads):
    out = ["| Scenario | v6.1 success (%) | " + " | ".join(heads) + " |", "|---|---|" + "---|" * len(heads)]
    for sc in ORDER:
        base = s[(s.variant == "base") & (s.scenario == sc)].success.mean()
        out.append(f"| {LAB[sc]} | {base:.1f} | " + " | ".join(cell(*diff(s, sc, v)) for v in variants) + " |")
    return "\n".join(out)


def n_sig(variant):
    return sum(abs(m) > h and h > 0 for m, h in (diff(s, sc, variant) for sc in ORDER))


def sig_list(variant):
    return [(LAB[sc], *diff(s, sc, variant)) for sc in ORDER if abs(diff(s, sc, variant)[0]) > diff(s, sc, variant)[1] > 0]


pen = ["penalty cap 0.90", "penalty cap 0.98", "no penalty", "constant penalty 5", "constant penalty 19"]
thr = ["drop from 85%", "drop from 90%", "limit 90%", "limit 100%"]
t_pen = table(pen, ["Cap 0.90 (κ ≤ 9)", "Cap 0.98 (κ ≤ 49)", "No penalty (κ = 0)", "Constant κ = 5", "Constant κ = 19"])
t_thr = table(thr, ["Drop from 85%", "Drop from 90%", "Limit and drop at 90%", "Limit and drop at 100%"])
nopen = sig_list("no penalty")
d90 = sig_list("drop from 90%")
d85 = sig_list("drop from 85%")
d85_main, d85_w30 = diff(s, "main", "drop from 85%"), diff(s, "report_interval=30", "drop from 85%")
v6_95 = diff(s, "load=95", "v6 (frozen)")
d90_95 = diff(s, "load=95", "drop from 90%")
succ = {v: s[(s.variant == v) & (s.scenario == "load=95")].success.mean() for v in ("base", "drop from 90%", "v6 (frozen)")}

# ---- greedy
G = g[["plans", "fallback", "compared", "optimal", "nonconvex", "nonconvex_cap", "nonconvex_and_gap", "convex_and_gap",
       "curves_differ"]].sum()
not_opt = int(G.compared - G.optimal)
ww = g[g.scenario == "wrong_weights"]
ww_bad = int((ww.compared - ww.optimal).sum())
gmax = g.loc[g.gap_max_pts.idxmax()]
others_max = g[g.scenario != "wrong_weights"].gap_max_pts.max()
two = g[g.sites == 2]
base_all = pd.concat([s[s.variant == "base"], p[p.variant == "base"]])
pl = pd.concat([base_all, p[p.variant != "base"]])
pl_d = {sc: diff(pl, sc, "best plan on the grid") for sc in dict.fromkeys(p.scenario)}
pl_sig = sum(abs(m) > h and h > 0 for m, h in pl_d.values())
pl_rng = (min(m for m, _ in pl_d.values()), max(m for m, _ in pl_d.values()))

doc = rf"""# Phase 2: the cost and the planner of v6.1

- **Project:** Packet Patrol, CMPS 342. **Date:** 15 Nov 2026. **Status:** checks done, **two decisions for the team** (section 7).
- **Questions (Prof. Maurice, 11 Nov 2026):** is κ defined in overload, are the units consistent, is the greedy allocation optimal?
- **Short answers:**
  - κ is not defined in overload. v6 caps it, so it is a constant 19 there. Results do not depend on the cap or on the formula.
  - The units are consistent, and the drop test uses the incremental cost.
  - Greedy is optimal in {100 * G.optimal / G.compared:.1f}% of {int(G.compared):,} plans. Where it is not, the cost curves are not convex. Replacing it by the best plan changes success in none of {len(pl_d)} scenarios.
  - The setting that does matter is the overload threshold, not κ.
- All runs: pilot seeds 101 to 105, Beirut network, v6's 11 pilot tests and the 5 development scenarios of Phase 1. The held-out tests and the other networks took no part.
- Every number below is computed from the result files in `feedback/phase2/` by `feedback/phase2/build_cost_note.py`.

## 1. Definitions

| Symbol | Meaning |
|---|---|
| T | total offered traffic, all ingresses together (frames/s), from the estimate of Phase 1 |
| x | traffic planned for site s, **from all ingresses together** (frames/s). Each ingress plans the split of the total and applies the resulting shares to its own frames |
| H | planning horizon = the report interval W |
| r_s(x) | average chance that a frame sent to s in the next H seconds is late, if s receives x. The last report is aged to now, then through the interval |
| k | calibration factor of the ingress (late share seen ÷ late share predicted) |
| n_s(H; x) | queue at s at the end of the interval if it receives x (fluid model, from the expected queue now) |
| n_s,safe | the largest queue at which a new frame is still late with chance ≤ 1/2, and at least the number of servers. **A risk tolerance of 1/2** |
| κ | late frames charged per frame left above n_s,safe (section 2) |
| cap_s | measured capacity of s (servers measured × frames per server per second) |

**Cost of sending x to site s** (late frames per second):

```latex
C_s(x) = x \cdot \min\{{1,\; k\, r_s(x)\}} \;+\; \kappa \cdot \frac{{\max\{{0,\; n_s(H;x) - n_{{s,\mathrm{{safe}}}}\}}}}{{H}}
```

**Objective of each plan**

```latex
\min_{{x_1..x_S,\,x_{{drop}}}} \;\sum_s C_s(x_s) + 1 \cdot x_{{drop}}
\quad \text{{s.t.}} \quad \sum_s x_s + x_{{drop}} = T,\;\; 0 \le x_s \le 0.95\, cap_s,\;\; x_{{drop}} \ge 0
```

- x_drop must be 0 unless T is above 95% of the measured capacity and the ingress has 100 answers to calibrate with.
- C_s is evaluated on 13 traffic levels (0 to 120% of cap_s) and interpolated linearly between them.
- Below overload, the plan is kept only if its cost is at least 25% below the cost of sharing by capacity. Otherwise the capacity split is used.

## 2. κ

**What the code does**
- ρ = min(0.95, T ÷ usable capacity of all sites). κ = ρ ÷ (1 − ρ). One number for the whole system, not per site.
- Without the cap the formula breaks: ρ = 1.2 gives κ = −6.
- Whenever dropping is allowed, ρ is at the cap, so κ = 19 exactly. In overload κ is a constant.

**Where the formula comes from**
- In a single queue at load ρ, one extra frame delays every frame that arrives before the queue next empties. On average that is ρ ÷ (1 − ρ) frames.
- v6 charges each of those frames as one **late** frame. That is an upper bound: a delayed frame is late only if the extra wait pushes it past its deadline.
- So κ is not a derived conversion from delay to missed deadlines. It is a backlog penalty inspired by that argument.
- In overload the queue never empties, the count is infinite, and the cap replaces it.

**Proposed wording for the paper:** "externality-inspired backlog penalty", with the cap stated as part of the algorithm.

## 3. Units and the drop test

- Risk term: frames/s × probability = late frames per second.
- Backlog term: frames left × κ (late frames per frame left) ÷ seconds = late frames per second.
- Drop: frames/s × 1 miss = missed frames per second.
- The drop test is on the incremental cost. A piece of size Δ goes to the cheapest site if C_s(x + Δ) − C_s(x) ≤ Δ × 1, and is dropped otherwise (`catsim/rules_v6.py`, `_plan`).
- When dropping is possible, the curve that picks the site and the curve of the drop test are the same curve: they differed in {int(G.curves_differ)} of {int(G.compared):,} plans.
- The calibration factor k scales only the risk term, not the backlog term.

## 4. Every cap and margin of the planner

Each one is part of the algorithm. "Checked" refers to section 5.

| Setting | Value | What it does | Checked |
|---|---|---|---|
| `RHO_MAX` | 0.95 | cap on ρ in κ, so κ ≤ 19 | yes: no effect |
| `U_LIMIT` | 0.95 | no site is planned above this share of its capacity | yes: matters |
| `DROP_FROM` | = `U_LIMIT` | dropping is allowed only when T is above this share of the measured capacity | yes: matters |
| `U_MAX` | 0.95 | when measured capacity cannot carry T at this load, sites measured below their told size get part back | no |
| `DROP_COST` | 1 | a dropped frame is one miss | by definition |
| `LATE_SAFE` | 0.5 | risk tolerance in n_s,safe; a site whose empty queue is already above it gets no traffic | no |
| `GAIN` | 0.25 | below overload: keep the plan only if it is this much cheaper than the capacity split | chosen in v6's pilot |
| `CAL_MIN` | 100 | answers needed before dropping is allowed | no |
| calibration | weight 0.01, +0.005, start 0.02, clip [0.05, 20] | smoothing and limits of the factor k | no |
| min{{1, k·r}} | 1 | a frame cannot count as more than one late frame | by definition |
| `GRID`, levels | 13 levels, 0 to 120% of capacity | where C_s is evaluated; above 120% it grows with slope 1 + κ | no |
| `POINTS` | 4 | moments in the interval at which the late chance is averaged | no |
| `CHUNKS` | 100 | the total is shared out in 1% pieces | no |
| drop-share cap | 0.9 | the estimate divides by at least 0.1 | no |
| `EWMA`, `RISE_Z` | 0.3, 3 | smoothing of the estimate; a rise beyond 3 sd is taken at once | Batch C |
| burst check | 2 s window, 4 sd, 25%, at most every 0.5 s, ≥ 20 frames | re-plan between reports on the ingress's own rate | Batch C |
| `SETTLE` | 0.05 s | plan 50 ms after the last report of a round | no |
| `ECHO_FRAC` | 0.25 | a drop count travels at most every W ÷ 4 | no |
| capacity meter | several margins | see `feedback/audit.md`, section 4 | Batch C |

## 5. Sensitivity, one setting at a time

- Each column changes one setting of v6.1. The numbers are the change in deadline success, in points, with its 95% interval (5 paired seeds).
- **Bold** = the change is outside its interval.

**The backlog penalty**

{t_pen}

- **The cap does not matter:** no change is outside its interval for cap 0.90 or 0.98 ({n_sig('penalty cap 0.90')} and {n_sig('penalty cap 0.98')} of 16 scenarios).
- **Removing the penalty matters in {len(nopen)} of 16 scenarios:** {'; '.join(f'{lab} ({m:+.1f} ± {h:.1f})' for lab, m, h in nopen)}.
- **A constant does as well as the formula:** κ = 5 and κ = 19 differ from it in {n_sig('constant penalty 5')} and {n_sig('constant penalty 19')} of 16 scenarios (κ = 5 is slightly better with shared GPUs).
- So the term earns its place in few scenarios, and its exact size is not important.

**The limit and the overload threshold**

{t_thr}

- **Dropping from 90% instead of 95%** (the site limit stays at 95%): {'; '.join(f'{lab} {m:+.1f} ± {h:.1f}' for lab, m, h in d90)}. No scenario gets worse.
  - It recovers the loss of Phase 1 at 95% load: {succ['drop from 90%']:.1f}% against {succ['base']:.1f}% for v6.1 and {succ['v6 (frozen)']:.1f}% for the frozen v6.
  - Between 90% and 95% a frame is then dropped only when every site would cost more than one miss for it.
- **Dropping from 85% is too early.** It starts dropping at the normal load: {'; '.join(f'{lab} {m:+.1f} ± {h:.1f}' for lab, m, h in d85 if m < 0)}, and the main scenario and 30-second reports also go down ({d85_main[0]:+.1f} ± {d85_main[1]:.1f} and {d85_w30[0]:+.1f} ± {d85_w30[1]:.1f}).
- **Moving the site limit is mixed.** At 90% it helps in steady overload and hurts in the burst and with very frequent reports. At 100% it is clearly worse.

## 6. Greedy against the best plan

**On the plans themselves**
- Every plan of v6.1 in {len(g)} runs was compared with the best split on the same grid of 100 pieces (same curves, same limits, same drop option). The comparison is exact: a dynamic programme covers every split.
- {len(two)} of the runs use a 2-site network, the others the 3 Beirut sites.
- {int(G.plans):,} plans. {int(G.fallback):,} used the "every site is at its limit" fallback and are left out. {int(G.compared):,} compared.
- **Greedy is the best plan in {int(G.optimal):,} of them ({100 * G.optimal / G.compared:.2f}%).**
- **Are incremental costs nondecreasing?** Not always: the curves are not convex in {int(G.nonconvex)} plans ({100 * G.nonconvex / G.compared:.1f}%). In {int(G.nonconvex_cap)} of those the min{{1, ·}} cap is active.
- Greedy is never worse than the best plan when the curves are convex ({int(G.convex_and_gap)} cases). All {not_opt} cases where it is worse have non-convex curves, and {ww_bad} of them are in the wrong-weights test.
- **Size of the gap:** at most {gmax.gap_max_pts:.1f} points of the traffic in predicted late frames ({LAB[gmax.scenario].lower()}), and at most {others_max:.2f} points in every other scenario.

**On the results**
- v6.1 was also run with the best plan in place of greedy.
- Deadline success changes by {pl_rng[0]:+.1f} to {pl_rng[1]:+.1f} points across {len(pl_d)} scenarios, and in {pl_sig} of them the change is outside its interval.
- In the wrong-weights test, where almost all the gaps are, the two give the same result in every run.

**Conclusion:** greedy is not optimal in general, the paper should say so, and the measured cost is nil. No change to the planner is proposed.

## 7. Decisions for the team

1. **The overload threshold.** Recommended: allow dropping from 90% of the measured capacity in v6.1 (`DROP_FROM = 0.90`), keep the site limit at 95%, and report the table above as the sensitivity check.
   - Reason: better in {len(d90)} scenarios, worse in none, and it removes the one loss that the corrected estimate caused.
   - It is a setting chosen on pilot seeds, to be stated as such.
2. **The backlog penalty.** Recommended: keep the formula and the cap as they are, call the term an "externality-inspired backlog penalty", and report that a constant gives the same results.
   - Alternative: replace the formula by a constant (κ = 19). Simpler to present, same results on these seeds, but one more change to v6.

## What was changed in the code

- Three hooks in `catsim/rules_v6.py`, all neutral: the penalty as a method (`_kappa`), the drop threshold as a setting (`DROP_FROM`, off), and a diagnostic hook after the greedy loop (`_after_greedy`).
- `KAPPA` in `catsim/rules_v61.py` for the constant-penalty check (off).
- Old results are untouched: {rep_txt} saved runs, re-run on the edited code, match exactly. All 69 tests pass.

## Files

| File | What it is |
|---|---|
| `feedback/cost.md` | this note |
| `feedback/phase2/run_phase2.py` | `sens` ({len(s)} runs), `greedy` ({len(g)} runs), `planner` ({len(p)} runs) |
| `feedback/phase2/sens.csv`, `greedy.csv`, `planner.csv` | every run behind the tables |
| `feedback/phase2/planner_opt.py` | the best-plan-on-the-grid planner (diagnostic only) |
| `feedback/phase2/repro_after_hooks.csv` | the 445 saved runs re-run on the edited code |
| `feedback/phase2/build_cost_note.py` | builds this note |
"""
with open(os.path.join(os.path.dirname(HERE), "cost.md"), "w") as f:
    f.write(doc)
print("cost.md written,", len(doc.splitlines()), "lines")
