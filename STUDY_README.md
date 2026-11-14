# Staleness-Aware CATS: research simulation (November 2026)

This study compares **Staleness-Aware CATS (ours v6)** with established load-balancing, distributed dispatching and deadline-aware routing methods.

**Research question:** with several independent ingress dispatchers and old telemetry, does it improve deadline success at the same telemetry budget?

It extends the existing Packet Patrol simulator (`catsim/`) instead of replacing it. Every earlier study still runs and reproduces its saved numbers (regression test).

- Results summary and research report: [`RESULTS.md`](RESULTS.md) (generated from the tables)
- Baseline implementation and verification report: [`BASELINES.md`](BASELINES.md)
- Run status (completed vs pending, per experiment): `study_results/tables/run_status.csv`, also at the top of `RESULTS.md`

**Status (3 Nov 2026): all 10,110 planned runs are complete** (seeds 201–210), after the 51 tests and the pilot (seeds 101–105) passed. Nothing is pending.

## Setup
```
pip install -r requirements.txt          # numpy, scipy, matplotlib (+ pandas and pytest for the study)
python3 -m pytest tests -q               # 51 unit and integration tests (about 1.5 min)
```
Python 3.9+ works; the study was run with Python 3.13 on 2 cores.

## Commands
| Step | Command | Notes |
|---|---|---|
| Smoke test | `python3 run_study.py --smoke` | every main rule once, true-state guard on |
| Tests | `python3 -m pytest tests -q` | must pass before the study |
| Pilot | `python3 run_study.py --pilot` | tunes on seeds 101–105, writes `study_results/frozen_params.json`; refuses to run again unless `--force` |
| Full study | `python3 run_study.py --run` | 10,110 runs on seeds 201–210, priority order, resumable; about 3 h on 2 cores |
| One experiment | `python3 run_study.py --run exp7_admission` | experiment ids are in `--status` |
| Status | `python3 run_study.py --status` | completed vs pending runs per experiment |
| Tables | `python3 run_study.py --tables` | CSVs from the completed runs only |
| Figures | `python3 run_study.py --plots` | PNG + PDF from the tables |
| Diagnostics | `python3 -m catsim.study_diagnostics` | Prequal probe pool and LSQ herding at the three budgets (explains Q4 of the report) |
| Report | `python3 -m catsim.study_writeup > RESULTS.md` | the written results, every number read from the tables |
| Markdown tables | `python3 -m catsim.study_report > study_results/tables/report_tables.md` | |

Every run is saved as one JSON file the moment it finishes, in `study_results/runs/`. Its name records the scenario, the exact rule string (with parameters), the seed and a hash of every physical setting. Re-running a command skips finished runs, so an interrupted batch resumes where it stopped.

## Code layout
| Module | Role |
|---|---|
| `catsim/engine.py` | discrete-event simulation of one run: frames generated from the seed before any routing decision, per-site FCFS GPU pools, network delays and delay changes, reports (periodic or threshold; delay, loss, noise), probes, deadline-aware sites, server failures and slowdowns, all metrics, conservation check, true-state guard |
| `catsim/config.py` | the `Scenario` dataclass (every physical setting) |
| `study_config.json` | every parameter of this study (topology, loads, delays, budgets, events, seeds) |
| `catsim/study.py` | this study: topology (8 sites, delay matrix), traffic patterns (steady, bursty, shifting), experiment list, pilot candidates, frozen parameters |
| `catsim/rules.py`, `rules_v5.py`, `rules_v6.py` | existing rules (WRR, DWRR, LSQ, power-of-two, oracle, expected delay + drop, ours v6 and its ablations) |
| `catsim/baselines.py` | added baselines: Prequal HCL, Liyanage 2026, Dahlin LI, CATS-draft load sharing, LSQ-Sample, oracle + admission, the common rejection wrapper (admission control), parameter resolution |
| `catsim/experiments.py` | parallel, resumable execution |
| `catsim/study_analysis.py` | per-run and aggregate CSVs, 95% CIs, oracle gaps, paired comparisons, event windows |
| `catsim/study_plots.py` | the figures |
| `catsim/study_diagnostics.py`, `study_report.py`, `study_writeup.py` | diagnostics, markdown tables, `RESULTS.md` |
| `catsim/queueing.py`, `checks.py` | queueing formulas and the Erlang C check |
| `tests/test_simulator.py` | unit and integration tests |

