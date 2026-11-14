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

`catsim/rules_v5.py`, lines 17–35:

```python
class OwnDrops:
    """This ingress's own frames and whether it dropped them. The sites count only the frames that reach them,
    so the traffic the cameras really offer is: counted / (1 - drop share). Every ingress drops (nearly) the same
    share, because they all compute the same plan from the same reports, so its own share stands for everyone's."""
    MAX = 0.9

    def __init__(self):
        self.log = deque()                         # (time, dropped?)

    def add(self, t, dropped):
        self.log.append((t, dropped))

    def share(self, t0, t1):
        n = d = 0
        for t, x in self.log:
            if t0 < t <= t1:
                n += 1
                d += x
        return min(self.MAX, d / n) if n else 0.0
```

`catsim/rules_v6.py`, lines 70–81:

```python
def on_report_x(self, now, s, q, g, A, X):
    if g <= self.g[s]:
        return
    r = A / self.W / (1.0 - self.own_log.share(g - self.W, g))
    if not self.seen[s]:
        self.rate_off[s] = r
    elif self.use_burst and A > self.rate_off[s] * self.W + self.RISE_Z * math.sqrt(max(self.rate_off[s] * self.W, 1.0)):
        self.rate_off[s] = r                         # a real rise (beyond count noise): take it at once
    else:
        self.rate_off[s] = self.EWMA * r + (1 - self.EWMA) * self.rate_off[s]
    self.own_log.prune(now - 2.0 * self.W - 5.0 - self.BURST_WIN)
    SplitSpeed.on_report_x(self, now, s, q, g, A, X)
```

`catsim/rules_v6.py`, lines 120–121:

```python
self.scale = self._scale_now(now)
total = float(self.rate_off.sum()) * self.scale
```

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

`catsim/rules.py`, lines 574–614:

```python
g0, q0 = p
dur = g - g0
if abs(dur - self.W) > 0.25 * self.W:            # a report is missing: start the evidence again
    self.span[s].clear()
    self.recent[s].clear()
    return False
served_w = A - X - (q - q0)
busy = min(q0, q) >= self.BUSY * self.told[s] or (X > 0 and min(q0, q) >= self.told[s])
# 2. served more than the estimate allows: raise at once
served, T = self._pool(self.recent[s], (served_w, dur))
if T >= self.min_span - 1e-9:
    lb = served / (self.mu * T)
    k = min(int(math.ceil(lb - self.Z * math.sqrt(self.scv * max(lb, 1.0) / (self.mu * T)) - 1e-9)),
            int(self.told[s]))                   # never above the configured size
    if k > self.c[s]:
        return self._set(s, k, g)
# 1. measured while the queue stayed long
if busy:
    self._quiet(s, g)
    served, T = self._pool(self.span[s], (served_w, dur))
    if T < self.min_span - 1e-9:
        return False                             # the queue has not been long for long enough yet
    est = served / (self.mu * T)                 # servers' worth of work done
    se = math.sqrt(self.scv * max(est, 1.0) / (self.mu * T))
    new = int(min(max(math.floor(est + 0.5), 1), self.told[s]))
    if new != self.c[s] and abs(est - self.c[s]) > 0.5 + self.Z * se:
        if new < self.c[s]:                      # slower: was a recent return wrong?
            recent = g - self.up_at[s] <= 2.0 * self.back[s]
            self.back[s] = min(2.0 * self.back[s], self.BACK_CAP * self.base) if recent else self.base
        return self._set(s, new, g)
    return False
# 3. a quiet spell
self.span[s].clear()
self.w_sum[s] += max(0.0, q - self.c[s])
self.w_n[s] += 1
if g - self.quiet_since[s] >= self.back[s]:
    if self.c[s] < self.told[s] and self.w_sum[s] / self.w_n[s] < 1.0:
        self.up_at[s] = g
        return self._set(s, int(self.c[s]) + 1, g)
    self._quiet(s, g)                            # not lightly loaded (or nothing to give back): start again
return False
```

`catsim/rules.py`, lines 629–639:

```python
def usable_capacity(meter, mu, total, u_max):
    """Frames per second each site can take, from the measured servers. If those cannot carry the measured
    traffic at u_max, the sites measured below their configured size get back just enough of the difference
    (a low measurement must not push the healthy sites over the limit; if a site really is that slow, its queue
    grows and it is measured again)."""
    cap = meter.c * mu
    need = total / u_max
    missing = (meter.told - meter.c) * mu
    if cap.sum() < need and missing.sum() > 0:
        cap = cap + min(1.0, (need - cap.sum()) / missing.sum()) * missing
    return cap.astype(float)
```

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

`catsim/rules_v5.py`, lines 112–121:

```python
def on_reply(self, now, s, delay, frame):
    raw = self.pred_raw.pop(frame, None)
    if raw is None or not self.calibrated:
        return
    a = self.CHECK_RATE
    self.n_cal += 1
    self.Pg = (1 - a) * self.Pg + a * raw
    self.Lg = (1 - a) * self.Lg + a * (1.0 if delay > self.D else 0.0)
    self.kcal = float(np.clip((self.Lg + self.CHECK_EPS) / (self.Pg + self.CHECK_EPS),
                              self.CHECK_MIN, self.CHECK_MAX))
```

`catsim/rules_v5.py`, lines 217–220:

```python
raw = float(self.plan_risk[j])
if self.calibrated and self.plan_t > -1e8:        # only frames sent under a plan say how good it is
    self.pred_raw[self.ctx.frame] = raw
return j, min(1.0, raw)
```

`catsim/rules_v6.py`, lines 133–136:

```python
ready = self.calibrated and self.n_cal >= self.CAL_MIN
kc = self.kcal if self.calibrated else 1.0                 # send-or-drop test (as v5)
ks = self.kcal if (self.cal_split and ready) else 1.0      # C: which site gets the traffic
kq = self.kcal if ready else 1.0                           # A: plan vs balanced comparison
```

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

`catsim/rules_v6.py`, lines 130–132:

```python
cap = usable_capacity(self.meter, mu, total, self.U_MAX)
rho = min(self.RHO_MAX, total / cap.sum())
kappa = rho / (1.0 - rho)
```

`catsim/rules_v6.py`, lines 137–138:

```python
overload = total > self.U_LIMIT * float((self.meter.c * mu).sum())
may_drop = overload and (self.n_cal >= self.CAL_MIN or not self.calibrated) and self.allow_drop
```

`catsim/rules_v6.py`, lines 140–156:

```python
for s, (c, lv, ga, late, n_safe) in enumerate(models):
    lam_now = self.p[s] * total
    idx = int(np.argmin(np.abs(lv - lam_now)))
    age = 0.0 if self.no_age else max(0.0, now - self.g[s])
    b0 = ga.age_one(point(self.q[s]), age, idx)
    B = ga.age_all(np.repeat(b0[None, :], self.GRID, axis=0), self.d[s] / 2 + H / (2 * M))
    acc = B @ late
    for _ in range(M - 1):
        B = ga.age_all(B, H / M)
        acc = acc + B @ late
    r = acc / M
    n_now = fluid(float(self.q[s]), lam_now, c, mu, age)
    back = kappa * np.array([max(0.0, fluid(n_now, float(x), c, mu, H) - n_safe) for x in lv]) / H
    risks.append(r)
    sel_c.append(lv * np.minimum(1.0, ks * r) + back)
    cal_c.append(lv * np.minimum(1.0, kc * r) + back)
    cmp_c.append(lv * np.minimum(1.0, kq * r) + back)
```

`catsim/rules_v6.py`, lines 162–166:

```python
slope = 1.0 + kappa

def at(curve, s, x):
    lv = models[s][1]
    return float(np.interp(x, lv, curve[s])) if x <= lv[-1] else float(curve[s][-1] + slope * (x - lv[-1]))
```

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

`catsim/rules_v6.py`, lines 168–201:

```python
for _ in range(self.CHUNKS):
    best, best_key = -1, None
    for s in range(S):
        x = lam[s] + step
        if x > limit[s] + 1e-9:
            continue
        key = (at(sel_c, s, x) - cur_sel[s], x / cap[s])
        if best_key is None or key < best_key:
            best, best_key = s, key
    if best >= 0:
        x = lam[best] + step
        v_cal = at(cal_c, best, x)
        dc, lim = v_cal - cur_cal[best], step * self.DROP_COST
        tie = may_drop and abs(dc - lim) <= self.TIE_TOL * max(lim, 1.0)
        self.t_ties += tie
        if self.tie_drop and tie:
            send = False                                 # the tie fix: a sure miss is dropped
        else:
            send = not may_drop or v_cal - cur_cal[best] <= step * self.DROP_COST + 1e-12   # as ours_v6
        if send:
            if may_drop:
                self.t_sent_drop += 1
                self.t_near += (not tie) and 0.9 * lim <= dc < lim
            lam[best] = x
            cur_sel[best] = at(sel_c, best, x)
            cur_cal[best] = v_cal
            continue
        self.t_costly += not tie
    elif not may_drop:
        lam += (total - lam.sum() - drop) * cap / cap.sum()
        break
    else:
        self.t_full += 1
    drop += step
```

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

`catsim/rules_v6.py`, lines 203–214:

```python
# ---- A: balance unless the plan clearly wins (only when there is no overload)
if self.use_balance and not overload and drop == 0.0:
    bal = total * ok / ok.sum()
    if np.all(bal <= self.U_LIMIT * cap + 1e-9):
        c_plan = sum(at(cmp_c, s, lam[s]) for s in range(S))
        c_bal = sum(at(cmp_c, s, bal[s]) for s in range(S))
        self.gains.append(1.0 - c_plan / c_bal if c_bal > 0 else 0.0)
        if not c_plan < (1.0 - self.GAIN) * c_bal:
            lam = bal
            self.n_bal += 1
        else:
            self.n_plan += 1
```

- Applies only below overload, when the plan drops nothing, and when the balanced split keeps every site under its 95% limit.
- The balanced split shares traffic by measured capacity.
- The risk plan is kept only if its cost is at least 25% below the balanced split's cost (`GAIN`, chosen on pilot seeds 101–105). Otherwise the balanced split is used.

**Sending frames**
- Smooth weighted round-robin on the shares, with drop as one more slot (`rules_v5.py` 200–220).

## 8. Burst detector

**B1: a clear rise in a site's counter**

`catsim/rules_v6.py`, lines 76–79:

```python
elif self.use_burst and A > self.rate_off[s] * self.W + self.RISE_Z * math.sqrt(max(self.rate_off[s] * self.W, 1.0)):
    self.rate_off[s] = r                         # a real rise (beyond count noise): take it at once
else:
    self.rate_off[s] = self.EWMA * r + (1 - self.EWMA) * self.rate_off[s]
```

- Rise taken at once if A > estimate × W + 3 · sqrt(estimate × W).
- A is the raw count of frames that reached the site. The estimate is drop-corrected (offered traffic).
- So while this ingress drops a share p, A is about (1 − p) of the offered count. A rise is taken at once only if offered traffic grows by more than about 1/(1 − p). At p = 27% (load 130%) that is +37%.
- Falls are never taken at once.

**B2: this ingress's own rate between reports**

`catsim/rules_v6.py`, lines 91–100:

```python
def _changed(self, n, b, scale):
    """Is my rate over the last BURST_WIN s (n frames) really different from the rate the plan assumes
    (scale x b frames in the counters' window of W s)? Both counts are random (Poisson), so the test uses the
    noise of both: z = (r_n - ref) / sqrt(r_max / BURST_WIN + scale^2 x r_b / W)."""
    r_n, r_b = n / self.BURST_WIN, b / self.W
    ref = scale * r_b
    if ref * self.BURST_WIN < self.MIN_COUNT or b < self.MIN_COUNT:
        return False
    var = max(r_n, ref) / self.BURST_WIN + scale * scale * r_b / self.W
    return abs(r_n - ref) > max(self.BURST_Z * math.sqrt(var), self.BURST_REL * ref)
```

`catsim/rules_v6.py`, lines 106–114:

```python
def _scale_now(self, now):
    """Ratio (own rate over the last BURST_WIN s) / (own rate in the counters' window), when the difference is
    more than noise; else 1."""
    if not self.use_burst:
        return 1.0
    n, b = self._own_count(now - self.BURST_WIN, now), self._window_count()
    if self._changed(n, b, 1.0):
        return (max(n, 0.5) / self.BURST_WIN) / (b / self.W)
    return 1.0
```

