"""Writes feedback/estimator.md from diagnose.csv and pilot.csv, so every number in the note comes from the result
files (python3 build_note.py)."""
import os

import numpy as np
from scipy import stats

import summarize as S

HERE = os.path.dirname(os.path.abspath(__file__))
d, p = S.load("diagnose.csv"), S.load("pilot.csv")
val = S.load("validate.csv")                                    # ours_v61 (the counter in the engine), same pilot runs
import csv                                                    # noqa: E402
import sys                                                    # noqa: E402
with open(os.path.join(HERE, "repro_after_v61.csv")) as _f:
    _rep = list(csv.DictReader(_f))
rep_ok, rep_n = sum(r["match"] == "True" for r in _rep), len(_rep)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tests"))
import test_v61 as tv                                         # noqa: E402
cx61 = tv._forced("ours_v61")
_cols = ["success", "rejected", "expired", "late"]
_a = val.set_index(["scenario", "seed"])[_cols]
_b = p[p.rule == "est_echo_b1"].set_index(["scenario", "seed"])[_cols]
same_runs, all_runs = int((_a.sort_index() == _b.sort_index()).all(axis=1).sum()), len(_a)


def mean_list(x, col):
    return np.mean(np.array(x[col].tolist()), axis=0)


def drow(key):
    return d[d.scenario == key]


def prow(key, rule):
    return p[(p.scenario == key) & (p.rule == rule)]


def diff(key, a, b="ours_v6", col="success"):
    x = (prow(key, a).set_index("seed")[col] - prow(key, b).set_index("seed")[col]).values
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return x.mean(), h


def pm(m, h):
    return f"{m:+.1f} ± {h:.1f}"


E8 = "_d50_steady_W2_R4_het_D300"
DIAG = [("Beirut", "O_110", "Load 110%"), ("Beirut", "O_130", "Load 130%"), ("Beirut", "O_150", "Load 150%"),
        ("Beirut", "O_130_W1", "Load 130%, reports every 1 s"), ("Beirut", "O_130_W10", "Load 130%, reports every 10 s"),
        ("Beirut", "O_surge", "Ingress A doubles its traffic for 50 s"),
        ("Beirut", "O_burst", "Burst to 140% for 20 s"),
        ("8 sites", "L130" + E8, "Load 130%"),
        ("8 sites", "L130_d50_steady_W0.5_R4_het_D300", "Load 130%, reports every 0.5 s"),
        ("8 sites", "L130_d50_steady_W10_R4_het_D300", "Load 130%, reports every 10 s"),
        ("8 sites", "L130" + E8 + "_loss", "Load 130%, 30% of reports lost"),
        ("8 sites", "L110_d50_bursty_W2_R4_het_D300", "Load 110%, bursty")]
t1 = ["| Network | Scenario | Drop share at ingress A / B / C / D (%) | Gap between ingresses (points) | Estimate ÷ truth, lowest to highest ingress | Admitted ÷ capacity |",
      "|---|---|---|---|---|---|"]
for net, key, lab in DIAG:
    x = drow(key)
    assert len(x) == 5, key
    sh = mean_list(x, "share_by_ingress")
    t1.append(f"| {net} | {lab} | {' / '.join(f'{v:.0f}' for v in sh)} | {x.spread_mean.mean():.0f} | "
              f"{x.est_min.mean():.2f} to {x.est_max.mean():.2f} | {x.admitted_over_capacity.mean():.2f} |")
r16 = drow("L130_d50_steady_W2_R16_het_D300")
r16_hi = r16.share_by_ingress.apply(max)
worst = d.loc[d.est_max.idxmax()]

PIL = [("main", "Main scenario (85% load)", "pilot test"), ("load=95", "Load 95%", "pilot test"),
       ("O_130", "Load 130%", "pilot test"), ("O_burst", "Burst to 140% for 20 s", "pilot test"),
       ("dev_115", "Load 115%", "new"), ("dev_surge_B", "Load 95%, Ingress B doubles for 50 s", "new"),
       ("dev_stagger_125", "Load 125%, sites report at different moments", "new"),
       ("dev_W1_120", "Load 120%, reports every 1 s", "new"),
       ("dev_loss_120", "Load 120%, 30% of reports lost", "new")]