## The simulated system
- **Sites.** 8 service sites ("servers"), each a GPU pool with one FCFS queue: 1, 2, 2, 3, 4, 5, 7 and 8 GPUs (homogeneous variant: 4 each). Each site has a capacity (GPUs × speed), a queue, frames in service, an availability (working GPUs) and a speed, all of which can change during a run (failures, slowdowns).
- **Delays.** Round trips depend on the ingress–site pair (`delay_matrix`): 8 ms to an ingress's own edge site, 18–22 ms to other edges, 25/35 ms to the regional sites, 50/60 ms to the core sites.
- **Work.** One frame = one GPU job, 100 ms on average (gamma, SCV 0.25). Deadline 300 ms end to end (strict) or 500 ms (relaxed). End-to-end time = trip to the site + queueing + processing + trip back.
- **Traffic.** Poisson; 4 ingresses with 40/30/20/10% by default.
  - Bursty: 5 s at twice the base rate at 30, 55 and 80 s, with the same average.
  - Shifting: the ingress shares rotate every 20 s.
  - Offered load is computed from the generated work (sum of job sizes) over the configured capacity, and reported per run.
- **Telemetry.** Each site reports (frames in the system, time measured, 4-byte arrivals counter) to every ingress every W seconds; each ingress keeps its own view.
  - Budgets: W = 10 / 2 / 0.5 s (low / medium / high), that is 53 / 264 / 1056 bytes/s per ingress with the counter.
  - Telemetry delay of 0 / 50 / 200 / 1000 ms on top of the path delay (reports only; probes see only the path delay).
  - Report loss and measurement noise (one supplementary experiment); threshold mode = sampled send-on-delta.
  - Probing rules spend exactly the budget of a report-based rule; a probe is 124 bytes (request + reply).
- **Sites are deadline-aware.** A frame whose deadline passed before service starts is discarded (expired).
- **Runs.** 100 s with a 20 s warm-up.

### Time scales
Kept from the Packet Patrol study, where they were set from the application (AI inference on camera frames): a 100 ms mean GPU job, a strict deadline of 3 mean service times, and round trips of up to 60 ms (a fifth of the deadline), so both the network and the queues matter. The pilot (seeds 101–105) checked that the range is useful: at 90% load the good rules meet about 95% of deadlines, at 130% load the best one about 66% (at most 1/1.3 ≈ 77% can be served), and plain round-robin collapses (`study_results/pilot_results.csv`, rows `timescale_check`).

### Events and their order
| Event | How it is modelled |
|---|---|
| Request arrival | Frames (id, arrival time, ingress, job size, deadline) are generated from the seed before the run; every rule sees the same list |
| Routing decision | At the frame's arrival at its ingress; the rule returns a site or a drop |
| Arrival at the site | After the one-way path delay (+ jitter when configured) |
| Service start / completion | FCFS per site; completion schedules the answer's trip back |
| Deadline expiration | A deadline-aware site discards a frame whose deadline has passed when its turn comes; a late answer is classified late |
| Telemetry measurement / delivery | Every W at each site (periodic, or threshold-checked); delivery after the path delay + telemetry delay; loss and noise optional |
| Active probing | Request and reply events (probing rules); the reply carries the site's state when the probe arrived |
| Server slowdown / failure / recovery | Speed changes and changes in working GPUs at given times, not announced to the rules |
| Network delay change | Path delays to one site × a factor during a window (`path_event`), not announced |
| Burst start / end, traffic shift | Built into the arrival process |

Ordering: the event heap is ordered by (time, insertion number). At equal times, heap events (reports, completions, probes, capacity changes) are handled before a new frame arriving at that moment, and heap events with equal times in the order they were scheduled. Each request is recorded with its id, arrival time, origin ingress, job size, deadline, assigned site (−1 = rejected) and final outcome (success, late, expired, rejected); every run checks that each frame ends in exactly one outcome.

