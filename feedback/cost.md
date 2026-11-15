# Phase 2: the cost and the planner of v6.1

- **Project:** Packet Patrol, CMPS 342. **Date:** 15 Nov 2026. **Status:** checks done, **two decisions for the team** (section 7).
- **Questions (Prof. Maurice, 11 Nov 2026):** is κ defined in overload, are the units consistent, is the greedy allocation optimal?
- **Short answers:**
  - κ is not defined in overload. v6 caps it, so it is a constant 19 there. Results do not depend on the cap or on the formula.
  - The units are consistent, and the drop test uses the incremental cost.
  - Greedy is optimal in 99.8% of 25,671 plans. Where it is not, the cost curves are not convex. Replacing it by the best plan changes success in none of 18 scenarios.
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
C_s(x) = x \cdot \min\{1,\; k\, r_s(x)\} \;+\; \kappa \cdot \frac{\max\{0,\; n_s(H;x) - n_{s,\mathrm{safe}}\}}{H}
```

**Objective of each plan**

```latex
\min_{x_1..x_S,\,x_{drop}} \;\sum_s C_s(x_s) + 1 \cdot x_{drop}
\quad \text{s.t.} \quad \sum_s x_s + x_{drop} = T,\;\; 0 \le x_s \le 0.95\, cap_s,\;\; x_{drop} \ge 0
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
- When dropping is possible, the curve that picks the site and the curve of the drop test are the same curve: they differed in 0 of 25,671 plans.
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
| min{1, k·r} | 1 | a frame cannot count as more than one late frame | by definition |
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

| Scenario | v6.1 success (%) | Cap 0.90 (κ ≤ 9) | Cap 0.98 (κ ≤ 49) | No penalty (κ = 0) | Constant κ = 5 | Constant κ = 19 |
|---|---|---|---|---|---|---|
| Main scenario (85% load) | 95.6 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 |
| Load 95% | 80.0 | +0.2 ± 0.6 | +0.0 ± 0.0 | +0.2 ± 0.8 | +0.3 ± 0.8 | +0.0 ± 0.0 |
| Load 130% | 63.2 | +0.6 ± 0.9 | +0.0 ± 0.5 | +0.7 ± 0.8 | +0.1 ± 1.0 | +0.0 ± 0.0 |
| Burst to 140% for 20 s | 82.4 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 |
| Server failure and return | 87.7 | -0.3 ± 1.7 | +0.0 ± 0.0 | +0.4 ± 0.9 | +0.3 ± 0.7 | +0.9 ± 2.0 |
| Shared GPUs | 79.3 | -0.0 ± 0.6 | +0.0 ± 0.0 | **-2.6 ± 2.0** | **+0.5 ± 0.4** | +0.0 ± 0.0 |
| Wrong weights | 86.3 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 |
| Reports every 0.2 s | 95.8 | +0.0 ± 0.3 | +0.1 ± 0.3 | **-0.4 ± 0.3** | +0.0 ± 0.4 | +0.0 ± 0.0 |
| Reports every 30 s | 95.8 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 |
| 2 ingresses | 95.7 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 |
| Deadline 200 ms | 71.8 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 |
| Load 115% | 70.6 | +0.5 ± 1.3 | -0.1 ± 0.4 | +0.5 ± 1.0 | +0.3 ± 1.4 | +0.0 ± 0.0 |
| Load 95%, Ingress B doubles for 50 s | 74.6 | -0.4 ± 0.6 | -0.1 ± 0.8 | -0.2 ± 0.7 | -0.5 ± 0.9 | +0.0 ± 0.0 |
| Load 125%, sites report at different moments | 66.4 | +0.1 ± 0.8 | +0.2 ± 1.0 | -0.2 ± 0.6 | -0.3 ± 0.7 | +0.0 ± 0.0 |
| Load 120%, reports every 1 s | 69.3 | +0.5 ± 1.1 | -0.3 ± 0.8 | -0.5 ± 0.9 | -0.4 ± 1.0 | +0.0 ± 0.0 |
| Load 120%, 30% of reports lost | 67.9 | -0.1 ± 1.7 | +0.1 ± 0.3 | -0.4 ± 1.7 | -0.5 ± 1.3 | +0.0 ± 0.0 |

- **The cap does not matter:** no change is outside its interval for cap 0.90 or 0.98 (0 and 0 of 16 scenarios).
- **Removing the penalty matters in 2 of 16 scenarios:** Shared GPUs (-2.6 ± 2.0); Reports every 0.2 s (-0.4 ± 0.3).
- **A constant does as well as the formula:** κ = 5 and κ = 19 differ from it in 1 and 0 of 16 scenarios (κ = 5 is slightly better with shared GPUs).
- So the term earns its place in few scenarios, and its exact size is not important.

**The limit and the overload threshold**

