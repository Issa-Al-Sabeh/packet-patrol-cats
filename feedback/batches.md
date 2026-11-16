# Batches A and B: first pass on the evaluation seeds (301 to 305)

- Evaluation of ours v6.1 as frozen on 15 Nov 2026 (tag `v6.1-frozen`, `FREEZE_v6.1.md`).
- The scenarios, the rules, the seeds and the rules of the analysis were fixed before any of these runs (`catsim/v61.py`).
- These are the first results on seeds 301 to 305. Nothing was changed after seeing them.
- This file is written by `feedback/batches/analyze_batches.py` from `feedback/batches/batch_A.csv` and `batch_B.csv`. Runner: `feedback/batches/run_batches.py`.

## How to read the numbers

- **Deadline success** = frames answered within 300 ms ÷ all frames generated after the warm-up.
- A frame dropped at the ingress, discarded at a site or answered late is a miss.
- **Difference** = v6.1 minus the other rule, seed by seed (same frames for both), then the mean and its 95% interval (Student's t, 4 degrees of freedom on five seeds).
- "Clearly ahead" or "clearly behind" = the whole interval is on one side of 0.
- Every scenario is in the tables. No scenario, rule or seed was removed.

## Checks

| Check | Result | Detail |
|---|---|---|
| Batch A: every run of the plan is there | pass | 770 of 770 runs (22 scenarios × 7 rules × 5 seeds) |
| Batch A: every scenario and rule has the same seeds | pass | seeds 301 to 305 |
| Batch A: every frame ends once (on time, late, discarded or rejected) | pass | 18,878,720 frames in 770 runs |
| Batch A: every rule saw the same frames (same scenario, same seed) | pass | needed for paired differences |
| Batch A: no missing value | pass |  |
| Batch A: run on the frozen code | pass | 31 frozen files match FREEZE_v6.1.md; Python 3.13.18, numpy 2.5.3, scipy 1.18.1; finished 2026-11-15 22:16:58 |
| Batch B: every run of the plan is there | pass | 280 of 280 runs (14 scenarios × 4 rules × 5 seeds) |
| Batch B: every scenario and rule has the same seeds | pass | seeds 301 to 305 |
| Batch B: every frame ends once (on time, late, discarded or rejected) | pass | 8,233,828 frames in 280 runs |
| Batch B: every rule saw the same frames (same scenario, same seed) | pass | needed for paired differences |
| Batch B: no missing value | pass |  |
| Batch B: run on the frozen code | pass | 31 frozen files match FREEZE_v6.1.md; Python 3.13.18, numpy 2.5.3, scipy 1.18.1; finished 2026-11-16 15:28:59 |
| Runs that Batch A and Batch B share give the same numbers (the recorder of Batch B changes nothing) | pass | 75 shared runs |

## Batch A: where does the gain come from?

- 22 scenarios × 7 rules × 5 seeds = 770 runs.
- \* = pilot scenario: v6.1's settings were chosen on it, with other seeds (101 to 105).
- Every other Beirut scenario, the 8-site network and the new network took no part in any choice.

**Table A1. Deadline success, % (rejected share, % in brackets). Mean of five seeds.**

| Network | Scenario | v6.1 | RR + matched adm. | Static + matched adm. | v6.1 no penalty | v6.1 no drop | v6 (frozen) | Round-robin |
|---|---|---|---|---|---|---|---|---|
| Beirut | Main scenario (load 85%) * | 96.6 (0.0) | 96.6 (0.0) | 96.6 (0.0) | 96.6 (0.0) | 96.6 (0.0) | 96.6 (0.0) | 96.6 (0.0) |
| Beirut | Load 95% * | 85.7 (4.1) | 79.5 (0.5) | 79.5 (0.5) | 85.6 (4.1) | 75.4 (0.0) | 84.4 (4.1) | 77.8 (0.0) |
| Beirut | Load 110% | 76.3 (16.6) | 72.4 (13.4) | 72.4 (13.4) | 75.2 (16.6) | 21.7 (0.0) | 76.1 (16.7) | 21.9 (0.0) |
| Beirut | Load 130% * | 63.9 (29.8) | 61.9 (26.9) | 61.9 (26.9) | 64.3 (29.4) | 4.7 (0.0) | 64.0 (29.8) | 4.6 (0.0) |
| Beirut | Load 150% | 56.6 (38.7) | 53.7 (36.5) | 53.7 (36.5) | 56.2 (38.6) | 1.9 (0.0) | 56.2 (39.0) | 1.7 (0.0) |
| Beirut | Burst: 85%, then 140% for 20 s * | 82.6 (11.7) | 74.3 (4.4) | 74.3 (4.4) | 82.6 (11.6) | 74.3 (0.0) | 82.3 (12.2) | 74.0 (0.0) |
| Beirut | Ingress A doubles for 50 s | 81.7 (12.9) | 69.5 (6.6) | 69.5 (6.6) | 82.0 (12.5) | 56.3 (0.0) | 80.9 (12.4) | 56.2 (0.0) |
| Beirut | Hamra loses 1 of 2 servers for 50 s * | 92.1 (1.1) | 86.2 (0.0) | 86.2 (0.0) | 91.6 (0.6) | 92.3 (0.0) | 92.3 (0.0) | 86.2 (0.0) |
| Beirut | DC loses 4 of 8 servers for 60 s | 72.9 (18.1) | 71.2 (0.0) | 71.2 (0.0) | 75.5 (13.7) | 69.4 (0.0) | 73.5 (16.9) | 71.2 (0.0) |
| Beirut | Wrong weights (DC has 6, rules told 8) * | 88.8 (0.0) | 74.1 (0.0) | 74.1 (0.0) | 88.8 (0.0) | 88.8 (0.0) | 88.8 (0.0) | 74.1 (0.0) |
| 8 sites | Load 90%, steady | 94.7 (0.4) | 95.1 (0.0) | 95.1 (0.0) | 94.6 (0.4) | 94.8 (0.0) | 94.9 (0.0) | 95.1 (0.0) |
| 8 sites | Load 110%, steady | 78.1 (17.8) | 75.5 (13.6) | 75.5 (13.6) | 78.0 (17.7) | 17.2 (0.0) | 78.1 (17.7) | 16.8 (0.0) |
| 8 sites | Load 130%, steady | 65.7 (30.9) | 63.5 (27.0) | 63.5 (27.0) | 65.7 (30.9) | 4.5 (0.0) | 66.1 (31.0) | 3.8 (0.0) |
| 8 sites | Load 90%, bursty | 73.8 (19.4) | 67.3 (3.6) | 67.3 (3.6) | 73.9 (19.3) | 68.8 (0.0) | 74.2 (19.1) | 68.7 (0.0) |
| 8 sites | Load 110%, bursty | 62.8 (28.8) | 58.8 (12.5) | 58.8 (12.5) | 62.9 (28.7) | 60.4 (0.0) | 63.5 (27.6) | 61.1 (0.0) |
| 8 sites | Load 130%, bursty | 53.3 (40.0) | 49.8 (25.6) | 49.8 (25.6) | 53.1 (40.0) | 11.6 (0.0) | 54.6 (36.9) | 11.2 (0.0) |
| New | Load 85% | 94.2 (0.0) | 94.1 (0.0) | 94.2 (0.0) | 94.2 (0.0) | 94.2 (0.0) | 94.2 (0.0) | 94.1 (0.0) |
| New | Load 95% | 84.1 (4.2) | 78.3 (0.6) | 78.6 (0.6) | 83.6 (4.3) | 72.5 (0.0) | 83.8 (4.0) | 74.9 (0.0) |
| New | Load 115% | 70.0 (21.0) | 66.5 (17.2) | 66.6 (17.2) | 70.3 (20.8) | 10.8 (0.0) | 70.7 (20.8) | 9.5 (0.0) |
| New | Load 130% | 62.4 (29.6) | 59.7 (26.9) | 59.2 (26.8) | 62.3 (29.4) | 3.5 (0.0) | 62.8 (30.2) | 3.5 (0.0) |
| New | Burst: 85%, then 140% for 20 s | 82.1 (10.5) | 73.9 (5.4) | 74.1 (5.4) | 82.1 (10.6) | 72.9 (0.0) | 81.8 (10.9) | 72.9 (0.0) |
| New | Regional DC loses 2 of 6 servers for 50 s | 87.2 (1.8) | 75.3 (0.0) | 75.5 (0.0) | 87.5 (1.7) | 84.6 (0.0) | 84.9 (0.1) | 75.3 (0.0) |

- Rejected = dropped at the ingress. Round-robin and "v6.1 no drop" never drop.
- The rest of the misses are frames discarded at a site or answered late (in `tables/A_success.csv`).

**Table A2. v6.1 minus each rule: difference in success, points, paired by seed, with the 95% interval. Bold = the interval does not contain 0.**

| Network | Scenario | − RR + matched adm. | − Static + matched adm. | − v6.1 no penalty | − v6.1 no drop | − v6 (frozen) | − Round-robin |
|---|---|---|---|---|---|---|---|
| Beirut | Main scenario (load 85%) * | same runs | same runs | same runs | same runs | same runs | same runs |
| Beirut | Load 95% * | **+6.3 ± 1.7** | **+6.3 ± 1.7** | +0.1 ± 1.1 | **+10.3 ± 6.3** | +1.3 ± 3.1 | **+7.9 ± 3.2** |
| Beirut | Load 110% | **+3.9 ± 1.5** | **+3.9 ± 1.5** | **+1.1 ± 1.1** | **+54.6 ± 3.5** | +0.2 ± 1.1 | **+54.4 ± 4.3** |
| Beirut | Load 130% * | **+2.0 ± 1.5** | **+2.0 ± 1.5** | -0.4 ± 0.8 | **+59.2 ± 1.0** | -0.1 ± 0.6 | **+59.3 ± 0.9** |
| Beirut | Load 150% | **+2.9 ± 1.6** | **+2.9 ± 1.6** | **+0.4 ± 0.3** | **+54.8 ± 1.1** | **+0.5 ± 0.5** | **+55.0 ± 1.0** |
| Beirut | Burst: 85%, then 140% for 20 s * | **+8.2 ± 1.8** | **+8.2 ± 1.8** | -0.1 ± 0.2 | **+8.2 ± 1.9** | +0.3 ± 1.0 | **+8.5 ± 1.9** |
| Beirut | Ingress A doubles for 50 s | **+12.1 ± 3.1** | **+12.1 ± 3.1** | -0.3 ± 0.6 | **+25.4 ± 1.4** | +0.8 ± 1.6 | **+25.5 ± 1.7** |
| Beirut | Hamra loses 1 of 2 servers for 50 s * | **+5.9 ± 0.6** | **+5.9 ± 0.6** | +0.5 ± 0.8 | -0.2 ± 1.2 | -0.2 ± 1.4 | **+5.9 ± 0.6** |
| Beirut | DC loses 4 of 8 servers for 60 s | **+1.8 ± 1.2** | **+1.8 ± 1.2** | **-2.5 ± 1.4** | **+3.5 ± 2.0** | -0.6 ± 1.6 | **+1.8 ± 1.2** |
| Beirut | Wrong weights (DC has 6, rules told 8) * | **+14.7 ± 9.8** | **+14.7 ± 9.8** | same runs | same runs | same runs | **+14.7 ± 9.8** |
| 8 sites | Load 90%, steady | -0.4 ± 0.5 | -0.4 ± 0.5 | +0.1 ± 0.5 | -0.1 ± 1.1 | -0.2 ± 0.6 | -0.4 ± 0.5 |
| 8 sites | Load 110%, steady | **+2.5 ± 2.0** | **+2.5 ± 2.0** | +0.0 ± 0.6 | **+60.8 ± 1.9** | -0.0 ± 0.9 | **+61.3 ± 1.5** |
| 8 sites | Load 130%, steady | **+2.2 ± 1.0** | **+2.2 ± 1.0** | -0.0 ± 0.8 | **+61.1 ± 0.7** | **-0.4 ± 0.3** | **+61.8 ± 0.7** |
| 8 sites | Load 90%, bursty | **+6.5 ± 1.3** | **+6.5 ± 1.3** | -0.1 ± 1.0 | **+5.0 ± 1.3** | -0.4 ± 0.7 | **+5.1 ± 1.3** |
| 8 sites | Load 110%, bursty | **+4.0 ± 1.5** | **+4.0 ± 1.5** | -0.1 ± 0.4 | **+2.4 ± 1.5** | -0.8 ± 1.6 | **+1.6 ± 1.4** |
| 8 sites | Load 130%, bursty | **+3.5 ± 0.4** | **+3.5 ± 0.4** | **+0.2 ± 0.2** | **+41.7 ± 0.8** | **-1.4 ± 0.7** | **+42.1 ± 0.7** |
| New | Load 85% | +0.1 ± 0.2 | -0.0 ± 0.2 | same runs | same runs | same runs | +0.1 ± 0.2 |
| New | Load 95% | **+5.7 ± 2.0** | **+5.5 ± 2.6** | +0.5 ± 0.7 | **+11.6 ± 5.0** | +0.3 ± 0.9 | **+9.2 ± 4.8** |
| New | Load 115% | **+3.5 ± 0.9** | **+3.4 ± 0.7** | -0.3 ± 0.8 | **+59.3 ± 2.2** | -0.7 ± 1.1 | **+60.6 ± 1.4** |
| New | Load 130% | **+2.7 ± 1.8** | **+3.2 ± 0.7** | +0.0 ± 0.4 | **+58.8 ± 0.9** | -0.5 ± 0.5 | **+58.9 ± 1.1** |
| New | Burst: 85%, then 140% for 20 s | **+8.2 ± 1.2** | **+8.1 ± 0.9** | +0.1 ± 0.2 | **+9.2 ± 0.9** | +0.3 ± 0.5 | **+9.3 ± 0.9** |
| New | Regional DC loses 2 of 6 servers for 50 s | **+11.9 ± 1.5** | **+11.8 ± 1.4** | -0.3 ± 1.5 | **+2.6 ± 1.7** | **+2.4 ± 2.1** | **+11.9 ± 1.5** |

- Positive = v6.1 is ahead. "same runs" = the two rules gave the same result in every seed.

**The static split is not a separate baseline (found after the runs).**

- "Static + matched admission" gave the same runs as "RR + matched admission" in 10 of 10 Beirut scenarios, 6 of 6 8 sites scenarios, 0 of 6 New scenarios.
- In the other 6 scenarios the two differ by at most 0.5 points of success, and never clearly (6 of 6 intervals contain 0).
- Reason: on all three networks the frozen static split uses exactly the capacity shares, at every ingress (`check_static.py`, `tables/static_shares.csv`).
- Its design load is 95% and no site may go above 95%: every site would have to sit at exactly 95%, which the 1% grid cannot do (Beirut: 99 of 100 pieces fit, 8 sites: 97 of 100 pieces fit, New: 98 of 100 pieces fit), so the rule falls back to the capacity shares.
- So it is round-robin with another send order. The column is kept (it was frozen), but it does **not** show "the gain over the best split that needs no reports".
- On the new network, where the largest site is far, a static split that looks at the deadline was never tested.

**Table A2b. The primary comparison in detail: v6.1 against RR + matched admission. Shares in % of all frames; differences in points, paired by seed.**

| Network | Scenario | Success: difference | Rejected: v6.1 | Rejected: RR + adm. | Rejected: difference | Late or discarded: v6.1 | Late or discarded: RR + adm. | Late or discarded: difference |
|---|---|---|---|---|---|---|---|---|
| Beirut | Main scenario (load 85%) * | same runs | 0.0 | 0.0 | same runs | 3.4 | 3.4 | same runs |
| Beirut | Load 95% * | **+6.3 ± 1.7** | 4.1 | 0.5 | **+3.6 ± 1.1** | 10.1 | 20.0 | **-9.8 ± 0.8** |
| Beirut | Load 110% | **+3.9 ± 1.5** | 16.6 | 13.4 | **+3.2 ± 1.1** | 7.1 | 14.2 | **-7.1 ± 2.3** |
| Beirut | Load 130% * | **+2.0 ± 1.5** | 29.8 | 26.9 | **+2.8 ± 0.7** | 6.3 | 11.1 | **-4.8 ± 1.9** |
| Beirut | Load 150% | **+2.9 ± 1.6** | 38.7 | 36.5 | **+2.2 ± 0.2** | 4.7 | 9.8 | **-5.1 ± 1.7** |
| Beirut | Burst: 85%, then 140% for 20 s * | **+8.2 ± 1.8** | 11.7 | 4.4 | **+7.3 ± 1.0** | 5.8 | 21.3 | **-15.5 ± 1.0** |
| Beirut | Ingress A doubles for 50 s | **+12.1 ± 3.1** | 12.9 | 6.6 | **+6.3 ± 2.0** | 5.4 | 23.8 | **-18.4 ± 1.8** |
| Beirut | Hamra loses 1 of 2 servers for 50 s * | **+5.9 ± 0.6** | 1.1 | 0.0 | **+1.1 ± 0.3** | 6.8 | 13.8 | **-6.9 ± 0.5** |
| Beirut | DC loses 4 of 8 servers for 60 s | **+1.8 ± 1.2** | 18.1 | 0.0 | **+18.1 ± 0.6** | 8.9 | 28.8 | **-19.9 ± 1.2** |
| Beirut | Wrong weights (DC has 6, rules told 8) * | **+14.7 ± 9.8** | 0.0 | 0.0 | same runs | 11.2 | 25.9 | **-14.7 ± 9.8** |
| 8 sites | Load 90%, steady | -0.4 ± 0.5 | 0.4 | 0.0 | **+0.4 ± 0.3** | 4.9 | 4.9 | -0.0 ± 0.7 |
| 8 sites | Load 110%, steady | **+2.5 ± 2.0** | 17.8 | 13.6 | **+4.2 ± 0.2** | 4.1 | 10.9 | **-6.8 ± 2.1** |
| 8 sites | Load 130%, steady | **+2.2 ± 1.0** | 30.9 | 27.0 | **+4.0 ± 0.1** | 3.4 | 9.5 | **-6.1 ± 1.0** |
| 8 sites | Load 90%, bursty | **+6.5 ± 1.3** | 19.4 | 3.6 | **+15.8 ± 0.7** | 6.8 | 29.1 | **-22.3 ± 0.7** |
| 8 sites | Load 110%, bursty | **+4.0 ± 1.5** | 28.8 | 12.5 | **+16.4 ± 0.9** | 8.4 | 28.7 | **-20.3 ± 0.8** |
| 8 sites | Load 130%, bursty | **+3.5 ± 0.4** | 40.0 | 25.6 | **+14.4 ± 0.5** | 6.7 | 24.7 | **-17.9 ± 0.4** |
| New | Load 85% | +0.1 ± 0.2 | 0.0 | 0.0 | same runs | 5.8 | 5.9 | -0.1 ± 0.2 |
| New | Load 95% | **+5.7 ± 2.0** | 4.2 | 0.6 | **+3.6 ± 0.8** | 11.7 | 21.1 | **-9.3 ± 2.5** |
| New | Load 115% | **+3.5 ± 0.9** | 21.0 | 17.2 | **+3.9 ± 0.6** | 8.9 | 16.3 | **-7.4 ± 0.9** |
| New | Load 130% | **+2.7 ± 1.8** | 29.6 | 26.9 | **+2.7 ± 0.2** | 8.1 | 13.5 | **-5.4 ± 1.8** |
| New | Burst: 85%, then 140% for 20 s | **+8.2 ± 1.2** | 10.5 | 5.4 | **+5.1 ± 0.4** | 7.3 | 20.6 | **-13.3 ± 1.0** |
| New | Regional DC loses 2 of 6 servers for 50 s | **+11.9 ± 1.5** | 1.8 | 0.0 | **+1.8 ± 0.6** | 11.0 | 24.7 | **-13.7 ± 1.2** |

- Late or discarded = admitted, then discarded at a site or answered after the deadline.
- Success difference = −(rejected difference + late-or-discarded difference).
- "Matched" admission = the same estimate from the same reports, and the same right to drop. It is **not** the same amount dropped: the wrapper drops what exceeds 95% of the configured capacity; v6.1 starts at 90% of the measured capacity and re-plans on a burst.

**Table A6. Routing alone: v6.1 without dropping against round-robin (neither drops). Success, %, and the paired difference.**

| Network | Scenario | v6.1 no drop | Round-robin | Difference |
|---|---|---|---|---|
| Beirut | Main scenario (load 85%) * | 96.6 | 96.6 | same runs |
| Beirut | Load 95% * | 75.4 | 77.8 | -2.4 ± 3.2 |
| Beirut | Load 110% | 21.7 | 21.9 | -0.1 ± 1.6 |
| Beirut | Load 130% * | 4.7 | 4.6 | +0.1 ± 0.3 |
| Beirut | Load 150% | 1.9 | 1.7 | **+0.2 ± 0.1** |
| Beirut | Burst: 85%, then 140% for 20 s * | 74.3 | 74.0 | +0.3 ± 0.4 |
| Beirut | Ingress A doubles for 50 s | 56.3 | 56.2 | +0.2 ± 0.6 |
| Beirut | Hamra loses 1 of 2 servers for 50 s * | 92.3 | 86.2 | **+6.1 ± 1.1** |
| Beirut | DC loses 4 of 8 servers for 60 s | 69.4 | 71.2 | **-1.7 ± 1.3** |
| Beirut | Wrong weights (DC has 6, rules told 8) * | 88.8 | 74.1 | **+14.7 ± 9.8** |
| 8 sites | Load 90%, steady | 94.8 | 95.1 | -0.2 ± 0.6 |
| 8 sites | Load 110%, steady | 17.2 | 16.8 | +0.4 ± 1.0 |
| 8 sites | Load 130%, steady | 4.5 | 3.8 | **+0.7 ± 0.1** |
| 8 sites | Load 90%, bursty | 68.8 | 68.7 | +0.1 ± 0.2 |
| 8 sites | Load 110%, bursty | 60.4 | 61.1 | **-0.8 ± 0.8** |
| 8 sites | Load 130%, bursty | 11.6 | 11.2 | +0.4 ± 1.0 |
| New | Load 85% | 94.2 | 94.1 | +0.1 ± 0.2 |
| New | Load 95% | 72.5 | 74.9 | **-2.4 ± 1.4** |
| New | Load 115% | 10.8 | 9.5 | **+1.3 ± 0.8** |
| New | Load 130% | 3.5 | 3.5 | +0.1 ± 0.2 |
| New | Burst: 85%, then 140% for 20 s | 72.9 | 72.9 | +0.0 ± 0.2 |
| New | Regional DC loses 2 of 6 servers for 50 s | 84.6 | 75.3 | **+9.3 ± 1.7** |

**Table A3. In how many scenarios is the first rule clearly ahead, clearly behind, or neither?**

| Comparison | Clearly ahead | Clearly behind | No clear difference | Same runs | Mean difference over the 22 scenarios | What it shows |
|---|---|---|---|---|---|---|
| v6.1 − RR + matched adm. | 19 | 0 | 2 | 1 | +4.9 ± 0.4 | the gain over no steering, at equal telemetry and equal chance to drop |
| v6.1 − Static + matched adm. | 19 | 0 | 2 | 1 | +4.9 ± 0.4 | planned: the gain over the best split that needs no reports; in fact the capacity split again (see above) |
| v6.1 − v6.1 no penalty | 3 | 1 | 15 | 3 | -0.0 ± 0.1 | what the backlog penalty adds |
| v6.1 − v6.1 no drop | 17 | 0 | 2 | 3 | +24.0 ± 0.5 | what admission adds to v6.1's routing |
| v6.1 − v6 (frozen) | 2 | 2 | 15 | 3 | +0.0 ± 0.4 | what the three changes of v6.1 did |
| v6.1 − Round-robin | 19 | 0 | 2 | 1 | +25.2 ± 0.8 | the floor |
| v6.1 no drop − Round-robin | 6 | 3 | 12 | 1 | +1.2 ± 0.6 | what v6.1's routing adds when nothing may be dropped |

- Mean difference: averaged over the scenarios inside each seed, then the 95% interval over the seeds.

**Table A4. The same mean difference (points), by group of scenarios.**

| Comparison | All scenarios (22) | Pilot scenarios (6) | Other scenarios (16) | Beirut (10) | 8 sites (6) | New (6) |
|---|---|---|---|---|---|---|
| v6.1 − RR + matched adm. | +4.9 ± 0.4 | +6.2 ± 1.5 | +4.4 ± 0.4 | +5.8 ± 1.0 | +3.1 ± 0.7 | +5.3 ± 0.4 |
| v6.1 − Static + matched adm. | +4.9 ± 0.4 | +6.2 ± 1.5 | +4.4 ± 0.4 | +5.8 ± 1.0 | +3.1 ± 0.7 | +5.3 ± 0.4 |
| v6.1 − v6.1 no penalty | -0.0 ± 0.1 | +0.0 ± 0.2 | -0.1 ± 0.2 | -0.1 ± 0.2 | +0.0 ± 0.4 | +0.0 ± 0.4 |
| v6.1 − v6.1 no drop | +24.0 ± 0.5 | +12.9 ± 1.3 | +28.2 ± 0.4 | +21.6 ± 0.7 | +28.5 ± 0.3 | +23.6 ± 1.0 |
| v6.1 − v6 (frozen) | +0.0 ± 0.4 | +0.2 ± 0.8 | -0.0 ± 0.3 | +0.2 ± 0.6 | -0.5 ± 0.2 | +0.3 ± 0.5 |
| v6.1 − Round-robin | +25.2 ± 0.8 | +16.1 ± 1.7 | +28.6 ± 0.4 | +23.3 ± 1.3 | +28.6 ± 0.3 | +25.0 ± 0.8 |
| v6.1 no drop − Round-robin | +1.2 ± 0.6 | +3.1 ± 1.8 | +0.5 ± 0.3 | +1.7 ± 1.2 | +0.1 ± 0.2 | +1.4 ± 0.4 |

**Table A5. Mean deadline success, %, by group of scenarios (mean of the scenario means).**

| Rule | All scenarios (22) | Pilot scenarios (6) | Other scenarios (16) | Beirut (10) | 8 sites (6) | New (6) |
|---|---|---|---|---|---|---|
| v6.1 | 77.5 | 85.0 | 74.7 | 79.7 | 71.4 | 80.0 |
| RR + matched adm. | 72.6 | 78.8 | 70.3 | 73.9 | 68.3 | 74.7 |
| Static + matched adm. | 72.6 | 78.8 | 70.3 | 73.9 | 68.3 | 74.7 |
| v6.1 no penalty | 77.6 | 84.9 | 74.8 | 79.8 | 71.4 | 80.0 |
| v6.1 no drop | 53.5 | 72.0 | 46.6 | 58.1 | 42.9 | 56.4 |
| v6 (frozen) | 77.5 | 84.7 | 74.8 | 79.5 | 71.9 | 79.7 |
| Round-robin | 52.3 | 68.9 | 46.1 | 56.4 | 42.8 | 55.0 |

**Where v6.1 is clearly behind (every case, none left out).**

- Beirut, DC loses 4 of 8 servers for 60 s: -2.5 ± 1.4 points against v6.1 no penalty.
- 8 sites, Load 130%, steady: -0.4 ± 0.3 points against v6 (frozen).
- 8 sites, Load 130%, bursty: -1.4 ± 0.7 points against v6 (frozen).
- Routing alone (v6.1 no drop) is clearly behind round-robin on Beirut, DC loses 4 of 8 servers for 60 s: -1.7 ± 1.3 points.
- Routing alone (v6.1 no drop) is clearly behind round-robin on 8 sites, Load 110%, bursty: -0.8 ± 0.8 points.
- Routing alone (v6.1 no drop) is clearly behind round-robin on New, Load 95%: -2.4 ± 1.4 points.

- Caution: Table A2 holds 120 intervals at 95%. About 6 of them would leave out 0 by chance alone, so a single bold cell is weak evidence. No correction was fixed at the freeze; none is applied.
- Five seeds give wide intervals. Seeds 306 to 310 are still unused.

## Batch B: does the estimate hold when ingresses differ?

- 14 scenarios × 4 rules × 5 seeds = 280 runs.
- Every scenario is in overload for at least part of the run: the estimate only matters while frames are dropped.
- Two pairs differ only in the estimate: v6.1 against v6 (v6.1 also has changes 2 and 3), and round-robin + admission with the drop counter against the same wrapper with its own drop share (nothing else differs).

**Table B1. Estimate of the offered traffic ÷ the truth: lowest ingress to highest ingress (1.00 = right). Mean of five seeds.**

| Network | Scenario | v6.1 (drop counter) | v6 (own share) | RR + adm. (drop counter) | RR + adm. (own share) |
|---|---|---|---|---|---|
| Beirut | Load 130%, shares 40/30/20/10% * | 1.00 to 1.00 | 0.82 to 1.06 | 1.00 to 1.00 | 1.00 to 1.00 |
| Beirut | Load 130%, equal shares | 1.00 to 1.00 | 0.98 to 1.02 | 1.00 to 1.00 | 1.00 to 1.00 |
| Beirut | Load 130%, staggered reports | 1.02 to 1.03 | 0.91 to 1.07 | 1.02 to 1.03 | 1.02 to 1.03 |
| Beirut | Load 130%, 30% of reports lost | 0.99 to 1.02 | 0.84 to 1.19 | 0.99 to 1.00 | 0.90 to 1.04 |
| Beirut | Load 130%, reports every 1 s | 1.00 to 1.00 | 0.73 to 1.38 | 1.00 to 1.00 | 1.00 to 1.01 |
| Beirut | Ingress A doubles for 50 s | 1.03 to 1.04 | 0.92 to 1.12 | 1.01 to 1.01 | 1.01 to 1.01 |
| 8 sites | Load 130%, steady | 1.00 to 1.00 | 0.81 to 1.04 | 1.00 to 1.00 | 1.00 to 1.00 |
| 8 sites | Load 130%, shifting | 0.99 to 1.01 | 0.89 to 1.05 | 1.00 to 1.00 | 1.00 to 1.00 |
| 8 sites | Load 110%, bursty | 1.14 to 1.15 | 1.01 to 1.17 | 1.04 to 1.04 | 1.04 to 1.04 |
| 8 sites | Load 130%, steady, reports every 0.5 s | 1.00 to 1.00 | 0.67 to 3.69 | 1.00 to 1.00 | 0.99 to 1.03 |
| 8 sites | Load 130%, steady, 16 ingresses | 1.00 to 1.00 | 0.70 to 1.16 | 1.00 to 1.00 | 0.94 to 1.85 |
| New | Load 130% | 1.00 to 1.00 | 0.74 to 1.09 | 1.00 to 1.00 | 1.00 to 1.00 |
| New | Load 130%, staggered reports | 1.01 to 1.01 | 0.76 to 1.09 | 1.01 to 1.01 | 1.00 to 1.01 |
| New | Load 95%, largest ingress doubles for 50 s | 1.01 to 1.01 | 0.87 to 1.19 | 1.00 to 1.00 | 1.00 to 1.00 |

- Estimate = what the rule believes the total offered traffic is, each time it updates it. Truth = the frames really created in the W seconds before. Averaged over time, after the warm-up.

**Table B2. All ingresses of all runs: how far is the estimate from the truth?**

| Rule | Ingress × run values | Lowest | Median | Highest | Within 5% of the truth | Within 10% | More than 25% off |
|---|---|---|---|---|---|---|---|
| v6.1 (drop counter) | 370 | 0.98 | 1.00 | 1.15 | 95% | 95% | 0% |
| v6 (own share) | 370 | 0.66 | 1.00 | 3.93 | 28% | 58% | 13% |
| RR + adm. (drop counter) | 370 | 0.98 | 1.00 | 1.05 | 100% | 100% | 0% |
| RR + adm. (own share) | 370 | 0.77 | 1.00 | 4.34 | 96% | 98% | 1% |

**Table B3. Deadline success, % (rejected share, % in brackets). Mean of five seeds.**

| Network | Scenario | v6.1 (drop counter) | v6 (own share) | RR + adm. (drop counter) | RR + adm. (own share) |
|---|---|---|---|---|---|
| Beirut | Load 130%, shares 40/30/20/10% * | 63.9 (29.8) | 64.0 (29.8) | 61.9 (26.9) | 61.3 (27.0) |
| Beirut | Load 130%, equal shares | 64.2 (29.9) | 63.6 (30.0) | 61.2 (27.1) | 60.8 (27.1) |
| Beirut | Load 130%, staggered reports | 64.6 (30.6) | 64.1 (31.0) | 62.5 (28.6) | 62.4 (28.7) |
| Beirut | Load 130%, 30% of reports lost | 64.3 (30.0) | 64.0 (30.3) | 60.4 (26.6) | 61.9 (26.7) |
| Beirut | Load 130%, reports every 1 s | 64.7 (29.0) | 65.0 (29.1) | 61.4 (27.0) | 62.2 (27.0) |
| Beirut | Ingress A doubles for 50 s | 81.7 (12.9) | 80.9 (12.4) | 69.5 (6.6) | 69.8 (6.7) |
| 8 sites | Load 130%, steady | 65.7 (30.9) | 66.1 (31.0) | 63.5 (27.0) | 64.2 (27.0) |
| 8 sites | Load 130%, shifting | 65.5 (31.3) | 66.2 (30.9) | 64.9 (27.1) | 64.6 (27.1) |
| 8 sites | Load 110%, bursty | 62.8 (28.8) | 63.5 (27.6) | 58.8 (12.5) | 58.7 (12.5) |
| 8 sites | Load 130%, steady, reports every 0.5 s | 66.0 (31.1) | 64.4 (33.1) | 65.2 (26.9) | 64.9 (27.0) |
| 8 sites | Load 130%, steady, 16 ingresses | 64.6 (30.7) | 65.0 (30.3) | 63.7 (26.8) | 63.0 (26.8) |
| New | Load 130% | 62.4 (29.6) | 62.8 (30.2) | 59.7 (26.9) | 59.3 (26.9) |
| New | Load 130%, staggered reports | 62.2 (30.0) | 62.8 (30.3) | 59.6 (27.4) | 59.8 (27.3) |
| New | Load 95%, largest ingress doubles for 50 s | 75.3 (14.9) | 75.4 (15.0) | 66.7 (9.9) | 67.3 (9.9) |

**Table B4. Differences in success, points, paired by seed, with the 95% interval. Bold = the interval does not contain 0.**

| Network | Scenario | v6.1 − v6 | RR + adm.: drop counter − own share | v6.1 − RR + matched adm. |
|---|---|---|---|---|
| Beirut | Load 130%, shares 40/30/20/10% * | -0.1 ± 0.6 | +0.6 ± 1.4 | **+2.0 ± 1.5** |
| Beirut | Load 130%, equal shares | +0.5 ± 1.5 | +0.4 ± 1.2 | **+3.0 ± 2.1** |
| Beirut | Load 130%, staggered reports | +0.5 ± 0.6 | +0.1 ± 0.7 | **+2.1 ± 0.9** |
| Beirut | Load 130%, 30% of reports lost | +0.3 ± 1.6 | -1.5 ± 2.1 | **+3.9 ± 3.1** |
| Beirut | Load 130%, reports every 1 s | -0.3 ± 0.9 | -0.9 ± 2.2 | **+3.4 ± 1.2** |
| Beirut | Ingress A doubles for 50 s | +0.8 ± 1.6 | -0.3 ± 1.2 | **+12.1 ± 3.1** |
| 8 sites | Load 130%, steady | **-0.4 ± 0.3** | -0.7 ± 1.5 | **+2.2 ± 1.0** |
| 8 sites | Load 130%, shifting | **-0.7 ± 0.4** | +0.4 ± 0.9 | +0.6 ± 0.6 |
| 8 sites | Load 110%, bursty | -0.8 ± 1.6 | +0.0 ± 0.4 | **+4.0 ± 1.5** |
| 8 sites | Load 130%, steady, reports every 0.5 s | **+1.6 ± 0.8** | +0.3 ± 0.9 | +0.8 ± 1.0 |
| 8 sites | Load 130%, steady, 16 ingresses | -0.5 ± 0.5 | +0.7 ± 1.3 | +0.9 ± 0.9 |
| New | Load 130% | -0.5 ± 0.5 | +0.4 ± 1.5 | **+2.7 ± 1.8** |
| New | Load 130%, staggered reports | **-0.6 ± 0.4** | -0.2 ± 1.5 | **+2.6 ± 1.8** |
| New | Load 95%, largest ingress doubles for 50 s | -0.1 ± 1.1 | -0.6 ± 1.0 | **+8.6 ± 2.2** |

| Comparison | Clearly ahead | Clearly behind | No clear difference | Same runs | Mean difference over the 14 scenarios |
|---|---|---|---|---|---|
| v6.1 − v6 | 1 | 3 | 10 | 0 | -0.0 ± 0.1 |
| RR + adm.: drop counter − own share | 0 | 0 | 14 | 0 | -0.1 ± 0.3 |
| v6.1 − RR + matched adm. | 11 | 0 | 3 | 0 | +3.5 ± 0.5 |

**Table B5. Drop share of the ingresses: lowest ingress to highest ingress, % of the frames each was offered. Mean of five seeds.**

| Network | Scenario | v6.1 (drop counter) | v6 (own share) | RR + adm. (drop counter) | RR + adm. (own share) |
|---|---|---|---|---|---|
| Beirut | Load 130%, shares 40/30/20/10% * | 29.1 to 30.1 | 12.7 to 34.3 | 26.9 to 27.0 | 26.9 to 27.0 |
| Beirut | Load 130%, equal shares | 29.7 to 30.1 | 28.4 to 31.9 | 27.1 to 27.1 | 27.1 to 27.2 |
| Beirut | Load 130%, staggered reports | 30.2 to 30.8 | 21.8 to 34.4 | 28.6 to 28.7 | 28.5 to 28.8 |
| Beirut | Load 130%, 30% of reports lost | 28.3 to 31.0 | 13.9 to 41.2 | 26.1 to 27.3 | 18.4 to 30.0 |
| Beirut | Load 130%, reports every 1 s | 28.7 to 29.1 | 1.7 to 48.0 | 26.9 to 27.0 | 26.5 to 27.6 |
| Beirut | Ingress A doubles for 50 s | 9.9 to 15.6 | 2.1 to 22.0 | 5.7 to 7.5 | 5.7 to 7.6 |
| 8 sites | Load 130%, steady | 30.9 to 31.0 | 14.1 to 33.4 | 27.0 to 27.0 | 26.9 to 27.1 |
| 8 sites | Load 130%, shifting | 30.9 to 31.6 | 23.2 to 34.7 | 27.0 to 27.2 | 26.9 to 27.3 |
| 8 sites | Load 110%, bursty | 27.4 to 29.4 | 20.6 to 30.9 | 12.4 to 12.5 | 12.5 to 12.6 |
| 8 sites | Load 130%, steady, reports every 0.5 s | 31.1 to 31.2 | 0.1 to 76.1 | 26.9 to 27.0 | 26.2 to 28.5 |
| 8 sites | Load 130%, steady, 16 ingresses | 22.8 to 30.9 | 0.0 to 39.2 | 26.5 to 26.8 | 20.9 to 44.7 |
| New | Load 130% | 28.9 to 30.1 | 4.4 to 36.3 | 26.8 to 26.9 | 26.7 to 27.0 |
| New | Load 130%, staggered reports | 29.6 to 30.3 | 6.8 to 35.8 | 27.4 to 27.4 | 26.7 to 27.8 |
| New | Load 95%, largest ingress doubles for 50 s | 12.3 to 17.7 | 0.7 to 29.5 | 8.8 to 11.5 | 8.7 to 11.5 |

- Whole run. Inside 5-second windows the shares differ more (`spread_mean`, `spread_max` in `tables/B_measures.csv`).

**Table B6. Admitted traffic ÷ configured capacity, and telemetry bytes per second per ingress. Mean of five seeds.**

| Network | Scenario | Admitted: v6.1 (drop counter) | Admitted: v6 (own share) | Admitted: RR + adm. (drop counter) | Admitted: RR + adm. (own share) | Bytes: v6.1 | Bytes: v6 | v6.1 over v6 |
|---|---|---|---|---|---|---|---|---|
| Beirut | Load 130%, shares 40/30/20/10% * | 0.91 | 0.91 | 0.95 | 0.95 | 40.9 | 38.3 | +6.8% |
| Beirut | Load 130%, equal shares | 0.92 | 0.91 | 0.95 | 0.95 | 40.9 | 38.3 | +6.9% |
| Beirut | Load 130%, staggered reports | 0.90 | 0.90 | 0.93 | 0.93 | 40.9 | 38.3 | +6.8% |
| Beirut | Load 130%, 30% of reports lost | 0.91 | 0.91 | 0.96 | 0.95 | 40.8 | 38.3 | +6.7% |
| Beirut | Load 130%, reports every 1 s | 0.93 | 0.92 | 0.95 | 0.95 | 209.4 | 196.7 | +6.5% |
| Beirut | Ingress A doubles for 50 s | 0.85 | 0.85 | 0.91 | 0.91 | 40.1 | 38.3 | +4.9% |
| 8 sites | Load 130%, steady | 0.90 | 0.90 | 0.95 | 0.95 | 270.3 | 258.7 | +4.5% |
| 8 sites | Load 130%, shifting | 0.90 | 0.90 | 0.95 | 0.95 | 270.2 | 258.7 | +4.5% |
| 8 sites | Load 110%, bursty | 0.78 | 0.80 | 0.96 | 0.96 | 269.6 | 258.7 | +4.2% |
| 8 sites | Load 130%, steady, reports every 0.5 s | 0.90 | 0.87 | 0.95 | 0.95 | 1096.4 | 1050.7 | +4.3% |
| 8 sites | Load 130%, steady, 16 ingresses | 0.90 | 0.90 | 0.95 | 0.95 | 269.7 | 258.7 | +4.2% |
| New | Load 130% | 0.92 | 0.91 | 0.95 | 0.95 | 113.5 | 107.8 | +5.3% |
| New | Load 130%, staggered reports | 0.91 | 0.91 | 0.94 | 0.94 | 113.5 | 107.8 | +5.3% |
| New | Load 95%, largest ingress doubles for 50 s | 0.90 | 0.90 | 0.95 | 0.95 | 113.1 | 107.8 | +4.9% |

- The admission wrapper aims at 0.95 of the configured capacity. v6.1 and v6 plan no site above 0.95 of its measured capacity.
- Bytes: reports (62 + 4 bytes each, + 2 for the drop counter) and the drop counts sent by the ingresses (2 bytes each). The wrapper with the drop counter costs the same bytes as v6.1's reports.

## Reproduce

```
python3 feedback/batches/run_batches.py check
python3 feedback/batches/run_batches.py A --workers 2      # 770 runs
python3 feedback/batches/run_batches.py B --workers 2      # 280 runs
python3 feedback/batches/analyze_batches.py                # tables/*.csv and this file
python3 -m pytest feedback/batches/test_batches.py -q      # checks of the runner (pilot seed only)
```
