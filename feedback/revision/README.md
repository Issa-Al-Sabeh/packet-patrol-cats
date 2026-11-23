# Paper revision (23 Nov 2026): the numbers added to the paper

Everything in the paper that does not come from `feedback/final/analyze_final.py` comes from this folder.
Nothing here changes a frozen file (`FREEZE_v6.1.md`, `FREEZE_v6.2.md`) or a stored result.

## One command

```
python3 feedback/revision/run_all.py        # about 1-2 minutes on one core
```

It writes the output of every step to `results/*.txt`. The committed copies are the outputs the paper quotes,
so a re-run can be compared with them line by line (`git diff feedback/revision/results/`).

## What each step gives the paper

| Paper | Script | Reads | Result |
|---|---|---|---|
| Table II, telemetry by field (Section II) | `telemetry_fields.py` | `feedback/final/batch_{A,B,D}.csv` | `telemetry.md`, `telemetry.csv`, `results/telemetry.txt` |
| Table VI, frames by outcome (Section V-A) | `breakdown.py` | `feedback/final/batch_A.csv` | `results/breakdown.txt` |
| Batch C diagnosis (Section III-E) | `trace.py`, then `an_c.py` | re-runs 4 pilot runs (seed 101) | `results/batchC_traces.txt` |
| Planned vs realised site rates (Section V-B) | `trace.py`, then `an_b.py` | re-runs 12 runs of Batch B (seed 301) | `results/batchB_planned_vs_realised.txt` |
| Erlang C check (Section IV) | `erlang.py` | built-in check 1 of `catsim/checks.py` | `results/erlang.txt`, `results/erlang.json` |

## The traces

- Section III-E quotes v6.1's traces (`O_burst` and `O_dc_half`, the version diagnosed), then v6.2's: on `O_burst`
  after the fix, and on `O_dc_half` to show that v6.2 keeps the same capacity meter.

- `trace.py` wraps a frozen rule and reads its state after each decision: its estimate of the offered traffic, its drop
  share, its calibration factor and its capacity meter. It never changes a decision.
- Each traced run is checked against the stored result: every one of the 16 gives exactly the stored deadline success
  (`feedback/final/batch_B.csv` for seed 301; `feedback/batchC/pilot.csv` for pilot seed 101, where the frozen
  `ours_v62` is the candidate `v62c_fall`).
- One seed per run, as the paper says. The traces themselves go to `traces/` (not committed; `run_all.py` re-creates them).

## Single steps

```
python3 feedback/revision/telemetry_fields.py
python3 feedback/revision/breakdown.py
python3 feedback/revision/trace.py A O_burst ours_v61 101
python3 feedback/revision/trace.py A O_burst ours_v62 101
python3 feedback/revision/trace.py A O_dc_half ours_v61 101
python3 feedback/revision/trace.py A O_dc_half ours_v62 101
python3 feedback/revision/an_c.py
python3 feedback/revision/trace.py B <scenario> ours_v62|ours_v6 301   # O_130, B_130_stagger, O_130_W1,
                                                                        # L130_d50_steady_W0.5_R4_het_D300, N_130, O_surge
python3 feedback/revision/an_b.py
python3 feedback/revision/erlang.py
```

## Telemetry by field

The frozen simulator charges a fixed 62 B per report (`catsim/config.py`) plus 4 B (arrivals counter) and 2 B (drop
sum). No CATS document fixes a wire format yet, so the paper defines the report field by field, IPv6 and UDP headers
included: 66 B for v6.1, v6.2 and the admission rivals (64 B for v6). No rule of Batches A, B or D uses the report size
to decide anything, so no run was redone: `telemetry_fields.py` rescales the stored byte counts.
See `telemetry.md`.