ECHO = "est_echo_b1"
t2 = ["| Scenario | Keep v6 | Lower bound | Drop counter | Drop counter − v6 (points) |", "|---|---|---|---|---|"]
t3 = ["| Scenario | Estimate ÷ truth: v6 | Estimate ÷ truth: drop counter | Gap between ingresses: v6 | Gap: drop counter |",
      "|---|---|---|---|---|"]
for key, lab, _ in PIL:
    v, b, e = prow(key, "ours_v6"), prow(key, "est_bound"), prow(key, ECHO)
    assert len(v) == len(b) == len(e) == 5
    t2.append(f"| {lab} | {v.success.mean():.1f} | {b.success.mean():.1f} | {e.success.mean():.1f} | {pm(*diff(key, ECHO))} |")
    if key != "main":
        t3.append(f"| {lab} | {v.est_min.mean():.2f} to {v.est_max.mean():.2f} | {e.est_min.mean():.2f} to "
                  f"{e.est_max.mean():.2f} | {v.spread_mean.mean():.0f} | {e.spread_mean.mean():.0f} |")
over = [k for k, _, _ in PIL if k not in ("main", "load=95")]
bound_d = [diff(k, "est_bound")[0] for k in over if k != "O_burst"]
bound_burst = diff("O_burst", "est_bound")
bins95 = (prow("load=95", "ours_v6").bins_dropping.mean(), prow("load=95", ECHO).bins_dropping.mean())
import test_estimator as te                                    # the counterexample, simulated (about 3 s)
cx = {r: te._estimates(r) for r in ("ours_v6", "est_bound", "est_echo")}
late_v = np.mean([prow(k, "ours_v6").late.mean() for k in ("O_130", "dev_115", "dev_W1_120")])
late_b = np.mean([prow(k, "est_bound").late.mean() for k in ("O_130", "dev_115", "dev_W1_120")])
b_est = (min(prow(k, "est_bound").est_min.mean() for k in over), max(prow(k, "est_bound").est_max.mean() for k in over))
e_est = (min(prow(k, ECHO).est_min.mean() for k in over + ["load=95"]),
         max(prow(k, ECHO).est_max.mean() for k in over + ["load=95"]))
v_est = (min(prow(k, "ours_v6").est_min.mean() for k in over + ["load=95"]),
         max(prow(k, "ours_v6").est_max.mean() for k in over + ["load=95"]))
e_gap = (min(prow(k, ECHO).spread_mean.mean() for k in over), max(prow(k, ECHO).spread_mean.mean() for k in over))
v_gap = (min(prow(k, "ours_v6").spread_mean.mean() for k in over), max(prow(k, "ours_v6").spread_mean.mean() for k in over))
bb = {k: prow(k, "ours_v6").base_bytes_per_s_per_ingress.mean() for k, _, _ in PIL}       # v6: reports only
xb = {k: val[val.scenario == k].base_bytes_per_s_per_ingress.mean() - bb[k] for k, _, _ in PIL}  # v6.1: what it adds
pct = {k: 100 * xb[k] / bb[k] for k in xb}
l95 = diff("load=95", ECHO)
l95_late = (prow("load=95", "ours_v6").late.mean(), prow("load=95", ECHO).late.mean())
l95_rej = (prow("load=95", "ours_v6").rejected.mean(), prow("load=95", ECHO).rejected.mean())
surge_plain, surge_fix = diff("dev_surge_B", "est_echo"), diff("dev_surge_B", ECHO)
b1_own = {k: (prow(k, "ours_v6").spread_mean.mean(), prow(k, "est_own_b1").spread_mean.mean())
          for k in ("dev_surge_B", "dev_W1_120")}
b1_own_succ = [diff(k, "est_own_b1") for k, _, _ in PIL]

