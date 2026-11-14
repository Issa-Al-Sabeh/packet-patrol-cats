# Phase 1: the offered-traffic estimator

- **Project:** Packet Patrol, CMPS 342. **Date:** 14 Nov 2026. **Status:** measurements done, **the team has to choose a fix** (section 6).
- **Question (Prof. Maurice, 11 Nov 2026):** is the offered-traffic estimate valid when ingresses drop different shares of their frames?
- **Short answer:** no. The estimate is wrong at each ingress, the drop shares do differ, and the difference lasts. The total that reaches the sites still comes out right, so deadline success in steady overload does not depend on the error.
- Every number below is computed from `feedback/phase1/diagnose.csv` and `feedback/phase1/pilot.csv` by `feedback/phase1/build_note.py`.

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
| Frozen v6, simulated | 299.6 | 149.8 |

- Both are wrong, in opposite directions.
- This is now a test: `feedback/phase1/test_estimator.py` (7 tests, all pass). It checks the frozen function directly and a simulated run.

## 3. Do drop shares really differ? Yes

Frozen v6, existing scenarios, seeds 201 to 205. Ingress A carries 40% of the traffic, B 30%, C 20%, D 10%.

| Network | Scenario | Drop share at ingress A / B / C / D (%) | Gap between ingresses (points) | Estimate ÷ truth, lowest to highest ingress | Admitted ÷ capacity |
|---|---|---|---|---|---|
| Beirut | Load 110% | 18 / 19 / 20 / 7 | 14 | 0.89 to 1.04 | 0.91 |
| Beirut | Load 130% | 30 / 30 / 34 / 16 | 18 | 0.85 to 1.07 | 0.92 |
| Beirut | Load 150% | 40 / 41 / 42 / 26 | 18 | 0.82 to 1.06 | 0.91 |
| Beirut | Load 130%, reports every 1 s | 50 / 22 / 10 / 2 | 49 | 0.72 to 1.45 | 0.92 |
| Beirut | Load 130%, reports every 10 s | 30 / 30 / 30 / 37 | 8 | 0.98 to 1.07 | 0.90 |
| Beirut | Ingress A doubles its traffic for 50 s | 21 / 5 / 5 / 6 | 20 | 0.95 to 1.10 | 0.85 |
| Beirut | Burst to 140% for 20 s | 16 / 13 / 7 / 6 | 24 | 0.95 to 1.14 | 0.82 |
| 8 sites | Load 130% | 33 / 33 / 33 / 14 | 19 | 0.81 to 1.04 | 0.90 |
| 8 sites | Load 130%, reports every 0.5 s | 63 / 16 / 16 / 1 | 63 | 0.68 to 3.14 | 0.87 |
| 8 sites | Load 130%, reports every 10 s | 32 / 32 / 33 / 34 | 2 | 0.99 to 1.01 | 0.88 |
| 8 sites | Load 130%, 30% of reports lost | 31 / 31 / 37 / 21 | 27 | 0.84 to 1.24 | 0.90 |
| 8 sites | Load 110%, bursty | 29 / 29 / 25 / 21 | 16 | 1.02 to 1.16 | 0.80 |

- "Gap" = highest minus lowest drop share among the ingresses, averaged over the 5-second windows in which frames were dropped.
- **The shares are not close.** At 130% load on Beirut the three larger ingresses drop about twice the share of the smallest one.
- **It gets worse with more frequent reports.** With reports every 0.5 s on the 8-site network, Ingress A drops 63% of its frames and Ingress D 1%. A's estimate is 3.1 times the truth on average (4.7 times in the worst run).
- **With reports every 10 s the shares stay close** (gap of 2 to 8 points).
- **16 ingresses:** in every run at least one ingress drops nothing, while another drops 35% to 53%.
- **A burst at one ingress** (Ingress A doubles): A drops 21% over the run, the other three about 5%.

**Why the total still comes out right**
- An ingress that drops more believes there is more traffic, so it keeps dropping more. One that drops less believes there is less, so it keeps dropping less.
- In a simple model (no smoothing): ingress i admits a share a_i, believes the total is A ÷ a_i, and then admits what fits, h. Its new share is a_i × h ÷ A. Every ingress multiplies its share by the same factor h ÷ A.
  - So the total moves to what fits.
  - And the ratio between two ingresses' shares never changes. Nothing pulls them back together.
