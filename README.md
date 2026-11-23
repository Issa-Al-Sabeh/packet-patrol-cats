# CATS site-selection study (Packet Patrol, CMPS 342)

## Start here: the paper and its final evaluation

The paper *Counting the Drops: Joint Admission and Site Selection for Computing-Aware Traffic Steering under Stale
Shared Telemetry* reports the final evaluation of 21 Nov 2026: ours v6.1 and v6.2 against round-robin with tuned
admission, 7,280 runs on seeds 301-320, three networks. Submitted version: tag `paper-submitted`.

| What | Where |
|---|---|
| Every table of the final evaluation (Batches A, B, D) | [`feedback/final.md`](feedback/final.md) |
| What was frozen before the runs (rules, parameters, scenarios, seeds, SHA-256 fingerprints) | [`FREEZE_v6.1.md`](FREEZE_v6.1.md), [`FREEZE_v6.2.md`](FREEZE_v6.2.md); tags `v6.1-frozen`, `v6.2-frozen` |
| Numbers added in the paper revision (outcome breakdown, traces, planned vs realised rates, Erlang C, telemetry by field) | [`feedback/revision/`](feedback/revision/README.md) |
| Answers to the feedback of 11 Nov 2026, one note per question | `feedback/audit.md`, `estimator.md`, `cost.md`, `baselines.md`, `batches.md`, `batchC/diagnosis.md`, `positioning.md` |
| Every change since v6 | [`CHANGES_v6.1.md`](CHANGES_v6.1.md), `FREEZE_v6.2.md` |

Check and reproduce (Python 3.9+, `pip install -r requirements.txt`):

```
python3 feedback/final/check_final.py          # results complete and consistent; re-runs a random sample of 18 runs
python3 feedback/final/analyze_final.py        # rebuilds every table and figure of feedback/final.md
python3 feedback/revision/run_all.py           # the numbers added in the revision (about 1-2 minutes)
python3 feedback/final/run_final.py A|B|D      # re-runs a whole batch (resumable; A, B, D: about 1.3, 0.8, 0.4 CPU-hours)
```

---

**Everything below describes the earlier v6 study (tag `v6-frozen`) and is unchanged.**

One command runs every test of the study, in order, and writes one final report.

```
python run_all.py
```

Final result: **`results/report.html`** (open it in any browser). Every chart and table is in that one file.

`results/runs/` holds every run of the study (round 1: 3,790 runs; round 2: 1,590 more; round 3: 1,020 more;
6,400 in total), so `python run_all.py --report-only` rebuilds the report in seconds and `python run_all.py --fresh`
redoes everything. `previous_results/` keeps the round-1 and round-2 reports for comparison.

---

### The staleness-aware CATS study (November 2026)

ours v6 against 11 baselines (nearest, capacity WRR, dynamic WRR, weighted power-of-two, Dahlin, LSQ, Prequal,
Liyanage et al. 2026, CATS-draft load sharing, expected delay + drop, fresh-state oracle) with 4 ingresses, old
telemetry and equal telemetry budgets. 10,110 runs on seeds 201-210.

```
python3 -m pytest tests -q      # validation
python3 run_study.py --run      # resumable; --status, --tables, --plots
```

- [`STUDY_README.md`](STUDY_README.md): setup, commands, the simulated system, experiments, metric definitions
- [`RESULTS.md`](RESULTS.md): results and the research report (generated from the tables)
- [`BASELINES.md`](BASELINES.md): baseline implementation and verification report

---

### The large network (a second, separate study)

```
python run_large.py
```

6 sites (2, 2, 4, 4, 6 and 12 servers; 8 to 60 ms away) and 12 ingresses, with the rules exactly as frozen in
round 3, so every test is out-of-sample. 12 tests (main, reports every 1 and 10 s, load 70 and 95%, a server
failure, two failures at once, a DC failure, shared GPUs, wrong weights, slow GPUs, 30% of reports lost) x 12 rules
x 10 seeds = 1,440 runs, about 25-30 minutes on 2 cores. Result: `results_large/report_large.html`. It does not
touch the main study. `--quick`, `--seeds`, `--workers` and `--report-only` work as for `run_all.py`.