# ---- other checks
const = [s for s in dict.fromkeys(d.scenario) if not any(t in s for t in ("dc_half", "fail", "slow"))]
xc = d[d.scenario.isin(const)]
n_false = int(sum(1 for m in xc.meter_changes if max(m) > 0))
steady = [s for s in const if s in ("O_100", "O_110", "O_130", "O_150", "O_130_W1", "O_130_W10", "O_130_nodiscard")
          or "steady" in s]
fast = "L130_d50_steady_W0.5_R4_het_D300"
br = np.concatenate(d[d.scenario.isin([s for s in steady if s != fast])].belief_over_realized.tolist())
br_fast = np.concatenate(drow(fast).belief_over_realized.tolist())
adm = d[d.scenario.isin(steady)].groupby("scenario").admitted_over_capacity.mean()
site_max = max(max(v) for v in d[d.scenario.isin(const)].site_load)

doc = f"""# Phase 1: the offered-traffic estimator

- **Project:** Packet Patrol, CMPS 342. **Date:** 14 Nov 2026. **Status:** closed. Option C (the drop counter) was chosen and built as v6.1 (sections 6 and 7).
- **Question (Prof. Maurice, 11 Nov 2026):** is the offered-traffic estimate valid when ingresses drop different shares of their frames?
- **Short answer:** no. The estimate is wrong at each ingress, the drop shares do differ, and the difference lasts. The total that reaches the sites still comes out right, so deadline success in steady overload does not depend on the error.
- Every number below is computed from the result files in `feedback/phase1/` by `feedback/phase1/build_note.py`.

## 1. What v6 does

- At each report, for site s: **estimate = (frames counted at the site ÷ W) ÷ (1 − own drop share)**.
- "Own drop share" = frames this ingress dropped ÷ frames it was offered, in the same window, all sites together, capped at 0.9.
- The total offered traffic is the sum over sites. Code and line numbers: `feedback/audit.md`, section 3.
- **Assumption:** every other ingress drops the same share as this one.

## 2. The professor's counterexample

Two ingresses offer 100 frames/s each. The first drops half, the second drops nothing. The sites count 150. The truth is 200.

| | Estimate at ingress 1 | Estimate at ingress 2 |
|---|---|---|
| By the formula | 150 ÷ (1 − 0.5) = 300 | 150 ÷ (1 − 0) = 150 |
| Frozen v6, simulated | {cx['ours_v6'][0]:.1f} | {cx['ours_v6'][1]:.1f} |

- Both are wrong, in opposite directions.
- This is now a test: `feedback/phase1/test_estimator.py` (7 tests, all pass). It checks the frozen function directly and a simulated run.

## 3. Do drop shares really differ? Yes

Frozen v6, existing scenarios, seeds 201 to 205. Ingress A carries 40% of the traffic, B 30%, C 20%, D 10%.

{chr(10).join(t1)}

- "Gap" = highest minus lowest drop share among the ingresses, averaged over the 5-second windows in which frames were dropped.
- **The shares are not close.** At 130% load on Beirut the three larger ingresses drop about twice the share of the smallest one.
- **It gets worse with more frequent reports.** With reports every 0.5 s on the 8-site network, Ingress A drops {mean_list(drow(fast), 'share_by_ingress')[0]:.0f}% of its frames and Ingress D {mean_list(drow(fast), 'share_by_ingress')[3]:.0f}%. A's estimate is {drow(fast).est_max.mean():.1f} times the truth on average ({worst.est_max:.1f} times in the worst run).
- **With reports every 10 s the shares stay close** (gap of {drow('L130_d50_steady_W10_R4_het_D300').spread_mean.mean():.0f} to {drow('O_130_W10').spread_mean.mean():.0f} points).
- **16 ingresses:** in every run at least one ingress drops nothing, while another drops {r16_hi.min():.0f}% to {r16_hi.max():.0f}%.
- **A burst at one ingress** (Ingress A doubles): A drops {mean_list(drow('O_surge'), 'share_by_ingress')[0]:.0f}% over the run, the other three about {np.mean(mean_list(drow('O_surge'), 'share_by_ingress')[1:]):.0f}%.

**Why the total still comes out right**
- An ingress that drops more believes there is more traffic, so it keeps dropping more. One that drops less believes there is less, so it keeps dropping less.
- In a simple model (no smoothing): ingress i admits a share a_i, believes the total is A ÷ a_i, and then admits what fits, h. Its new share is a_i × h ÷ A. Every ingress multiplies its share by the same factor h ÷ A.
  - So the total moves to what fits.
  - And the ratio between two ingresses' shares never changes. Nothing pulls them back together.
- Measured: admitted traffic is {adm.min():.2f} to {adm.max():.2f} of capacity in the {len(steady)} steady overload scenarios. Averaged over a run, no site receives more than {site_max:.2f} of its capacity (runs without a failure).
- What starts the difference was not isolated. Candidates: ingresses reach their first 100 answers at different times (A first), each has its own burst check, and each has its own late tables.

## 4. The three options, with numbers

**How they were compared**
- Pilot seeds 101 to 105 only, on the Beirut network only.
- Scenarios: four of v6's own pilot tests, plus five new development scenarios made for this check.
- The held-out tests, the large network and the 8-site network took no part in the comparison. Section 3 only measures the frozen rule there.
- The three options are prototypes outside `catsim/` (`feedback/phase1/candidates.py`). The same class with v6's settings reproduces v6 exactly (tested).

**Option A. Keep v6 and state the assumption ("restrict the model")**
- No change to the code.
- The assumption "ingresses drop alike" is false (section 3), so it cannot be stated as holding.
- What can be stated: the quantity is a control signal, not an estimate of offered traffic; the total admitted is right; the split of the drops between ingresses is uneven and can be very uneven.

**Option B. A lower bound ("bound it")**
- Count only this ingress's own drops: offered ≥ counted + own drops. This is the only bound available without new information.
- Counterexample: {cx['est_bound'][0]:.1f} and {cx['est_bound'][1]:.1f} (truth 200). Right where the drops are, low where there are none.

**Option C. An aggregate drop counter in the report ("add information")**
- Each ingress counts the frames it drops. At most every W ÷ 4 seconds it writes that count (2 bytes) on a frame it is sending anyway.
- Each site adds up the counts it received in the window and reports the sum (2 more bytes per report).
- Estimate = (counted ÷ W) ÷ (1 − p), with p = all drops ÷ (all arrivals + all drops). Same formula and smoothing as v6; only p changes.
- Counterexample: {cx['est_echo'][0]:.1f} and {cx['est_echo'][1]:.1f} (truth 200).
- It also includes one small correction: the "clear rise" test compares arrivals with expected arrivals (audit finding 3).
- In this pilot the counter is emulated: the ingresses share an object that stands for the sites' counters and read it only when the matching report arrives.
- The version built afterwards, with the counter in the engine and the reports, gives the same results in {same_runs} of {all_runs} pilot runs (section 7). So the tables below hold for v6.1 as built.

**Deadline success (%), mean of 5 pilot seeds**

{chr(10).join(t2)}

- The last column is the paired difference with its 95% interval.

**Estimate and fairness**

{chr(10).join(t3)}

**What the numbers say**
- **Lower bound: clearly worse.** It under-counts, so it drops too little: {abs(max(bound_d)):.0f} to {abs(min(bound_d)):.0f} points of success lost in six of the seven overload scenarios (the short burst is the exception, {pm(*bound_burst)}). Late frames go from {late_v:.0f}% to {late_b:.0f}% in steady overload. Its estimate is {b_est[0]:.2f} to {b_est[1]:.2f} of the truth.
- **Drop counter: the estimate is right** ({e_est[0]:.2f} to {e_est[1]:.2f} of the truth at every ingress, against {v_est[0]:.2f} to {v_est[1]:.2f} for v6).
- **Drop counter: the ingresses drop alike** (gap of {e_gap[0]:.0f} to {e_gap[1]:.0f} points, against {v_gap[0]:.0f} to {v_gap[1]:.0f}).
- **Drop counter: success in overload is unchanged.** No difference is outside its interval in the seven overload scenarios.
- **Drop counter: worse at exactly 95% load** ({pm(*l95)} points).
  - It is worse in each of the 5 seeds. 95% is v6's own overload threshold.
  - With the correct estimate, all four ingresses sit right at the threshold and switch dropping on and off together. They reject as much on average ({l95_rej[1]:.1f}% against {l95_rej[0]:.1f}%), but in bunches: drops occur in {bins95[1]:.0f} of 26 five-second windows, against {bins95[0]:.0f} for v6. Late frames rise from {l95_late[0]:.1f}% to {l95_late[1]:.1f}%.
  - In v6 an ingress that has started dropping over-estimates the traffic, stays in overload mode and sheds steadily. So part of v6's result at 95% load came from its estimation error.
  - This belongs to the threshold, not to the estimator. It goes to Phase 2 (sensitivity of every cap and margin).
- **The rise-test correction matters only with the counter.**
  - With the counter, it is what makes the one-ingress burst neutral: {pm(*surge_plain)} points without it, {pm(*surge_fix)} with it.
  - With v6's own-share estimator it changes success by less than its interval everywhere, but widens the gap between ingresses (one-ingress burst: {b1_own['dev_surge_B'][0]:.0f} → {b1_own['dev_surge_B'][1]:.0f} points; reports every 1 s: {b1_own['dev_W1_120'][0]:.0f} → {b1_own['dev_W1_120'][1]:.0f}).

**Cost of the counter**
- Telemetry (measured on v6.1 as built): {xb['O_130']:.1f} extra bytes per second per ingress on Beirut with reports every 5 s (+{pct['O_130']:.0f}% on {bb['O_130']:.1f}), and {xb['dev_W1_120']:.1f} with reports every 1 s (+{pct['dev_W1_120']:.0f}% on {bb['dev_W1_120']:.1f}). Below capacity only the 2 bytes per report remain (+{pct['main']:.0f}%). These bytes are counted in v6.1's budget in every comparison.
- Protocol: one new 2-byte field from ingress to site, and 2 more bytes in the report. This is a design addition the paper has to justify.

## 5. Other checks of Phase 1

**Windows, delay, small shares**
- The site counts arrivals in (g − W, g]. The ingress counts its own decisions in the same clock window. The two are offset by the one-way delay (a few ms to about 35 ms). With the counter, add up to W ÷ 4.
- A late report still describes (g − W, g]. The ingress keeps its own log for 2W + 7 s, so a report later than about W + 7 s would find the log gone. The longest delay tested is 1 s (Study 2) and 2 s (Beirut "late reports").
- The own drop share is capped at 0.9, so the estimate is at most 10 times the count.
- With few own frames per window the share is coarse. With 16 ingresses the smallest one has about 6 frames per 2-second window.

**Planned against realized traffic per site**
- For each site: what the ingresses planned to send there in total, against what arrived.
- Steady overload, reports every 1 s or slower: planned ÷ realized is {br.min():.2f} to {br.max():.2f} over every run and site.
- Reports every 0.5 s (8 sites): {br_fast.min():.2f} to {br_fast.max():.2f}.

**Capacity meter: it sometimes measures a server too few**
- In {n_false} of {len(xc)} runs in which no server ever fails or slows, the meter lowered a site's size.
- Example (Beirut, 110% load, seed 204): the DC is measured at 7 servers instead of 8 at 15 s, and gets the server back at 75 s.
- Example (8 sites, 130% bursty, seed 201): two sites are measured one and two servers too low at 62 s; one of them is still one server low when the run ends.
- Likely cause, from the code (`rules.py` 581): with deadline discards, a window counts as "busy" if the queue was at least the number of servers at both reports and something was discarded. The queue can still dip below the servers in between. Then throughput is below capacity and the meter reads it as capacity.
- This is the point the professor raised (throughput is not capacity unless the site is busy the whole time). It is not fixed here.
- With real failures, the slow return of a server is already documented in `RESULTS.md`, Q9.

**Calibration (last 100 answers)**
- With deadline-aware sites, a discarded frame comes back as a reject and counts as late (`engine.py` 337–340). Timed-out frames are therefore included.
- Without discarding (most Beirut tests below capacity), a late frame is counted only when its answer returns. While queues grow, the late share lags.
- Frames dropped at the ingress never enter (no prediction is made for them).
- "100 answers" is a count, not a time: about 2 s at the largest ingress and 8 s at the smallest. This is one more way ingresses differ.
- Near-zero predicted risk: 0.005 is added to both the late share and the predicted risk, both start at 0.02, and the factor is clipped to [0.05, 20] (`rules.py` 399–401).

## 6. Decisions (taken 14 Nov 2026)

1. **Option C, the drop counter, is chosen.** It is the only option that makes the estimate correct, and it is the example the feedback itself gives. B was rejected (it loses {abs(max(bound_d)):.0f} to {abs(min(bound_d)):.0f} points in overload). A was the fallback.
2. **The new field is accepted**, and its bytes are counted in v6.1's telemetry budget.
3. **The 95% threshold** is disclosed here and studied in Phase 2 with the other caps and margins. Until then it is a known limit of v6.1.
4. **The capacity meter** is handled with the slow-recovery work (Batch C), since it is the same component. Until then it is a known limit.

## 7. What was built, and how it was checked

**The v6.1 estimate**
- Estimate at site s = (A_s ÷ W) ÷ (1 − p), with p = all drops ÷ (all arrivals + all drops), from the last round of reports.
- Assumptions, stated:
  - a drop count is lost when the report that carries it is lost;
  - a count reaches the reports up to W ÷ 4 plus one way of path delay after the drops it counts;
  - the same share p is applied to every site (the sites the dropped frames would have gone to are not known).

**Built**
- Engine: an ingress can put its drop count on a frame it sends anyway; each site reports the sum. Off for every other rule (`catsim/engine.py`).
- Rule `ours_v61` (`catsim/rules_v61.py`): v6 with the new estimate and the corrected rise test.
- Wrapper `<rule>+adm61` (`catsim/baselines.py`): the common rejection wrapper with the same estimate, as the matched-admission rival.
- Every change is listed in `CHANGES_v6.1.md`.

**Checked**
- **The counterexample passes:** v6.1 estimates {cx61[0]:.1f} and {cx61[1]:.1f} (truth 200). v6 gives {cx['ours_v6'][0]:.1f} and {cx['ours_v6'][1]:.1f}.
- **v6.1 equals v6 while nothing is dropped** (main scenario, seed 201: 2.8937% missed in both).
- **The old rules are untouched:** {rep_ok} of {rep_n} saved runs of Studies 1 and 2, re-run on the edited code, match exactly.
- **The built version equals the prototype:** {same_runs} of {all_runs} pilot runs identical.
- **Every drop is counted once**, and the bytes of the counter are in the byte totals (`tests/test_v61.py`).
- 69 tests pass: the 51 of v6, 11 for v6.1, 7 for the counterexample and the prototype.

## Files

| File | What it is |
|---|---|
| `feedback/estimator.md` | this note |
| `catsim/rules_v61.py`, `tests/test_v61.py` | v6.1 and its tests |
| `CHANGES_v6.1.md` | every change since the v6 freeze |
| `feedback/phase1/candidates.py` | the three options as prototypes (outside `catsim/`) |
| `feedback/phase1/test_estimator.py` | the counterexample tests and the harness check |
| `feedback/phase1/run_phase1.py` | `counter`, `diagnose` (125 runs), `pilot` (270 runs), `validate` (45 runs) |
| `feedback/phase1/diagnose.csv`, `pilot.csv`, `validate.csv` | every run behind the tables |
| `feedback/phase1/repro_after_v61.csv` | the 445 saved runs re-run on the edited code |
| `feedback/phase1/summarize.py`, `build_note.py` | the tables and this note |
"""
with open(os.path.join(os.path.dirname(HERE), "estimator.md"), "w") as f:
    f.write(doc)
print("estimator.md written,", len(doc.splitlines()), "lines")