`catsim/rules_v6.py`, lines 228–236:

```python
def choose(self, now):
    # B2: a burst (or its end) between two reports: re-plan at once
    if (self.use_burst and not self.dirty and self.plan_t > -1e8 and now - self.last_check >= self.CHECK_EVERY):
        self.last_check = now
        if now - self.plan_t >= self.BURST_GAP and self.ref_b > 0:
            n = self._own_count(now - self.BURST_WIN, now)
            if self._changed(n, self.ref_b, self.scale):
                self._plan(now)
                self.n_replan += 1
```

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

`catsim/rules_v5.py`, lines 205–209:

```python
p, pd = self.p, self.p_drop
age = now - self.plan_t
if age > self.W:                                  # no fresh plan: slide back to the capacity split
    w = math.exp(-(age - self.W) / self.W)
    p, pd = w * p + (1 - w) * self.pi, w * pd
```

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

`catsim/rules.py`, lines 145–170:

```python
class LSQ(LastReport):
    """LSQ-style local view (after Vargaftik et al.): last report + this ingress's own frames sent since,
    counted once, no ageing. Joins the lowest local count PER SERVER (the sites differ in size);
    ties go to the larger site."""

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        self.log = [deque() for _ in range(self.S)]      # estimated arrival times of own frames

    def on_report(self, now, s, q, g, A):
        if g < self.g[s]:
            return
        super().on_report(now, s, q, g, A)
        lg = self.log[s]
        while lg and lg[0] <= g:
            lg.popleft()

    def on_send(self, now, s):
        self.log[s].append(now + self.d[s] / 2)

    def choose(self, now):
        qh = (self.q + np.array([len(x) for x in self.log])) / self.c
        best = np.flatnonzero(qh <= qh.min() + 1e-12)
        if len(best) > 1:
            best = best[self.c[best] == self.c[best].max()]
        return int(best[0]) if len(best) == 1 else int(self.rng.choice(best)), NAN
```

- Local view = last report + this ingress's own frames sent since then. No ageing.
- Choice = lowest local count per server, deterministic. Ties go to the larger site.
- Different from the paper:
  - updates are the shared periodic reports, pushed to every ingress at the same moment. The paper's dispatchers refresh independently (random samples, or a server updating one random dispatcher);
  - the count is divided by the site's servers.
- Consequence: after each report, all ingresses hold the same picture and pick the same minimum until their own sends change it. Part of the herding in the results comes from this adaptation.
- Existing diagnostic: `study_results/tables/diag_lsq_herding.csv`. With 4 ingresses, LSQ's success goes from 93.8% (reports every 10 s) to 49.3% (every 0.5 s). With 1 ingress it stays at 95–96%.
- `lsq_sample` uses the paper's independent sampling, but at about 2 samples per second per ingress (the byte budget), against 2 per arrival in the paper.

**G. Prequal**

`catsim/baselines.py`, lines 116–133:

```python
def choose(self, now):
    # issue this query's probes (asynchronous: their answers serve later queries)
    if self.R_PROBE > 0:                                  # Prequal's native rate, budget ignored
        self.tokens += self.R_PROBE
        k = int(self.tokens)
        self.tokens -= k
        k = min(k, self.S)
    else:
        self.tokens = min(self.tokens + (now - self.t_last) * self.rate, max(4.0 * self.pb, self.rate))
        k = min(int(self.tokens // self.pb), self.S)
        self.tokens -= k * self.pb
    self.t_last = now
    if k > 0:
        self.probe_bytes += k * self.pb
        self.probe_out.extend(int(x) for x in self.rng.choice(self.S, size=k, replace=False))
    self.n_q += 1
    self.n_p += k
    self.r_probe = self.n_p / self.n_q
```

`catsim/baselines.py`, lines 141–154:

```python
if len(self.pool) < 2:
    return int(self.rng.choice(self.S, p=self.p_cap)), NAN
cold = [j for j, e in enumerate(self.pool) if e[1] <= thr]
if cold:
    j = min(cold, key=lambda q: self.pool[q][2] + self.d[self.pool[q][0]])
else:
    j = min(range(len(self.pool)), key=lambda q: self.pool[q][1])
e = self.pool[j]
s = int(e[0])
e[4] += 1
e[1] += 1.0 / self.c[s]                               # local RIF increment
if e[4] >= e[5]:
    self.pool.pop(j)
return s, NAN
```

