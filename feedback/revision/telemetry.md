# Telemetry with the report defined field by field, headers included

- Added after the freeze (23 Nov 2026). Written by `feedback/revision/telemetry_fields.py` from `feedback/final/batch_{A,B,D}.csv`. No run was redone: the report size is only counted, never used by a rule of Batches A, B or D, so every success number is unchanged.
- The frozen accounting (62 B per report + 4 + 2) stays in `feedback/final.md`, Table 8.

## The report

| Field | Bytes | Sent by | Why this size |
|---|---|---|---|
| IPv6 header | 40 | all report rules | fixed IPv6 header (RFC 8200); link-layer headers vary per hop and are not counted |
| UDP header | 8 | all report rules | RFC 768 |
| Service ID | 2 | all report rules | which service the report is for (one service here; room for 65,535) |
| Frames at the site q_s | 2 | all report rules | unsigned; a run has at most 40,875 frames, below 65,535 |
| Time measured t_s | 8 | all report rules | 64-bit NTP timestamp format (RFC 5905) |
| Arrivals since last report A_s | 4 | rules with the counter | as frozen |
| Sum of drop counts D_s | 2 | v6.1, v6.2, admission rivals | as frozen |
| **One report** | **66** (v6.1, v6.2, admission rivals); **64** (v6) | | frozen accounting: 68 and 66 |
| Own drop count (ingress to site) | 2 | v6.1, v6.2, admission rivals | written on a frame sent anyway, at most every W/4: no header of its own |

## Bytes per second per ingress

Formula: S x (one report) / W. Measured: mean over all runs of Batch A (20 seeds), reports plus drop counts.

| Network (S, W) | Formula, v6.2 | v6.2 | v6.1 | v6 | Tuned rival | Frozen rival | Round-robin | v6.2 vs v6 |
|---|---|---|---|---|---|---|---|---|
| Beirut (3, 5 s) | 39.6 | 39.0 | 39.1 | 37.1 | 39.0 | 38.9 | 0.0 | +5.1% |
| 8 sites (8, 2 s) | 264.0 | 261.3 | 261.4 | 250.9 | 261.5 | 261.2 | 0.0 | +4.1% |
| New (5, 3 s) | 110.0 | 109.0 | 109.1 | 104.5 | 109.1 | 108.8 | 0.0 | +4.3% |

Same table with the frozen accounting (62 B + 4 + 2), for comparison:

| Network | Formula, v6.2 | v6.2 | v6.1 | v6 | Tuned rival | Frozen rival | Round-robin | v6.2 vs v6 |
|---|---|---|---|---|---|---|---|---|
| Beirut | 40.8 | 40.2 | 40.2 | 38.3 | 40.1 | 40.0 | 0.0 | +5.0% |
| 8 sites | 272.0 | 269.1 | 269.3 | 258.7 | 269.3 | 269.0 | 0.0 | +4.0% |
| New | 113.3 | 112.3 | 112.3 | 107.8 | 112.3 | 112.1 | 0.0 | +4.2% |

## Why the measured value is below the formula

- A report's bytes are counted when it is sent, lost or not (`catsim/engine.py`), so losses do not lower it.
- A run of T seconds holds fewer than T / W rounds of reports (on Beirut, 29 rounds in 150 s, not 30).
- The drop counts the ingresses write on their frames add a little (Batch A, v6.2):
  - Beirut: reports 38.28 + drop counts 0.75 = 39.03 B/s
  - 8 sites: reports 258.72 + drop counts 2.55 = 261.27 B/s
  - New: reports 107.80 + drop counts 1.22 = 109.02 B/s

Every other batch: `telemetry.csv` (one row per run, old and new bytes/s).