- Measured: admitted traffic is 0.87 to 0.92 of capacity in the 14 steady overload scenarios. Averaged over a run, no site receives more than 0.93 of its capacity (runs without a failure).
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
- Counterexample: 199.4 and 149.8 (truth 200). Right where the drops are, low where there are none.

**Option C. An aggregate drop counter in the report ("add information")**
- Each ingress counts the frames it drops. At most every W ÷ 4 seconds it writes that count (2 bytes) on a frame it is sending anyway.
- Each site adds up the counts it received in the window and reports the sum (2 more bytes per report).
- Estimate = (counted ÷ W) ÷ (1 − p), with p = all drops ÷ (all arrivals + all drops). Same formula and smoothing as v6; only p changes.
- Counterexample: 198.9 and 198.9 (truth 200).
- It also includes one small correction: the "clear rise" test compares arrivals with expected arrivals (audit finding 3).
- In this pilot the counter is emulated: the ingresses share an object that stands for the sites' counters and read it only when the matching report arrives.

**Deadline success (%), mean of 5 pilot seeds**

| Scenario | Keep v6 | Lower bound | Drop counter | Drop counter − v6 (points) |
|---|---|---|---|---|
| Main scenario (85% load) | 95.6 | 95.6 | 95.6 | +0.0 ± 0.0 |
| Load 95% | 83.4 | 76.2 | 80.0 | -3.5 ± 1.8 |
| Load 130% | 63.6 | 54.1 | 63.2 | -0.4 ± 0.8 |
| Burst to 140% for 20 s | 81.5 | 82.8 | 82.4 | +0.9 ± 1.0 |
| Load 115% | 71.0 | 62.9 | 70.6 | -0.3 ± 2.0 |
| Load 95%, Ingress B doubles for 50 s | 74.5 | 70.4 | 74.6 | +0.0 ± 0.7 |
| Load 125%, sites report at different moments | 65.9 | 59.5 | 66.4 | +0.5 ± 0.7 |
| Load 120%, reports every 1 s | 69.2 | 60.9 | 69.3 | +0.1 ± 0.8 |
| Load 120%, 30% of reports lost | 68.2 | 59.4 | 67.9 | -0.3 ± 1.2 |

- The last column is the paired difference with its 95% interval.

**Estimate and fairness**

| Scenario | Estimate ÷ truth: v6 | Estimate ÷ truth: drop counter | Gap between ingresses: v6 | Gap: drop counter |
|---|---|---|---|---|
| Load 95% | 0.96 to 1.11 | 1.00 to 1.00 | 17 | 6 |
| Load 130% | 0.83 to 1.05 | 1.00 to 1.00 | 19 | 2 |
| Burst to 140% for 20 s | 0.96 to 1.17 | 1.05 to 1.06 | 22 | 9 |
| Load 115% | 0.85 to 1.04 | 1.00 to 1.00 | 19 | 2 |
| Load 95%, Ingress B doubles for 50 s | 0.89 to 1.18 | 1.02 to 1.03 | 28 | 6 |
| Load 125%, sites report at different moments | 0.89 to 1.08 | 1.03 to 1.03 | 16 | 1 |
| Load 120%, reports every 1 s | 0.79 to 1.33 | 1.00 to 1.01 | 39 | 1 |
| Load 120%, 30% of reports lost | 0.86 to 1.16 | 0.99 to 1.00 | 26 | 5 |

