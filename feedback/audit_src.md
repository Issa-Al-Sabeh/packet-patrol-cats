# Phase 0 audit: what the frozen v6 code implements

- **Project:** Packet Patrol, CMPS 342 (Issa Al Sabeh, Hussein Maatouk).
- **Date:** 14 Nov 2026.
- **Scope:** the frozen v6 package (`v6-frozen`, frozen 12 Nov 2026). Nothing in it was changed.
- **Purpose:** answer "what is implemented" for every item Prof. Maurice questioned, with file and line. No fixes and no new experiments here; those start in Phase 1.
- **How the quotes were made:** every code block below is copied from the frozen files by `feedback/build_audit.py`, which also checks the line numbers. Paths are relative to the package root.

## 1. Findings to carry forward

Correctness items come first, as the professor asked.

| # | Finding | Where | Goes to |
|---|---|---|---|
| 1 | The offered-traffic estimate is counted arrivals ÷ (1 − this ingress's own drop share). This is the form the professor flagged. It is right only if every ingress drops the same share. | `rules_v6.py` 73, `rules_v5.py` 43–46 | Phase 1 |
| 2 | The code comment says every ingress computes the same plan. In v6 that does not hold: the late tables, the calibration factor and the burst re-plans are all per ingress. | `rules_v5.py` 17–20, `rules_v6.py` 133–136, 228–236 | Phase 1 |
| 3 | The "clear rise" test (B1) compares the raw count of frames that reached the site with the drop-corrected estimate. While the ingress is dropping, a rise is harder to detect. | `rules_v6.py` 76 | Phase 1, Batch C |
| 4 | κ is one number for the whole system, ρ/(1−ρ) with ρ capped at 0.95. In every plan that is allowed to drop, ρ is at the cap, so κ = 19 exactly. In overload κ is a constant, not a derived quantity. | `rules_v6.py` 130–132, 137 | Phase 2 |
| 5 | The planner is greedy, 1% of traffic at a time. Greedy is optimal only if each site's cost curve is convex. The code never checks that, and two parts of the curve can break it. | `rules_v6.py` 154, 168–201 | Phase 2 |
| 6 | The calibration factor scales only the risk term of the cost, not the backlog term. | `rules_v6.py` 154–156 | Phase 2 |
| 7 | "LSQ" is our adaptation: all ingresses get the same report at the same moment and pick the minimum deterministically. The paper's LSQ refreshes each dispatcher independently. | `rules.py` 145–170 | Phase 3 |
| 8 | "Prequal" runs at about 0.03 probes per frame (the byte budget), against 3 to 5 in the paper. | `baselines.py` 116–133 | Phase 3 |
| 9 | The "oracle" is a per-frame greedy rule on the true state at decision time. It ignores frames in flight and cannot drop, so it is not an upper bound. | `rules.py` 965–987 | Phase 3 |
| 10 | Three baselines contain v6 parts: DWRR uses v6's speed meter, ED+drop uses our v1 belief, and the common wrapper uses the same offered-traffic estimator as v6. | `rules.py` 751, `rules_v5.py` 442, `baselines.py` 514 | Phase 3, Batch A |
| 11 | No non-oracle rule reads live simulator truth (checked on all 45 rule strings). But some true parameters are handed to rules without a guard: the job-size distribution, exact path delays, and (Liyanage only) each ingress's true arrival rate. | section 11 | Phase 3, paper |
| 12 | After a burst ends, the estimate falls only by smoothing (30% per report). The existing diagnostic shows the estimate is highest in the 2 s after a burst. | `rules_v6.py` 79, 106–114 | Batch C |

Items 3 and 12 are readings of the code backed by one existing table. They are not yet measured causes.

## 2. Freeze and reproduction check

**Freeze**
- The package has no git history, so there is no tag. The folder itself is the checkpoint, identified by the SHA-256 list in `FREEZE.md`.
- All 32 files listed in `FREEZE.md` match their fingerprints, before and after the checks below.
- All 51 tests pass (`python3 -m pytest tests -q`, 48 s).
- Work from here on goes in a separate copy, `v6.1/`. The `feedback/` folder lives there.

**Reproduction** (`feedback/repro_check.py`, results in `feedback/repro_results.csv`)
- 445 saved runs were re-run from the frozen code. **All 445 match exactly** (largest difference 0).
- Study 1 (61 tests): 179 runs.
  - v6 on every one of the 61 tests, one seed each.
  - Every rule on four anchor tests: main, overload 130%, burst, large-network main.
  - 60 more runs drawn at random.
  - Compared with the per-seed miss % in `results_v6/tables/summary_v6.csv` (4 decimals, as saved).
- Study 2 (11 baselines): 266 runs.
  - Every one of the 30 rule strings, 3 runs each.
  - v6 on 60 points of the grid.
  - 120 more runs drawn at random.
  - Compared with `study_results/tables/runs_all.csv` on success, late, expired, rejected, mean and 99th-percentile response time, and telemetry bytes, at full precision.
- The sample is fixed by a seed in the script, so the check can be repeated.
- Environment of the re-run: Python 3.13, numpy 2.5, scipy 1.18. The saved results were produced before this session, so this is an independent re-run, not a repeat in the same process.

**Not in the package**
- Study 1's per-run files (`results_v6/runs/`). Only the summary table is there, so Study 1 was checked on miss % only.
- The full report (`Packet_Patrol_Final_Report.docx`). This audit therefore points to code and to `RESULTS.md`, not to report sections.

## 3. Offered-traffic estimator

**What the code does**

[[rules_v5.py 17-35]]

[[rules_v6.py 70-81]]

[[rules_v6.py 120-121]]

- For site s, at a report measured at time g:
  - r_s = (A_s / W) ÷ (1 − p_own).
  - A_s = frames that reached site s in the last W seconds, from every ingress (the 4-byte counter).
  - p_own = dropped ÷ offered, over the frames this ingress handled in (g − W, g], all sites together, capped at 0.9.
- Smoothing:
  - the first report sets the estimate to r_s;
  - a clear rise sets it to r_s at once (B1, section 8);
  - anything else: estimate ← 0.3 r_s + 0.7 × old estimate.
- Total offered traffic = sum over sites × `scale` (the burst ratio of section 8).
- The same estimator exists twice: inline in v6 (`rules_v6.py` 73), and as `_offered` (`rules_v5.py` 43–46) for v5, round-robin + drop and the common wrapper. A fix must cover both or say why not.

**What it assumes**
- Every ingress drops the same share as this one. The comment at `rules_v5.py` 17–20 states this and gives the reason: "they all compute the same plan from the same reports".
- In v6 the plans are not the same:
  - each ingress has its own late(n) tables, because its path delays differ (`rules.py` 667);
  - each ingress has its own calibration factor (section 5);
  - each ingress re-plans on its own burst detector (section 8).

**The professor's counterexample, by the formula**
- Two ingresses offer 100 frames/s each. One admits half, the other admits all. The sites count 150.
- First ingress: 150 ÷ (1 − 0.5) = 300. Second ingress: 150 ÷ (1 − 0) = 150. The truth is 200.
- So the code does what he described. Phase 1 adds this as a test and measures how far drop shares really diverge in the saved scenarios.

**Smaller points**
- p_own is measured on send times, A_s on arrival times at the site. They are offset by the one-way delay (half the round trip, a few ms to about 35 ms).
- p_own is one share for all sites, applied to each site's counter.
- `_window_rate` (`rules_v6.py` 87–89) is never called.

## 4. Capacity meter

**What the code does**

[[rules.py 574-614]]

[[rules.py 629-639]]

- Between two consecutive reports: served = A − X − (q now − q before). X is the site's discard count (0 unless sites discard expired frames).
- Three rules, in this order:
  1. **Served more than the estimate allows:** over the last max(2W, 10 s), if the frames served prove more servers than the estimate (beyond 2 standard errors), the estimate goes up at once.
  2. **Measured while busy:** counted only when the queue is at least 2× the told servers at both reports, for at least max(W, 5 s). The estimate moves to the rounded measurement if that is more than half a server plus 2 standard errors away.
  3. **Quiet spell:** a site measured slower gets one server back after max(20 s, 4W) without a long queue. The spell doubles (up to 8×) if the return was wrong.
- The estimate is in whole servers, from 1 up to the told number. A slower GPU shows up as fewer servers.
- A missing or late report (gap off by more than 25% of W) clears the evidence.
- `usable_capacity`: if the measured capacity cannot carry the traffic at 95%, sites measured below their told size get part of the difference back.

**What it needs to know**
- The nominal service rate per GPU (`mu`) and the job-size variability (`scv`), both exact from the scenario (section 11).
- The told number of servers, as an upper limit.

**Already documented**
- Slow recovery after a failure or slowdown is traced to rule 3 in `RESULTS.md`, Q9 (v6 recovers in 28.7 s after the failure event, WRR in 0.8 s). Batch C starts from there.

## 5. Calibration factor

**What the code does**

[[rules_v5.py 112-121]]

[[rules_v5.py 217-220]]

[[rules_v6.py 133-136]]

- One factor per ingress, `kcal`, shared by all sites.
- kcal = (share of own answered frames that were late + 0.005) ÷ (average predicted risk of those frames + 0.005), clipped to [0.05, 20].
- Both averages are exponential, weight 0.01 per answer (about the last 100 answers). Both start at 0.02, so kcal starts at 1.
- "Predicted risk" is the plan's average risk for the site the frame was sent to, not a per-frame prediction.
- "Late" means the answer came back after the deadline. A reject from a site that discards expired frames counts as late. Frames dropped at the ingress do not enter.
- Where it is used (`rules_v6.py` 133–136):
  - `kc`: send-or-drop comparison;
  - `ks`: which site gets the traffic (change C);
  - `kq`: plan against balanced split (change A).
- Before 100 answers, dropping is off and `ks` = `kq` = 1. After 100 answers all three equal kcal. So in frozen v6 the three cost curves are the same curve whenever dropping is possible. They differ only in the "without C" ablation.

## 6. Cost C_s(x) and κ

**What the code does**

[[rules_v6.py 130-132]]

[[rules_v6.py 137-138]]

[[rules_v6.py 140-156]]

[[rules_v6.py 162-166]]

- For site s and a candidate traffic level x (frames/s), on a grid of 13 levels from 0 to 120% of the site's measured capacity:
  - C_s(x) = x · min(1, k · r_s(x)) + κ · max(0, n_end(x) − n_safe) / W.
- r_s(x) = average chance that a frame sent in the next interval is late.
  - The last report is aged from its measurement time to now, at the traffic level of the current plan.
  - It is then aged through the interval at level x, and the late chance is averaged at 4 moments.
  - The ageing model is a birth-death chain (exact for exponential jobs, approximate otherwise; `queueing.py` 118–153).
- n_end(x) = queue at the end of the interval from a fluid model (`queueing.py` 200–223).
- n_safe = the largest queue at which a new frame is still late with chance ≤ 1/2, and at least the number of servers (`rules.py` 668–669).
- Between grid levels the cost is interpolated linearly. Above 120% of capacity it grows with slope 1 + κ.
- Dropping costs exactly 1 per frame (`DROP_COST`).

**Units**
- First term: frames/s × probability = late frames per second.
- Second term: leftover frames × κ (late frames per leftover frame) ÷ seconds = late frames per second.
- Drop: frames/s × 1 miss = missed frames per second.
- The three are in the same unit. Whether κ is the right exchange rate is a separate question (below).

**κ**
- ρ = min(0.95, total offered traffic ÷ usable capacity). κ = ρ / (1 − ρ).
- It is one number for the whole system. It is not per site.
- The argument for it is in the v2 + speeds docstring (`rules.py` 648–651): at load ρ, clearing one extra frame takes as long as ρ/(1−ρ) new arrivals, which are late meanwhile. This is a heuristic. No derivation is given.
- Values: 1.5 at 60% load, 5.7 at 85%, 9 at 90%, 19 at the cap.
- **In overload:** the overload test is "total > 95% of measured capacity" (line 137). Whenever it is true, ρ is at the cap. So every plan that may drop uses κ = 19. The formula is undefined at ρ ≥ 1, and the cap replaces it with a constant.
- The cap value 0.95 (`RHO_MAX`) therefore sets how strongly v6 penalises backlog in overload. Phase 2 tests the sensitivity.

**Calibration and the cost**
- k multiplies only r_s(x). The backlog term is not calibrated.

## 7. Planner

**Greedy allocation and the drop option**

[[rules_v6.py 168-201]]

- The total is cut into 100 equal pieces.
- Each piece goes to the site with the smallest increase in cost. Equal increases go to the site with the lower utilisation.
- A site cannot go above 95% of its usable capacity. A site where an empty queue already gives a late chance above 1/2 is never used (line 127).
- If dropping is allowed and the cheapest site would cost more than one miss for that piece, the piece is dropped. An exact tie is sent (`tie_drop` is off).
- If every site is full: the piece is dropped when dropping is allowed, otherwise the rest is shared by capacity.
- Dropping is allowed only when all three hold: overload, at least 100 answers, and the drop switch on (line 138).

**Is greedy optimal?**
- Only if every C_s(x) is convex in x. Two parts can break convexity:
  - min(1, k · r) flattens once the risk reaches 1;
  - the curve is a linear interpolation on 13 points.
- The backlog term looks convex (a hinge on a queue that grows faster as x grows), but that is not checked either.
- The code has no convexity check and no comparison with an exhaustive search. Phase 2 does that comparison.

**Change A: balance unless the plan clearly wins**

[[rules_v6.py 203-214]]

- Applies only below overload, when the plan drops nothing, and when the balanced split keeps every site under its 95% limit.
- The balanced split shares traffic by measured capacity.
- The risk plan is kept only if its cost is at least 25% below the balanced split's cost (`GAIN`, chosen on pilot seeds 101–105). Otherwise the balanced split is used.

**Sending frames**
- Smooth weighted round-robin on the shares, with drop as one more slot (`rules_v5.py` 200–220).

## 8. Burst detector

**B1: a clear rise in a site's counter**

[[rules_v6.py 76-79]]

- Rise taken at once if A > estimate × W + 3 · sqrt(estimate × W).
- A is the raw count of frames that reached the site. The estimate is drop-corrected (offered traffic).
- So while this ingress drops a share p, A is about (1 − p) of the offered count. A rise is taken at once only if offered traffic grows by more than about 1/(1 − p). At p = 27% (load 130%) that is +37%.
- Falls are never taken at once.

**B2: this ingress's own rate between reports**

[[rules_v6.py 91-100]]

[[rules_v6.py 106-114]]

[[rules_v6.py 228-236]]

- Every 0.25 s the ingress counts its own offered frames (sent + dropped) in the last 2 s.
- It compares that rate with the rate the plan assumed: `scale` × own count in the counters' window ÷ W.
- It re-plans if the difference is more than 4 standard deviations and more than 25%. At most one re-plan per 0.5 s. It needs at least 20 expected frames.
- On a re-plan, the total is multiplied by the ratio of the two rates. The assumption: every other ingress changed like this one.
- B2 works in both directions (rise and fall).

**Burst end, from the code**
- The stored estimate only falls by smoothing: 70% of the excess is left after one report, 49% after two, 34% after three.
- B2 can scale the total down between reports. But at each report the plan recomputes `scale` by comparing the last 2 s with the counters' window.
  - With W = 2 s (Study 2, medium budget) the two windows almost coincide, so `scale` returns to 1 and the total falls back to the smoothed estimate.
- Existing evidence: `study_results/tables/diag_v6_bursts.csv` (90% load, bursty). Offered estimate ÷ capacity is 1.11 during a burst, **1.34 in the 2 s after it**, 1.18 at 2–5 s and 0.96 at 5–10 s. The drop share is 38% in the 2 s after the burst.
- This matches the reading, but the cause is not yet isolated. Batch C does that and then tests one fix.

## 9. Staleness handling

- Each report is aged from its measurement time to now before it is used (`rules_v6.py` 143–144, quoted in section 6). The "no ageing" ablation sets the age to 0.
- Age = now − measurement time. This assumes the sites' and ingresses' clocks agree.
- With no fresh plan for more than W seconds, the shares slide back to the capacity split and the drop share decays:

[[rules_v5.py 205-209]]

- A report older than one already held is ignored (`rules_v6.py` 71–72).

## 10. Baselines

**Label of each one**

| | Algorithm | Run name | Class, file and lines | Label |
|---|---|---|---|---|
| A | Nearest site | `nearest` | `Nearest`, `rules.py` 64–68 | Exact |
| B | Capacity WRR | `wrr` | `WRR`, `rules.py` 79–91 | Exact (nginx smooth WRR) |
| C | Dynamic WRR | `wrr_speed` | `WRRSpeed`, `rules.py` 740–785 | Ours: WRR on v6's speed meter |
| D | Weighted power-of-two | `wpow2_stale` | `WPow2Stale`, `rules.py` 132–142 | Our adaptation |
| E | Dahlin, Basic LI | `dahlin_li` | `DahlinLI`, `baselines.py` 289–337 | Our adaptation |
| F | LSQ | `lsq` | `LSQ`, `rules.py` 145–170 | Our adaptation |
| F2 | LSQ-Sample | `lsq_sample` | `LSQSample`, `baselines.py` 440–471 | Our adaptation |
| G | Prequal (HCL) | `prequal_hcl` | `PrequalHCL`, `baselines.py` 31–154 | Our adaptation |
| H | Liyanage et al. 2026 | `liyanage26` | `Liyanage26`, `baselines.py` 158–261 | Our adaptation |
| I | CATS-draft load sharing | `cats_lb` | `CatsLB`, `baselines.py` 355–422 | Our instantiation of an individual draft |
| J | Expected delay + drop | `expected_delay_drop` | `ExpectedDelayDrop`, `rules_v5.py` 442–460 | Ours: the v1 belief plus a drop rule |
| K | Ours v6 | `ours_v6` | `SplitV6`, `rules_v6.py` 32–257 | Ours |
| L | Fresh-state oracle | `oracle` | `Oracle`, `rules.py` 965–987 | Reference, not an optimum |
| | Oracle + admission | `oracle_adm` | `OracleAdm`, `baselines.py` 426–436 | Reference |
| | Common wrapper | `<rule>+adm` | `AdmissionWrapper`, `baselines.py` 475–553 | Ours |

- Study 1 only: v5 (`SplitDrop`, `rules_v5.py` 50–223), v2 + speeds (`SplitSpeed`, `rules.py` 642–737), v4 port (`TeammateV4`, `rules_v5.py` 233–314), RR + drop (`WRRDrop`, `rules_v5.py` 323–386), RR + speeds + drop (`WRRSpeedDrop`, `rules_v5.py` 389–439).
- Every adaptation and the frozen parameters are listed per baseline in `BASELINES.md`. That file is the reference; this section adds line numbers and the three baselines the professor questioned.
- None of D to I is a reproduction of the original system. The paper must say "adapted to shared periodic reports" (or to the byte budget) for each.

**F. LSQ**

[[rules.py 145-170]]

- Local view = last report + this ingress's own frames sent since then. No ageing.
- Choice = lowest local count per server, deterministic. Ties go to the larger site.
- Different from the paper:
  - updates are the shared periodic reports, pushed to every ingress at the same moment. The paper's dispatchers refresh independently (random samples, or a server updating one random dispatcher);
  - the count is divided by the site's servers.
- Consequence: after each report, all ingresses hold the same picture and pick the same minimum until their own sends change it. Part of the herding in the results comes from this adaptation.
- Existing diagnostic: `study_results/tables/diag_lsq_herding.csv`. With 4 ingresses, LSQ's success goes from 93.8% (reports every 10 s) to 49.3% (every 0.5 s). With 1 ingress it stays at 95–96%.
- `lsq_sample` uses the paper's independent sampling, but at about 2 samples per second per ingress (the byte budget), against 2 per arrival in the paper.

**G. Prequal**

[[baselines.py 116-133]]

[[baselines.py 141-154]]

- The selection rule (hot-cold on requests-in-flight and latency), the pool, the reuse budget and the removal rule follow the paper.
- Different from the paper:
  - the probe rate comes from the byte budget: 264 B/s per ingress ÷ 124 B per probe = about 2.1 probes per second, which is about 0.03 probes per frame. The paper uses 3 to 5 per query;
  - pool of 4 (16 in the paper); requests-in-flight divided by servers; latency = site estimate + round trip; fallback by capacity.
- Existing diagnostic: `study_results/tables/diag_prequal_budget.csv`. At the medium budget each probe is planned for about 395 uses, and 18% of decisions use the fallback. At the low budget every decision uses the fallback.
- So the result labelled "Prequal" measures Prequal starved of probes. `prequal_native` (3 probes per query, about 100× the budget) is the run in its intended regime.

**L. Oracle**

[[rules.py 976-987]]

- Reads the true queue, working servers and speed of every site at the moment of the decision.
- Sends each frame to the site with the lowest true late chance for that frame alone.
- It does not see frames already in flight, it does not plan ahead, and it cannot drop.
- So it is not an upper bound. `BASELINES.md` already says so (it is below round-robin at 90% load).
- "Oracle" suggests an optimum. Phase 3 picks a name such as "fresh-state greedy" and decides which reference the gap table uses.

**Common wrapper**

[[baselines.py 511-520]]

- Drops just enough to keep admitted traffic at 95% of the **told** capacity. v6 uses the **measured** capacity.
- Uses the same offered-traffic estimator as v6 (section 3). If that estimator is biased, the wrapper is biased the same way, so "v6 against the wrapper" is not an independent comparison.

## 11. Where a controller could read simulator truth

**The guard in the engine**

[[engine.py 53-53]]

[[engine.py 228-234]]

- Four fields are the live true state: queues (`nsys`), working servers (`c_now`), GPU speed (`speed_now`) and the true late table (`late_true`).
- With `guard=True`, a non-oracle rule that touches any of them raises an error.

**Check done for this audit** (`feedback/context_reads.py`, results in `feedback/context_reads.csv`)
- Every rule string of both studies (15 in Study 1, 30 in Study 2) was run below capacity and in overload, with the guard on. None raised.
- The same runs were repeated with a recorder that logs every context field a rule reads.
- Only `oracle`, `oracle+adm` and `oracle_adm` read the four live fields.
- The existing test (`test_conservation_and_guard`) covered the Study 2 rules only. The Study 1 rules (v5, v2 + speeds, v4, RR + drop) are now covered too.

**What rules are given that is not guarded**

| Field | What it is | Who reads it |
|---|---|---|
| `late`, `late_for`, `mean_t` | late(n) tables the engine builds from the **true job-size shape and variability**, the nominal GPU speed, the told servers and the exact mean round trip | v6 and its ablations, v5, v2 + speeds, v4, ED+drop, oracle |
| `scv` | true job-size variability | the speed meter (v6, v5, DWRR), Liyanage's prior |
| `ingress_rate` | **true mean arrival rate of each ingress** | Liyanage only, to set its number of clients (`baselines.py` 194) |
| `d_known` | exact mean round trip for every ingress and site, mean jitter included. Not updated during the congestion event | every rule |
| `mu` | nominal frames per second per GPU | every rule |
| `c` | told servers (wrong on purpose in the "wrong weights" test) | every rule |
| `W`, `D`, byte sizes, budget | configuration | as needed |
| `frame` | global frame number, counted over all ingresses | v6, v5 (a dictionary key); Liyanage (camera = frame mod clients); CATS-LB (hash input) |
| `rngs`, `grid_ager` | the ingress's own random stream; a shared cache of ageing matrices (a pure function of servers, speed and rate) | as needed |

[[engine.py 186-188]]

[[baselines.py 194-194]]

- For v6 this means three assumptions the paper must state:
  1. the job-size distribution is known exactly (it shapes late(n) and the meter's error bars);
  2. mean path delays are known exactly;
  3. clocks are synchronised (report age = now − measurement time).
- `ingress_rate` is a real gap in the guard: it is the true arrival rate. Only Liyanage reads it, and only to decide how many "cameras" it models. v6 does not read it.

**What reaches rules through events**

| Event | What the rule receives | Source lines |
|---|---|---|
| Report | queue (with noise if set), measurement time, arrivals count, discard count | `engine.py` 431–467 |
| Answer | true end-to-end time of the ingress's own frame; a reject if the site discarded it | `engine.py` 337–340, 420–421, 469–470 |
| Probe answer | queue at the site, and for Prequal and Liyanage a latency estimate the engine computes at the site from the site's own recent frames | `engine.py` 304–316, 472–483 |

- These are things an ingress or a site could observe. None passes another ingress's state.

**Evaluation only**
- Telemetry age and error, utilisation, queue areas and per-second series are recorded for the tables. They are never passed to a rule (`engine.py` 277–292).

## 12. Open items for the team

- **Send the full report** (`Packet_Patrol_Final_Report.docx`), so later notes can point to its sections.
- **Study 1 per-run files** (`results_v6/runs/`), if you still have them. Not blocking.
- **Git or folders:** the package has no git history. Say if you want a repository with a `v6-frozen` tag; until then the checkpoint is the folder plus `FREEZE.md`.
- **Next submission date:** still not set. It decides how many seeds Batches A to D can afford.

## Files of this phase

| File | What it is |
|---|---|
| `feedback/audit.md` | this note |
| `feedback/repro_check.py`, `repro_results.csv` | the reproduction check and its 445 rows |
| `feedback/context_reads.py`, `context_reads.csv` | which context fields each rule reads, and the guard result |
| `feedback/build_audit.py`, `audit_src.md` | builds this note and checks every quoted line number |
