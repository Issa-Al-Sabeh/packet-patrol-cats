# The v6 study: 61 tests, 10 rules (Packet Patrol, CMPS 342)

This folder is the CATS site-selection simulator with **ours v6** added. One command runs the whole study.

```
pip install -r requirements.txt        # numpy, scipy, matplotlib (Python 3.9+)
python3 run_v6.py --pilot              # step 1 (optional): v6's threshold on spare seeds 101-105
python3 run_v6.py                      # step 2: the full study, 8,230 runs on fresh seeds 201-210
python3 -m catsim.v6_analysis          # step 3: the comparison tables (prints them, writes analysis_v6.json)
```

- The full study took 1 h 11 min on 2 cores. Use `--workers N` for more cores.
- Every run is saved the moment it finishes (`results_v6/runs/`). Run the same command again to continue after a stop.
- `python3 run_v6.py --tables` rebuilds `results_v6/tables/summary_v6.csv` from the saved runs.

## Where things are

| File | What it holds |
|---|---|
| `catsim/rules_v6.py` | **v6** (`SplitV6`), its three changes A/B/C, and the versions with one change switched off |
| `catsim/rules_v5.py` | v5 (`SplitDrop`), the v4 port, round-robin + drop variants, expected delay + drop |
| `catsim/rules.py` | the shared split (v2), v2 + measured speeds (`SplitSpeed`, `SpeedMeter`), round-robin, LSQ, the oracle |
| `catsim/v6.py` | the v6 study: rules, seeds (201-210 final, 101-105 pilot), the pilot decision rule and its outcome |
| `catsim/v5.py` | **the 61 tests**: `beirut_tests()` (36), `build_overload()` (11 + 2), `large_tests()` (12) |
| `catsim/config.py` | the `Scenario` settings: sites, servers, path delays, load, deadline, report interval, events |
| `catsim/engine.py` | one simulation run: frames, queues, reports, answers, drops (event by event) |
| `catsim/queueing.py` | late(n) with a Gamma fit, the birth-death ageing of a report, Erlang C |
| `catsim/checks.py` | the simulator checked against textbook M/M/c (Erlang C) results |
| `catsim/v6_analysis.py` | v6 against every rule, gap to the best rule, the ablations |
| `results_v6/tables/summary_v6.csv` | the final results: every test x rule, mean miss %, 95% interval, the 10 seed values |

## The 61 tests

**Beirut network** (3 sites: Hamra 2 servers, Jdeideh 4, DC 8; 8 / 16 / 60 ms; 4 ingresses; 300 ms deadline; reports every 5 s; 85% load), 36 tests:
- Main scenario
- Report interval 0.2, 0.5, 1, 2, 10, 30 s
- Load 50%, 70%, 95%
- Deadline 200 ms, 500 ms
- Job sizes exponential, heavy-tailed
- 2, 8, 16 ingresses; equal traffic between ingresses; equal sites 4/4/4; staggered reports
- Delay jitter +5 ms, +20 ms; 10% and 30% of reports lost; reports up to 2 s late
- Load jump 60% to 95%; Hamra loses 1 server halfway
- Server failure and recovery; shared GPUs; wrong weights (DC told 8 servers, 6 work); rush hour 60-95-60%; one ingress doubles its frames; mixed short and long jobs; DC path congestion
- Held out: DC failure and recovery; slow GPUs at Jdeideh

**Overload**, 13 tests (sites discard frames already past their deadline):
- Beirut: load 100%, 110%, 130%, 150%; burst 85% to 140%; rush hour to 120%; one ingress doubles (119%); the DC loses half its servers; load 130% with reports every 1 s and every 10 s; load 130% without discarding
- Large network: load 130%; burst 85% to 140%

**Large network** (6 sites with 2, 2, 4, 4, 6 and 12 servers, 8 to 60 ms; 12 ingresses), 12 tests:
- Main; reports every 1 s and 10 s; load 70%, 95%
- One server failure; two failures; DC failure; shared GPUs; wrong weights; slow GPUs; 30% of reports lost

## Rules compared

v6, v5, v2 + speeds, v4 (port), round-robin, round-robin + speeds, both with drop, LSQ, the oracle (below capacity); expected delay + drop and v4 without dropping in the overload tests. Plus v6 without A, without B and without C (ablations).

## Main result (fresh seeds 201-210)

| Rule | Average gap to the best rule (points) | Worst gap | Within 0.5 points of the best |
|---|---|---|---|
| v6 | 0.31 | 3.40 | 52 of 61 |
| v5 | 0.75 | 6.73 | 31 of 61 |
| RR + speeds + drop | 1.67 | 11.90 | 32 of 61 |
| v4 (port) | 5.45 | 81.51 | 22 of 61 |