**What the numbers say**
- **Lower bound: clearly worse.** It under-counts, so it drops too little: 4 to 9 points of success lost in six of the seven overload scenarios (the short burst is the exception, +1.3 ± 1.6). Late frames go from 7% to 16% in steady overload. Its estimate is 0.73 to 1.01 of the truth.
- **Drop counter: the estimate is right** (0.99 to 1.06 of the truth at every ingress, against 0.79 to 1.33 for v6).
- **Drop counter: the ingresses drop alike** (gap of 1 to 9 points, against 16 to 39).
- **Drop counter: success in overload is unchanged.** No difference is outside its interval in the seven overload scenarios.
- **Drop counter: worse at exactly 95% load** (-3.5 ± 1.8 points).
  - It is worse in each of the 5 seeds. 95% is v6's own overload threshold.
  - With the correct estimate, all four ingresses sit right at the threshold and switch dropping on and off together. They reject as much on average (5.0% against 5.0%), but in bunches: drops occur in 16 of 26 five-second windows, against 22 for v6. Late frames rise from 11.6% to 15.0%.
  - In v6 an ingress that has started dropping over-estimates the traffic, stays in overload mode and sheds steadily. So part of v6's result at 95% load came from its estimation error.
  - This belongs to the threshold, not to the estimator. It goes to Phase 2 (sensitivity of every cap and margin).
- **The rise-test correction matters only with the counter.**
  - With the counter, it is what makes the one-ingress burst neutral: -1.8 ± 1.3 points without it, +0.0 ± 0.7 with it.
  - With v6's own-share estimator it changes success by less than its interval everywhere, but widens the gap between ingresses (one-ingress burst: 28 → 39 points; reports every 1 s: 39 → 47).

**Cost of the counter**
- Telemetry: 2.6 extra bytes per second per ingress on Beirut with reports every 5 s (+7% on 38.3), and 12.7 with reports every 1 s (+6% on 196.7). These bytes must be added to v6's budget in every comparison.
- Protocol: one new 2-byte field from ingress to site, and 2 more bytes in the report. This is a design addition the paper has to justify.
- Work: about half a day to move the counter from the emulation into the engine and the reports, with tests.

## 5. Other checks of Phase 1

**Windows, delay, small shares**
- The site counts arrivals in (g − W, g]. The ingress counts its own decisions in the same clock window. The two are offset by the one-way delay (a few ms to about 35 ms). With the counter, add up to W ÷ 4.
- A late report still describes (g − W, g]. The ingress keeps its own log for 2W + 7 s, so a report later than about W + 7 s would find the log gone. The longest delay tested is 1 s (Study 2) and 2 s (Beirut "late reports").
- The own drop share is capped at 0.9, so the estimate is at most 10 times the count.
- With few own frames per window the share is coarse. With 16 ingresses the smallest one has about 6 frames per 2-second window.

**Planned against realized traffic per site**
- For each site: what the ingresses planned to send there in total, against what arrived.
- Steady overload, reports every 1 s or slower: planned ÷ realized is 0.97 to 1.03 over every run and site.
- Reports every 0.5 s (8 sites): 0.86 to 1.01.

**Capacity meter: it sometimes measures a server too few**
- In 9 of 110 runs in which no server ever fails or slows, the meter lowered a site's size.
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

## 6. Decisions for the team

1. **Which option?**
   - A: keep v6, rename the quantity, and report the uneven drops as a limit.
   - B: lower bound. Not recommended (it loses 4 to 9 points in overload).
   - C: drop counter. Recommended: it is the only option that makes the estimate correct, and it is the example the feedback itself gives.
   - If a new protocol field is not acceptable, A is the fallback.
2. **If C:** accept the new field and count its bytes in v6's telemetry budget.
3. **The 95% threshold:** agree to disclose the loss at 95% load and to study the threshold in Phase 2.
4. **The capacity meter:** fix it now, or handle it with the slow-recovery work (Batch C), since it is the same component. Suggested: with Batch C.

## 7. After the choice

- The chosen option moves into `catsim/` as v6.1 (off by default, so every v6 result still reproduces).
- The counterexample test must pass on v6.1.
- This note gets the choice and its reason, and Phase 1 is closed.

## Files

| File | What it is |
|---|---|
| `feedback/estimator.md` | this note |
| `feedback/phase1/candidates.py` | the three options as prototypes (outside `catsim/`) |
| `feedback/phase1/test_estimator.py` | the counterexample tests and the harness check |
| `feedback/phase1/run_phase1.py` | `counter`, `diagnose` (125 runs), `pilot` (270 runs) |
| `feedback/phase1/diagnose.csv`, `pilot.csv` | every run behind the tables |
| `feedback/phase1/summarize.py`, `build_note.py` | the tables and this note |