- The selection rule (hot-cold on requests-in-flight and latency), the pool, the reuse budget and the removal rule follow the paper.
- Different from the paper:
  - the probe rate comes from the byte budget: 264 B/s per ingress ÷ 124 B per probe = about 2.1 probes per second, which is about 0.03 probes per frame. The paper uses 3 to 5 per query;
  - pool of 4 (16 in the paper); requests-in-flight divided by servers; latency = site estimate + round trip; fallback by capacity.
- Existing diagnostic: `study_results/tables/diag_prequal_budget.csv`. At the medium budget each probe is planned for about 395 uses, and 18% of decisions use the fallback. At the low budget every decision uses the fallback.
- So the result labelled "Prequal" measures Prequal starved of probes. `prequal_native` (3 probes per query, about 100× the budget) is the run in its intended regime.

**L. Oracle**

`catsim/rules.py`, lines 976–987:

```python
def choose(self, now):
    n = self.ctx.nsys
    c_now = self.ctx.c_now
    spd = self.ctx.speed_now
    risk = np.array([self.ctx.late_true(self.i, s, c_now[s], spd[s])[min(n[s], self.N - 1)]
                     for s in range(self.S)])
    best = np.flatnonzero(risk <= risk.min() + 1e-12)
    if len(best) > 1:
        free = np.array([(c_now[s] - n[s]) / c_now[s] for s in best])
        best = best[free >= free.max() - 1e-12]
    s = int(best[0]) if len(best) == 1 else int(self.rng.choice(best))
    return s, float(risk[s])
```

- Reads the true queue, working servers and speed of every site at the moment of the decision.
- Sends each frame to the site with the lowest true late chance for that frame alone.
- It does not see frames already in flight, it does not plan ahead, and it cannot drop.
- So it is not an upper bound. `BASELINES.md` already says so (it is below round-robin at 90% load).
- "Oracle" suggests an optimum. Phase 3 picks a name such as "fresh-state greedy" and decides which reference the gap table uses.

**Common wrapper**

`catsim/baselines.py`, lines 511–520:

```python
def on_report_x(self, now, s, q, g, A, X):
    if g > self.last_g[s]:
        self.last_g[s] = g
        _offered(self.own_log, self.rate_off, self.seen, s, A, g, self.ctx.W, self.EWMA)
        self.seen[s] = True
        self.own_log.prune(now - 2.0 * self.ctx.W - 5.0)
        self.last_rx = now
        total = float(self.rate_off.sum()) if self.seen.all() else 0.0
        room = self.U * float(self.cap.sum())
        self.p_drop = 1.0 - room / total if total > room else 0.0
```

- Drops just enough to keep admitted traffic at 95% of the **told** capacity. v6 uses the **measured** capacity.
- Uses the same offered-traffic estimator as v6 (section 3). If that estimator is biased, the wrapper is biased the same way, so "v6 against the wrapper" is not an independent comparison.

## 11. Where a controller could read simulator truth

**The guard in the engine**

`catsim/engine.py`, line 53:

```python
TRUE_STATE = ("nsys", "c_now", "speed_now", "late_true")   # what only an oracle may read
```

`catsim/engine.py`, lines 228–234:

```python
cls = resolve_rule(rule)
ctx_r = ctx                                        # the context the rules see
if guard and not getattr(cls, "oracle", False):
    ctx_r = SimpleNamespace(**vars(ctx))
    for name in TRUE_STATE:
        setattr(ctx_r, name, _Tripwire(name))
rules = [cls(ctx_r, i) for i in range(R)]
```

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

`catsim/engine.py`, lines 186–188:

```python
late = [[late_table(int(c_known[s]), mu, D - d_known[i, s], sc.job_shape, sc.job_scv) for s in range(S)]
        for i in range(R)]
late_exp = [[late_table(int(c_known[s]), mu, D - d_known[i, s], "exp", 1.0) for s in range(S)] for i in range(R)]
```

`catsim/baselines.py`, line 194:

```python
nc = max(1, int(round(ctx.ingress_rate[i] / self.FRAMES_PER_CLIENT)))
```

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