### The v5 study (ours v5: v2 + measured speeds + dropping, with ideas from the teammate's v4)

```
python run_v5.py --pilot     # step 1: spare seeds 101-105 only; decide between the two candidate versions, freeze
python run_v5.py             # step 2: the full study, then results_v5/report_v5.html
```

- **Ours v5** = ours v2 + measured speeds, with DROP as one more option in the plan, costing exactly one miss.
  Each 1% of the traffic goes where it adds the fewest expected late frames (its own chance of being late + the
  harm to the others + the backlog it leaves); if every site costs more than one miss, it is dropped. Dropping is
  only allowed in overload (offered traffic above 95% of the measured capacity), as in v4. From v4:
  dropping, counting its own drops when it measures the traffic (offered = counted / (1 - drop share)), and never
  using a site that would be late even when empty. The send-or-drop comparison uses the risk scaled to reality
  (late / predicted over the ingress's own answers), and only after 100 answers. While it drops nothing, v5 sends
  every frame exactly where v2 + speeds would.
- **Rivals:** ours v2 + speeds, v4 (ported from its report) and v4 without dropping, round-robin and round-robin +
  speeds, and their versions that **drop the excess** (same offered-traffic estimate as v5), LSQ-style, expected
  delay + drop (v4's strongest rival in its own report), and the oracle (below capacity only).
- **61 tests:** the 36 of the main study and the 12 of the large network (physics unchanged), plus 13 overload tests
  (load 100 to 150%, a burst, rush hour to 120%, a surge, the DC losing half its servers, reports every 1 or 10 s,
  and one without deadline-aware sites). In the overload tests the sites discard a frame whose deadline has passed,
  for every rule; the discard count travels in the same 4-byte counter.
- **Done 31 Oct 2026:** 5,790 runs, 1.07 CPU-hours, 26 minutes on 2 cores; `results_v5/report_v5.html`.
- 5,790 runs (about 1-1.5 CPU-hours). Runs of the old rules already made by `run_all.py` / `run_large.py` are
  copied (a sample is re-run first and must match exactly). Pilot: 280 runs, a few minutes.
- The capacity bound (the fewest frames any rule must miss) is the reference in overload.
- **Pilot decision rule (written before any pilot run):** keep the calibrated v5 unless the version without
  calibration is lower in more of the 8 pilot tests than it is higher (tie: calibrated). If the chosen version is
  clearly worse than v2 + speeds in a below-capacity pilot test, look into it before freezing and disclose any
  change. Then v5 is frozen.
- **Pilot outcome (31 Oct 2026):** pass 1 kept the calibrated version (the uncalibrated one was lower in 1 test,
  higher in 6), but the calibrated v5 was clearly worse than v2 + speeds in main (-0.48 pts) and wrong weights
  (-14.5 pts): it dropped below capacity, and its drops hid the DC's real size from the speed meter. Change: drop
  only in overload. Pass 2: never clearly worse than v2 + speeds; clearly lower at load 95%, shared GPUs, load 130%
  and the burst. v5 frozen. Tables: `results_v5/pilot/pilot_v5_pass1.csv` and `pilot_v5.csv`.
- `--quick`, `--seeds`, `--workers`, `--report-only`, `--no-reuse` as for the other commands.

## 1. Install (once)

You need Python 3.9 or newer.

**Windows (PowerShell or Command Prompt)**

```
cd path\to\cats-sim-v2
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux**

```
cd path/to/cats-sim-v2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Run

| Command | What it does |
|---|---|
| `python run_all.py --pilot` | First look at the new rules on **spare seeds 101-105** (main, real-life scenarios and a few hard settings; never the held-out scenarios). Prints a small table; never used in the report. |
| `python run_all.py` | The full study: 6,400 simulation runs (only the missing ones are run) |
| `python run_all.py --quick` | Main scenario only, 2 seeds, to try the pipeline (under a minute) |
| `python run_all.py --workers 4` | Use 4 CPU cores (default: all cores but one on machines with 4+ cores) |
| `python run_all.py --seeds 5` | 5 repetitions per test instead of 10 |
| `python run_all.py --report-only` | Rebuild the report from runs already saved |
| `python run_all.py --fresh` | Delete saved runs and redo everything (about 1.5 CPU-hours, estimated) |

**Interrupted?** Run the same command again. Every run is saved the moment it finishes, so it continues where it
stopped.

## 3. What runs, in order

1. **Built-in checks**: simulator vs textbook (Erlang C) formulas; our late(n) formula vs simulation; our belief
   ageing vs simulation.
2. **Main scenario (Beirut)**: 17 rules x 10 seeds.
3. **Sweeps**, one factor at a time: report interval (0.2, 0.5, 1, 2, 5, 10, 30 s), load (50, 70, 85, 95%),
   deadline (200, 300, 500 ms), job-size shape, number of ingresses (2, 4, 8, 16), equal vs unequal traffic,
   equal vs unequal sites, reports in sync vs staggered.
4. **Stress tests**: delay jitter (5 and 20 ms), 10% and 30% of reports lost, reports up to 2 s late, load jump
   from 60% to 95%, Hamra losing one of its two servers halfway.
5. **Real-life scenarios** (new in round 2), none announced to the rules:
   - **Server failure:** Hamra loses 1 of its 2 servers at 50 s and gets it back at 100 s.
   - **Shared GPUs:** another app takes 2 of Jdeideh's 4 GPUs, 20 s on, 20 s off.
   - **Wrong weights:** the rules are told the DC has 8 servers; only 6 work.
   - **Rush hour:** load goes from 60% to 95% and back over 5 minutes.
   - **Incident:** Ingress D doubles its frames from 50 s to 100 s.
   - **Mixed jobs:** 80% short (75 ms) and 20% long (200 ms); the average stays 100 ms.
   - **Congestion:** the DC's path delays double from 60 s to 90 s.
6. **Held-out scenarios** (new in round 3): defined before any run of round 3 and never used to design or tune a
   rule (not in the pilot either):
   - **DC failure:** the DC loses 1 of its 8 servers at 50 s and gets it back at 110 s.
   - **Slow GPUs:** Jdeideh's GPUs run at 70% speed from 40 s to 110 s.
7. **Ablations** of ours v1 (no counting, no ageing, exponential late(n), no random near-ties) for every report
   interval.
8. **Analysis and report**: averages with 95% confidence intervals, paired comparisons, the slowest 1% of
   frames, the room to win, calibration of the predicted risk, what the speed meters measured, charts, CSV
   tables, `results/report.html`.

## 4. The four versions of our rule (and the control)

| Version | How it picks a site |
|---|---|
| **Ours v1** (round 1) | Ages the last report into a range of possible queue sizes, counting the other ingresses with the 4-byte counter, and sends each frame to the site with the lowest chance of being late. |
| **Ours v2** (round 2) | At each round of reports it chooses a **split** of all the traffic for the next interval that gives the fewest expected late frames (same belief and late(n) as v1), then sends by taking turns with those shares. Every ingress computes the same split, so no copycat guess is needed. No site is planned above 95% of its capacity. Without new reports the split slides back to 2 : 4 : 8. |
| **Ours v2 + self-check** (round 2) | v2, plus each ingress compares the risk it predicted with how many of its own frames were actually late (from the answers) and scales each site's risk by that ratio. |
| **Ours v2 + measured speeds** (round 3) | v2, plus each ingress **measures how many servers each site really has** from the reports it already gets (frames served = arrivals counter minus the change in the queue, counted only after the queue stayed long for 5 s) and uses that in the whole model; the plan also counts the backlog it leaves behind. No new report fields. |
| *Round-robin + measured speeds* (round 3, control) | Weighted round-robin whose weights are the same measured speeds. It shows how much of the gain comes from the measurement alone. Identical to weighted round-robin until its meter measures a change. |

Round 1 showed v1 sends traffic in bursts and predicts about twice the real risk. v2 targets the bursts, the
self-check targets the wrong risk. Their settings were fixed before any result on the reported seeds (1-10) was
seen. The pilot used only the spare seeds 101-105; after it, one rule was added to v2: no site is planned above
95% of its capacity (in the pilot, at peak load the plan deliberately overloaded one site and left a growing
backlog).

Round 2 showed v2 keeps feeding a site that is secretly slower than configured (wrong weights, a failed server).
**Measured speeds** targets that. This weakness was found on the reported seeds, so the scenarios it was designed
for are not independent evidence: the **held-out scenarios** and the **round-robin control** are. The round-3 pilot
(spare seeds only) ran three times; the speed meter was changed twice in between, and all three tables are in
`results/pilot/`:
1. After false measurements with reports every 0.2 s: measure only after the queue stayed long for 5 s; give a
   slowed site a server back after a quiet spell only if its queue stayed short, and wait twice as long after a
   wrong return.
2. After the shared-GPU scenario got much worse (a low measurement pushed the healthy sites over 95%): when the
   measured speeds cannot carry the traffic, a slowed site gets back just enough capacity; a site that serves more
   than measured is raised at once; the quiet spell became 20 s.

The settings were then fixed before any run on seeds 1-10. After the full run, one bug was found and fixed: when a
site served more than its configured size, the meter logged a "change" to the value it already had. It happened in
3 of 720 runs; redoing them gave the same results (only the false log entries disappeared).

How the speed meter works, in short:
- **Measure:** only after the queue stayed long (at least 2 x the configured servers, at every report) for 5 s,
  so the servers cannot have been idle; rounded to whole servers, and changed only if clearly different (more
  than half a server plus 2 standard errors).
- **Served more:** a site cannot serve more than it can, so if it served more than its estimate allows (over the
  last 10 s), the estimate goes up at once.
- **Quiet spell:** a slowed site gets one server back after 20 s without a long queue and with less than one frame
  waiting beyond its measured servers on average; if that was wrong, the next spell is twice as long.
- **Top-up:** if the measured speeds cannot carry the measured traffic at 95%, the slowed sites get back just
  enough of their configured capacity, so a low measurement never pushes the healthy sites over the limit.

## 5. The main scenario

- 3 sites: Hamra (2 GPU servers, 8 ms), Jdeideh (4 servers, 16 ms), Regional DC (8 servers, 60 ms).
  These are round-trip times from Ingress A; the other ingresses are up to 25% nearer or farther.
- One server finishes 10 frames per second on average (100 ms); job sizes vary (Gamma, variability 0.25).
- 4 ingresses send 85% of total capacity, split 40 / 30 / 20 / 10%. Deadline 300 ms.
- Each site reports its number of frames, plus a 4-byte arrivals counter, every 5 s.
- Each run: 150 s of traffic (rush hour: 300 s); the first 20 s are not counted. With reports every 10 s or 30 s,
  runs are longer (200 s and 600 s; the first 20 s and 60 s not counted) so every run sees at least 20 rounds of
  reports. Those runs see more frames, so even round-robin (no reports) gives slightly different numbers there.

Change any number in `catsim/config.py`. Runs whose settings changed are redone automatically; runs that did not
change are reused. After changing the **code** of a rule or of the engine, use `--fresh` (or change
`MODEL_VERSION` in `catsim/config.py`).

## 6. Files

| File | What it holds |
|---|---|
| `run_all.py` | The one command (and `--pilot`) |
| `catsim/config.py` | Every setting: scenario, sweeps, stress tests, real-life and held-out scenarios, list of rules |
| `catsim/queueing.py` | Job sizes, late(n), belief ageing, Erlang C |
| `catsim/rules.py` | All rules: ours v1, v2, v2 + self-check, v2 + measured speeds (and its speed meter), the comparison rules, the ablations |
| `catsim/engine.py` | One simulation run (discrete-event), including the real-life events (servers lost, slower GPUs, ...) |
| `catsim/checks.py` | The built-in checks |
| `catsim/experiments.py` | Runs everything in parallel; saves every run |
| `catsim/analysis.py` | Confidence intervals, paired comparisons, calibration, room to win |
| `catsim/plots.py`, `catsim/report.py` | Charts and the HTML report |
| `catsim/large.py`, `catsim/large_report.py`, `run_large.py` | The large-network study |
| `run_v5.py` | The one command of the v5 study (and `--pilot`) |
| `catsim/rules_v5.py` | Ours v5, v4 (ported) and v4 without dropping, the rivals that drop the excess, expected delay + drop |
| `catsim/v5.py` | The v5 study: rules, the 13 overload tests, the plan, the pilot |
| `catsim/v5_report.py` | Capacity bound, analysis, checks, charts and `results_v5/report_v5.html` |

Outputs, in `results/`:

| Output | What it holds |
|---|---|
| `report.html` | The final result: every chart and table |
| `tables/summary.csv` | Every test x rule: miss %, 95% CI, mean and p99 time, load swing, bytes/s, shares, verdict vs ours v1 |
| `tables/ours_vs_each_rule.csv` | For each version of ours: in how many tests it was lower / not clearly different / higher than each rule |
| `tables/room_to_win.csv` | Per test: round-robin's miss rate minus the oracle's |
| `tables/calibration.csv` | Predicted risk vs share actually late, by bin |
| `tables/speed_meter.csv` | Per test and metered rule: runs with a change, changes per run, how fast it reacted to a real change |
| `tables/checks.csv` | The built-in checks |
| `charts/*.png` | The charts of the report |
| `runs/*.json` | Every single run (scenario, rule, seed); runs of metered rules also log what ingress A's meter measured |
| `pilot/pilot.csv` | The latest pilot table (spare seeds only) |
| `pilot/pilot_round2.csv`, `pilot/pilot_round3_pass1/2/3_final.csv` | Every earlier pilot table, for transparency |

## 7. Method notes

- **Same world for every rule.** For a given seed, every rule sees exactly the same frames, job sizes, path
  delays, jitter, report losses and real-life events (common random numbers). Rules are compared seed by seed
  (paired), with a 95% Student-t confidence interval.
- **Same information.** Rules only know what their ingress could know: path delays, site sizes (as configured:
  in "wrong weights" they are told 8 DC servers), the reports they received, their own sends, and (Liyanage-style
  and ours v2 + self-check) the delays of their own frames. Only the oracle sees the true queues, servers and GPU
  speed.
- **Fair control for the measured speeds.** Round-robin + measured speeds uses exactly the same meter (and the
  same top-up) as ours v2 + measured speeds, so any difference between the two comes from our model, not from the
  measurement.
- **Same telemetry budget.** Report-based rules receive the same reports; Prequal-style spends the same bytes
  per second on probes instead.
- **Adaptations, chosen to be fair to each rule:** LSQ-style compares frames per server; Prequal-style uses each
  probe answer at most twice; Liyanage-style runs one controller per camera (about 10 frames/s); Dahlin-style is
  the deterministic version.
- **Earlier results are unchanged:** the round-2 code reproduced saved round-1 runs exactly (checked on 18 runs),
  and the round-3 code reproduces saved runs exactly (checked on 71 runs: every group x rule, and the oracle in
  every scenario where servers change), so they are reused.
- The v5 code also reproduces earlier runs exactly: 10 Beirut runs against the round-3 code and 16 saved
  large-network runs (every field but the run time), and `run_v5.py` re-runs a sample of any runs it reuses.
- The engine is a small custom event loop (not SimPy): faster, and no extra dependency.
- Not modelled: ingress failures, batching on the GPUs, frames that know their own job size, a site that stops
  completely. In "slow GPUs", frames already being processed when the speed changes keep their time.
- The speed meter counts whole servers at the configured speed per server, so a slowdown of every GPU is seen as
  fewer servers of normal speed.