| Scenario | v6.1 success (%) | Drop from 85% | Drop from 90% | Limit and drop at 90% | Limit and drop at 100% |
|---|---|---|---|---|---|
| Main scenario (85% load) | 95.6 | -1.4 ± 2.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 |
| Load 95% | 80.0 | **+3.6 ± 1.6** | **+3.6 ± 1.6** | **+6.6 ± 2.4** | **-10.9 ± 4.9** |
| Load 130% | 63.2 | +0.0 ± 0.0 | +0.0 ± 0.0 | **+1.4 ± 1.3** | **-1.9 ± 1.8** |
| Burst to 140% for 20 s | 82.4 | -0.2 ± 0.8 | -0.0 ± 0.3 | **-1.0 ± 0.2** | +0.4 ± 0.4 |
| Server failure and return | 87.7 | **+1.5 ± 1.0** | **+2.2 ± 1.4** | +2.0 ± 2.0 | +0.3 ± 2.1 |
| Shared GPUs | 79.3 | +0.3 ± 2.2 | +0.3 ± 0.3 | +0.1 ± 1.0 | **-3.8 ± 2.6** |
| Wrong weights | 86.3 | -0.1 ± 3.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 |
| Reports every 0.2 s | 95.8 | +0.1 ± 0.3 | +0.0 ± 0.2 | **-0.8 ± 0.4** | **+0.2 ± 0.2** |
| Reports every 30 s | 95.8 | -0.9 ± 1.0 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 |
| 2 ingresses | 95.7 | **-0.9 ± 0.2** | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 |
| Deadline 200 ms | 71.8 | +0.5 ± 0.7 | +0.0 ± 0.0 | +0.0 ± 0.0 | +0.0 ± 0.0 |
| Load 115% | 70.6 | +0.0 ± 0.0 | +0.0 ± 0.0 | **+1.9 ± 1.7** | **-2.4 ± 1.4** |
| Load 95%, Ingress B doubles for 50 s | 74.6 | +0.5 ± 1.1 | +0.4 ± 1.1 | +1.5 ± 2.1 | **-3.4 ± 1.8** |
| Load 125%, sites report at different moments | 66.4 | +0.0 ± 0.0 | +0.0 ± 0.0 | -0.4 ± 1.0 | **-1.7 ± 1.3** |
| Load 120%, reports every 1 s | 69.3 | +0.0 ± 0.0 | +0.0 ± 0.0 | -0.0 ± 0.6 | **-4.1 ± 0.9** |
| Load 120%, 30% of reports lost | 67.9 | +0.0 ± 0.0 | +0.0 ± 0.0 | +1.0 ± 1.9 | **-2.6 ± 1.4** |

- **Dropping from 90% instead of 95%** (the site limit stays at 95%): Load 95% +3.6 ± 1.6; Server failure and return +2.2 ± 1.4. No scenario gets worse.
  - It recovers the loss of Phase 1 at 95% load: 83.6% against 80.0% for v6.1 and 83.4% for the frozen v6.
  - Between 90% and 95% a frame is then dropped only when every site would cost more than one miss for it.
- **Dropping from 85% is too early.** It starts dropping at the normal load: 2 ingresses -0.9 ± 0.2, and the main scenario and 30-second reports also go down (-1.4 ± 2.0 and -0.9 ± 1.0).
- **Moving the site limit is mixed.** At 90% it helps in steady overload and hurts in the burst and with very frequent reports. At 100% it is clearly worse.

## 6. Greedy against the best plan

**On the plans themselves**
- Every plan of v6.1 in 90 runs was compared with the best split on the same grid of 100 pieces (same curves, same limits, same drop option). The comparison is exact: a dynamic programme covers every split.
- 10 of the runs use a 2-site network, the others the 3 Beirut sites.
- 26,735 plans. 1,064 used the "every site is at its limit" fallback and are left out. 25,671 compared.
- **Greedy is the best plan in 25,627 of them (99.83%).**
- **Are incremental costs nondecreasing?** Not always: the curves are not convex in 477 plans (1.9%). In 168 of those the min{1, ·} cap is active.
- Greedy is never worse than the best plan when the curves are convex (0 cases). All 44 cases where it is worse have non-convex curves, and 41 of them are in the wrong-weights test.
- **Size of the gap:** at most 14.2 points of the traffic in predicted late frames (wrong weights), and at most 0.09 points in every other scenario.

**On the results**
- v6.1 was also run with the best plan in place of greedy.
- Deadline success changes by -0.5 to +0.3 points across 18 scenarios, and in 0 of them the change is outside its interval.
- In the wrong-weights test, where almost all the gaps are, the two give the same result in every run.

**Conclusion:** greedy is not optimal in general, the paper should say so, and the measured cost is nil. No change to the planner is proposed.

## 7. Decisions for the team

1. **The overload threshold.** Recommended: allow dropping from 90% of the measured capacity in v6.1 (`DROP_FROM = 0.90`), keep the site limit at 95%, and report the table above as the sensitivity check.
   - Reason: better in 2 scenarios, worse in none, and it removes the one loss that the corrected estimate caused.
   - It is a setting chosen on pilot seeds, to be stated as such.
2. **The backlog penalty.** Recommended: keep the formula and the cap as they are, call the term an "externality-inspired backlog penalty", and report that a constant gives the same results.
   - Alternative: replace the formula by a constant (κ = 19). Simpler to present, same results on these seeds, but one more change to v6.

## What was changed in the code

- Three hooks in `catsim/rules_v6.py`, all neutral: the penalty as a method (`_kappa`), the drop threshold as a setting (`DROP_FROM`, off), and a diagnostic hook after the greedy loop (`_after_greedy`).
- `KAPPA` in `catsim/rules_v61.py` for the constant-penalty check (off).
- Old results are untouched: 445 of 445 saved runs, re-run on the edited code, match exactly. All 69 tests pass.

## Files

| File | What it is |
|---|---|
| `feedback/cost.md` | this note |
| `feedback/phase2/run_phase2.py` | `sens` (880 runs), `greedy` (90 runs), `planner` (100 runs) |
| `feedback/phase2/sens.csv`, `greedy.csv`, `planner.csv` | every run behind the tables |
| `feedback/phase2/planner_opt.py` | the best-plan-on-the-grid planner (diagnostic only) |
| `feedback/phase2/repro_after_hooks.csv` | the 445 saved runs re-run on the edited code |
| `feedback/phase2/build_cost_note.py` | builds this note |