## Experiments (seeds 201–210)
| id | content | runs |
|---|---|---|
| `grid_core_load`, `grid_core_delay`, `grid_core_pattern`, `grid_rest` | main grid: 12 algorithms × 4 loads × 4 telemetry delays × 3 patterns | 5,760 |
| `exp3_budget` | low/high budget; Prequal at its own 3 probes/query; threshold telemetry | 640 |
| `exp5_scalability` | 1 and 16 ingresses (4 in the grid) | 480 |
| `exp6_failures` | Core-2 loses half its GPUs 40–70 s; regional sites at half speed 35–70 s | 240 |
| `exp6_congestion` | paths to Core-2 twice as slow 40–70 s (network delay change, supplementary) | 120 |
| `exp7_admission` | the common rejection wrapper on 10 rules + oracle with admission | 440 |
| `exp8_ablation` | v6 with one mechanism off, steady and bursty | 400 |
| `cap_hom`, `deadline_relaxed` | homogeneous sites; 500 ms deadline | 480 |
| `exp_telemetry_faults` | 30% report loss, or noisy reports (supplementary) | 480 |
| `supp_lsq_sample` | LSQ-Sample (the LSQ paper's own update style) on the grid and the other scenarios (supplementary) | 630 |
| `grid_oracle_wrapped` | fresh-state oracle behind the common wrapper on the grid (reference, supplementary) | 440 |

Run order: the core experiments first, then the rest of the grid, then the supplementary ones. Parameters were frozen by the pilot before any final run (`frozen_params.json`, with the decision rule).

## Outputs
- `study_results/tables/`
  - `runs_all.csv` (every run), `agg_by_scenario.csv` (means and 95% CIs), `run_status.csv`
  - `main_comparison.csv` (the main table, by regime), `by_load.csv`, `oracle_gap.csv`, `paired_vs_v6.csv`, `v6_vs_best_rival.csv`
  - `telemetry_efficiency.csv` (configured and realized bytes), `delay_sensitivity.csv`, `delay_effect.csv`, `telemetry_faults.csv`
  - `admission_comparison.csv`, `ablation.csv`, `traffic_patterns.csv`, `burst_windows.csv`, `scalability.csv`, `failures.csv`, `event_windows.csv`, `capacity_deadline.csv`
  - `parameters.csv`, `diag_prequal_budget.csv`, `diag_lsq_herding.csv`, `diag_v6_bursts.csv`, `report_tables.md`
- `study_results/figures/`: `fig01`–`fig10`, PNG + PDF.
- `study_results/frozen_params.json`, `pilot_results.csv`, `pilot_log.txt`, `config_snapshot.json` (every scenario and rule string), `study_log_main.txt` and `study_log_supp.txt` (run logs).
- `study_results/runs/` and `pilot_runs/`: one JSON file per run (shipped separately, about 50 MB).

## Metric definitions (identical for every algorithm)
- **Deadline success** = answered on time / all frames generated after the warm-up. Rejected (dropped at the ingress), expired (discarded by the site) and late answers are failures. The four classes add up to 100% for every run (checked). Miss rate = 1 − success; admission rate = 1 − rejected.
- **Latency:** mean and p50/p95/p99 of answered frames (on time or late), end to end.
- **Throughput:** offered and completed frames per second; goodput = on-time frames per second.
- **Queueing delay:** site arrival → service start. Average and maximum frames at a site.
- **Utilization:** busy GPU-time / working GPU-time per site. Load imbalance = coefficient of variation of utilization over sites.
- **Telemetry bytes/s:** reports + probes, as sent, per ingress; number of messages. Realized usage is reported next to the configured budget.
- **Age of information:** at each decision, now − measurement time of the newest telemetry the ingress holds for the chosen site (mean and p95).
- **Estimation error:** |frames in that telemetry − true frames now|.
- **Decisions and switching rate:** routing decisions; share of an ingress's consecutive frames sent to a different site than the previous one.
- **Recovery time:** after an event ends, the time until the 3 s rolling success is back within 5 points of its level in the 5 s before the event (censored at the end of the run).
- **95% confidence intervals:** Student t over the 10 seeds. Differences are paired by seed.
