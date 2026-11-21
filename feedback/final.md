# Final evaluation: Batches A, B and D on seeds 301 to 320

- Ours v6.1 (frozen 15 Nov 2026) and ours v6.2 (v6.1 + one change, frozen 21 Nov 2026, `FREEZE_v6.2.md`).
- Seeds 301 to 310: evaluation seeds of the v6.1 freeze. Seeds 311 to 320: added after that freeze, never used before. Settings of v6.2 and of the tuned rival were chosen on pilot seeds 101 to 105 only.
- Written by `feedback/final/analyze_final.py` from `feedback/final/batch_{A,B,D}.csv`; checks in `feedback/final/check_final.py`.
- Deadline success = frames answered within the deadline ÷ all frames generated after the warm-up. Differences paired by seed; 95% interval, Student's t, 19 degrees of freedom. Nothing removed.

## Batch A: where does the gain come from? (22 scenarios, 10 rules, 20 seeds = 4,400 runs)

**Table 1. Deadline success, % (rejected share in brackets), mean of 20 seeds.** \* = pilot scenario (v6.1's settings were chosen on it, with other seeds).

| Network | Scenario | v6.2 | v6.1 | RR + adm. (tuned) | RR + adm. (frozen) | Round-robin |
|---|---|---|---|---|---|---|
| Beirut | Main scenario (load 85%) * | 96.0 (0.0) | 96.0 (0.0) | 96.0 (0.1) | 96.1 (0.0) | 96.1 (0.0) |
| Beirut | Load 95% * | 84.1 (5.3) | 84.2 (5.3) | 85.4 (5.4) | 77.0 (0.8) | 72.0 (0.0) |
| Beirut | Load 110% | 74.7 (17.3) | 74.7 (17.3) | 75.8 (18.1) | 71.9 (13.6) | 21.0 (0.0) |
| Beirut | Load 130% * | 64.0 (29.8) | 64.0 (29.8) | 64.5 (30.8) | 61.5 (26.9) | 4.5 (0.0) |
| Beirut | Load 150% | 56.1 (39.0) | 56.1 (39.0) | 56.1 (40.0) | 53.2 (36.7) | 1.7 (0.0) |
| Beirut | Burst: 85%, then 140% for 20 s * | 84.6 (9.6) | 82.9 (11.6) | 83.0 (7.3) | 74.4 (4.3) | 74.5 (0.0) |
| Beirut | Ingress A doubles for 50 s | 82.2 (11.7) | 81.6 (12.6) | 80.9 (10.9) | 68.6 (7.0) | 55.9 (0.0) |
| Beirut | Hamra loses 1 of 2 servers for 50 s * | 90.7 (1.7) | 90.9 (1.7) | 85.7 (0.1) | 85.8 (0.0) | 85.8 (0.0) |
| Beirut | DC loses 4 of 8 servers for 60 s | 73.2 (17.1) | 73.0 (17.9) | 70.9 (0.1) | 71.0 (0.0) | 71.0 (0.0) |
| Beirut | Wrong weights (DC has 6, rules told 8) * | 88.4 (0.3) | 88.1 (0.4) | 70.2 (0.0) | 70.2 (0.0) | 70.2 (0.0) |
| 8 sites | Load 90%, steady | 94.7 (0.4) | 94.7 (0.4) | 94.3 (1.7) | 94.8 (0.0) | 94.8 (0.0) |
| 8 sites | Load 110%, steady | 77.8 (17.9) | 77.8 (17.9) | 77.9 (18.0) | 75.9 (13.6) | 16.7 (0.0) |
| 8 sites | Load 130%, steady | 66.0 (30.9) | 66.0 (30.9) | 66.0 (30.7) | 64.5 (26.9) | 3.9 (0.0) |
| 8 sites | Load 90%, bursty | 76.3 (16.6) | 73.3 (19.6) | 72.9 (9.9) | 67.1 (3.6) | 68.6 (0.0) |
| 8 sites | Load 110%, bursty | 68.6 (22.1) | 63.0 (28.8) | 65.7 (16.0) | 59.1 (12.4) | 61.2 (0.0) |
| 8 sites | Load 130%, bursty | 57.9 (34.5) | 53.2 (40.1) | 55.7 (28.6) | 49.9 (25.4) | 12.2 (0.0) |
| New | Load 85% | 94.2 (0.0) | 94.2 (0.0) | 94.2 (0.1) | 94.1 (0.0) | 94.1 (0.0) |
| New | Load 95% | 84.0 (4.4) | 84.0 (4.4) | 84.6 (5.3) | 77.8 (0.7) | 74.6 (0.0) |
| New | Load 115% | 70.9 (21.0) | 70.9 (21.0) | 70.9 (21.6) | 67.4 (17.3) | 9.5 (0.0) |
| New | Load 130% | 63.1 (29.5) | 63.1 (29.5) | 63.3 (30.6) | 60.4 (26.8) | 3.5 (0.0) |
| New | Burst: 85%, then 140% for 20 s | 83.5 (9.4) | 82.5 (10.5) | 83.0 (7.8) | 74.8 (5.4) | 73.0 (0.0) |
| New | Regional DC loses 2 of 6 servers for 50 s | 87.9 (1.6) | 87.7 (1.8) | 75.6 (0.1) | 75.4 (0.0) | 75.4 (0.0) |

- RR + adm. (tuned) = round-robin + admission at 0.90 of capacity, no smoothing: settings chosen on pilot seeds, added after the v6.1 freeze. RR + adm. (frozen) = the primary rival of the v6.1 freeze (0.95, smoothing 0.3).

**Table 2. Differences in success, points, paired by seed, 95% interval. Bold = the interval excludes 0.**

| Network | Scenario | v6.2 − tuned | v6.1 − tuned | v6.2 − v6.1 |
|---|---|---|---|---|
| Beirut | Main scenario (load 85%) * | +0.0 ± 0.1 | +0.0 ± 0.1 | same runs |
| Beirut | Load 95% * | **-1.3 ± 0.8** | **-1.3 ± 0.7** | -0.1 ± 0.1 |
| Beirut | Load 110% | **-1.1 ± 0.5** | **-1.1 ± 0.5** | same runs |
| Beirut | Load 130% * | -0.5 ± 0.5 | -0.5 ± 0.5 | same runs |
| Beirut | Load 150% | +0.1 ± 0.4 | +0.1 ± 0.4 | same runs |
| Beirut | Burst: 85%, then 140% for 20 s * | **+1.6 ± 0.6** | -0.0 ± 0.6 | **+1.7 ± 0.1** |
| Beirut | Ingress A doubles for 50 s | **+1.4 ± 0.5** | **+0.7 ± 0.6** | **+0.7 ± 0.1** |
| Beirut | Hamra loses 1 of 2 servers for 50 s * | **+4.9 ± 0.6** | **+5.1 ± 0.6** | -0.2 ± 0.7 |
| Beirut | DC loses 4 of 8 servers for 60 s | **+2.3 ± 0.8** | **+2.1 ± 0.7** | +0.2 ± 1.0 |
| Beirut | Wrong weights (DC has 6, rules told 8) * | **+18.2 ± 3.7** | **+17.9 ± 3.6** | +0.3 ± 0.6 |
| 8 sites | Load 90%, steady | **+0.4 ± 0.2** | **+0.4 ± 0.2** | same runs |
| 8 sites | Load 110%, steady | -0.1 ± 0.3 | -0.1 ± 0.3 | same runs |
| 8 sites | Load 130%, steady | +0.0 ± 0.2 | +0.0 ± 0.2 | same runs |
| 8 sites | Load 90%, bursty | **+3.4 ± 0.5** | +0.4 ± 0.6 | **+3.0 ± 0.2** |
| 8 sites | Load 110%, bursty | **+3.0 ± 0.6** | **-2.7 ± 0.5** | **+5.6 ± 0.5** |
| 8 sites | Load 130%, bursty | **+2.3 ± 0.4** | **-2.5 ± 0.4** | **+4.7 ± 0.3** |
| New | Load 85% | -0.0 ± 0.1 | -0.0 ± 0.1 | same runs |
| New | Load 95% | **-0.6 ± 0.5** | **-0.6 ± 0.5** | same runs |
| New | Load 115% | -0.0 ± 0.3 | -0.0 ± 0.3 | same runs |
| New | Load 130% | -0.2 ± 0.3 | -0.2 ± 0.3 | same runs |
| New | Burst: 85%, then 140% for 20 s | **+0.5 ± 0.3** | **-0.5 ± 0.3** | **+1.0 ± 0.1** |
| New | Regional DC loses 2 of 6 servers for 50 s | **+12.3 ± 0.6** | **+12.1 ± 0.5** | +0.2 ± 0.6 |

**Table 3. Mean difference over groups of scenarios, points (mean over the scenarios inside each seed, then the interval over the 20 seeds), and the count of scenarios clearly ahead / behind / neither.** The kinds of scenario were defined after the first results.

| Scenarios | n | v6.2 − tuned | v6.1 − tuned | v6.2 − v6.1 | v6.1 − frozen rival | v6.2 − frozen rival |
|---|---|---|---|---|---|---|
| All 22 scenarios | 22 | +2.1 ± 0.2 (11/3/8) | +1.3 ± 0.2 (6/6/10) | +0.8 ± 0.1 (6/0/16) | +5.0 ± 0.3 (19/0/3) | +5.8 ± 0.3 (19/0/3) |
| Beirut | 10 | +2.6 ± 0.4 (5/2/3) | +2.3 ± 0.4 (4/2/4) | +0.3 ± 0.1 (2/0/8) | +6.2 ± 0.5 (9/0/1) | +6.4 ± 0.5 (9/0/1) |
| 8 sites | 6 | +1.5 ± 0.2 (4/0/2) | -0.7 ± 0.2 (1/2/3) | +2.2 ± 0.1 (3/0/3) | +2.8 ± 0.2 (5/0/1) | +5.0 ± 0.2 (5/0/1) |
| New | 6 | +2.0 ± 0.2 (2/1/3) | +1.8 ± 0.2 (1/2/3) | +0.2 ± 0.1 (1/0/5) | +5.4 ± 0.3 (5/0/1) | +5.6 ± 0.3 (5/0/1) |
| Capacity is not what was configured (failures, wrong weights) | 4 | +9.4 ± 1.0 (4/0/0) | +9.3 ± 1.0 (4/0/0) | +0.1 ± 0.4 (0/0/4) | +9.3 ± 1.0 (4/0/0) | +9.4 ± 1.0 (4/0/0) |
| Bursts and a surge | 6 | +2.0 ± 0.2 (6/0/0) | -0.8 ± 0.2 (1/3/2) | +2.8 ± 0.1 (6/0/0) | +7.1 ± 0.2 (6/0/0) | +9.9 ± 0.2 (6/0/0) |
| Steady load, 95% and above | 9 | -0.4 ± 0.2 (0/3/6) | -0.4 ± 0.2 (0/3/6) | -0.0 ± 0.0 (0/0/9) | +3.5 ± 0.4 (9/0/0) | +3.5 ± 0.4 (9/0/0) |
| Steady load below capacity (85% to 90%) | 3 | +0.1 ± 0.1 (1/0/2) | +0.1 ± 0.1 (1/0/2) | +0.0 ± 0.0 (0/0/3) | -0.1 ± 0.1 (0/0/3) | -0.1 ± 0.1 (0/0/3) |

**Table 4. What each part contributes (all 22 scenarios).**

| Comparison | Mean difference | Clearly ahead | Clearly behind | Neither | What it shows |
|---|---|---|---|---|---|
| v6.1 − v6.1 no penalty | +0.0 ± 0.1 | 3 | 3 | 16 | the backlog penalty |
| v6.1 − v6 | +0.1 ± 0.1 | 3 | 3 | 16 | the three changes of v6.1 (estimate, rise test, 90% threshold) |
| v6.1 no drop − Round-robin | +1.4 ± 0.2 | 11 | 3 | 8 | routing alone (neither rule drops) |
| v6.1 − Static + adm. | +5.1 ± 0.3 | 19 | 0 | 3 | against the static split (= the capacity split) |
| v6.1 − RR + adm. at 0.90 | +3.1 ± 0.2 | 10 | 9 | 3 | against RR + admission at 0.90, smoothed |
| v6.1 − Round-robin | +25.5 ± 0.4 | 19 | 0 | 3 | against plain round-robin (the floor) |

- Mean success over the 22 scenarios: v6.2 78.1%, v6.1 77.4%, v6.1 no penalty 77.3%, v6 77.2%, RR + adm. (tuned) 76.0%, RR + adm. at 0.90 74.2%, RR + adm. (frozen) 72.3%, Static + adm. 72.3%, v6.1 no drop 53.3%, Round-robin 51.8%.

**Where v6.2 is clearly behind the tuned rival (every case):** Beirut, Load 95% *: -1.3 ± 0.8; Beirut, Load 110%: -1.1 ± 0.5; New, Load 95%: -0.6 ± 0.5.

## Batch B: does the estimate hold when ingresses differ? (14 scenarios, 6 rules, 20 seeds = 1,680 runs)

**Table 5. Estimate of the offered traffic ÷ the truth, every ingress of every run.**

| Rule | Values | Lowest | Median | Highest | Within 5% | More than 25% off |
|---|---|---|---|---|---|---|
| v6.2 | 1480 | 0.95 | 1.00 | 1.04 | 100% | 0% |
| v6.1 | 1480 | 0.97 | 1.00 | 1.16 | 95% | 0% |
| v6 | 1480 | 0.64 | 1.00 | 5.63 | 29% | 14% |
| RR + adm. (tuned) | 1480 | 0.97 | 1.00 | 1.02 | 100% | 0% |
| RR + adm. (frozen) | 1480 | 0.97 | 1.00 | 1.05 | 100% | 0% |
| RR + adm. (own share) | 1480 | 0.77 | 1.00 | 4.34 | 96% | 0% |

- v6.1 and v6.2 use the drop counter; v6 and "RR + adm. (own share)" use each ingress's own drop share.

**Table 6. Per scenario: estimate ÷ truth (lowest to highest ingress), drop share of the ingresses (lowest to highest, %), and success, %. Mean of 20 seeds.**

| Network | Scenario | Estimate: v6.2 | Estimate: v6 | Drop share: v6.2 | Drop share: v6 | Success: v6.2 | Success: v6 | Success: tuned rival |
|---|---|---|---|---|---|---|---|---|
| Beirut | Load 130%, shares 40/30/20/10% * | 1.00–1.00 | 0.83–1.06 | 29.2–30.2 | 14.9–34.5 | 64.0 | 63.9 | 64.5 |
| Beirut | Load 130%, equal shares | 1.00–1.00 | 0.99–1.02 | 29.7–30.2 | 28.7–31.5 | 64.1 | 64.1 | 64.7 |
| Beirut | Load 130%, staggered reports | 1.00–1.00 | 0.90–1.08 | 29.1–30.2 | 20.1–34.9 | 64.1 | 64.0 | 64.2 |
| Beirut | Load 130%, 30% of reports lost | 0.99–1.01 | 0.85–1.23 | 28.2–31.4 | 15.5–42.2 | 63.4 | 64.0 | 64.5 |
| Beirut | Load 130%, reports every 1 s | 1.00–1.01 | 0.73–1.38 | 28.7–29.2 | 1.8–47.7 | 64.7 | 64.7 | 64.3 |
| Beirut | Ingress A doubles for 50 s | 1.00–1.01 | 0.94–1.11 | 8.7–14.3 | 4.3–21.5 | 82.2 | 80.4 | 80.9 |
| 8 sites | Load 130%, steady | 1.00–1.00 | 0.81–1.04 | 30.8–30.9 | 14.3–33.4 | 66.0 | 66.2 | 66.0 |
| 8 sites | Load 130%, shifting | 1.00–1.01 | 0.88–1.06 | 30.7–31.4 | 22.3–35.0 | 65.8 | 66.2 | 66.0 |
| 8 sites | Load 110%, bursty | 1.03–1.03 | 1.03–1.16 | 20.7–22.6 | 21.3–30.7 | 68.6 | 63.6 | 65.7 |
| 8 sites | Load 130%, steady, reports every 0.5 s | 1.00–1.01 | 0.66–4.06 | 31.0–31.2 | 0.1–77.9 | 66.2 | 64.0 | 66.3 |
| 8 sites | Load 130%, steady, 16 ingresses | 1.00–1.00 | 0.70–1.17 | 24.0–30.9 | 0.0–39.6 | 64.8 | 65.2 | 64.7 |
| New | Load 130% | 1.00–1.00 | 0.74–1.11 | 29.1–29.9 | 4.3–36.9 | 63.1 | 63.3 | 63.3 |
| New | Load 130%, staggered reports | 1.00–1.00 | 0.77–1.09 | 28.7–29.5 | 7.1–35.9 | 63.3 | 63.3 | 63.2 |
| New | Load 95%, largest ingress doubles for 50 s | 1.00–1.01 | 0.88–1.19 | 12.4–17.9 | 2.0–29.3 | 75.3 | 75.5 | 75.2 |

| Success difference (14 scenarios) | Mean | Clearly ahead | Clearly behind | Neither |
|---|---|---|---|---|
| v6.2 − v6.1 | +0.4 ± 0.1 | 2 | 0 | 12 |
| v6.1 − v6 | +0.1 ± 0.1 | 2 | 3 | 9 |
| v6.2 − RR + adm. (tuned) | +0.2 ± 0.1 | 2 | 2 | 10 |
| RR + adm. (frozen) − RR + adm. (own share) | -0.1 ± 0.1 | 0 | 3 | 11 |

## Batch D: outside the design range (12 scenarios, 5 rules, 20 seeds = 1,200 runs)

- Fast on/off traffic: every 4 s, 2 s at 1.5 × and 2 s at 0.5 × the mean rate. Deadline 200 ms instead of 300 ms. Each at loads 95% and 115%, on the three networks. Fixed before any run (`catsim/final.py`).

**Table 7. Success, % (rejected, %), mean of 20 seeds; differences in points, paired by seed.**

| Network | Scenario | v6.2 | v6.1 | RR + adm. (tuned) | RR + adm. (frozen) | Round-robin | v6.2 − tuned | v6.1 − tuned | v6.2 − v6.1 |
|---|---|---|---|---|---|---|---|---|---|
| Beirut | Fast on/off, load 95% | 50.0 (33.8) | 50.7 (34.2) | 30.6 (6.3) | 23.9 (1.1) | 21.6 (0.0) | **+19.4 ± 0.9** | **+20.1 ± 0.7** | **-0.7 ± 0.5** |
| 8 sites | Fast on/off, load 95% | 44.1 (32.5) | 52.0 (36.0) | 33.2 (10.5) | 38.4 (2.2) | 39.5 (0.0) | **+10.9 ± 0.3** | **+18.8 ± 0.3** | **-7.9 ± 0.3** |
| New | Fast on/off, load 95% | 41.0 (32.2) | 44.3 (35.0) | 34.6 (8.7) | 23.8 (1.6) | 20.9 (0.0) | **+6.4 ± 1.5** | **+9.7 ± 0.9** | **-3.3 ± 0.9** |
| Beirut | Fast on/off, load 115% | 35.6 (46.9) | 35.9 (47.3) | 22.1 (21.0) | 18.0 (17.4) | 0.0 (0.0) | **+13.5 ± 0.7** | **+13.9 ± 0.7** | -0.4 ± 0.5 |
| 8 sites | Fast on/off, load 115% | 33.4 (40.6) | 42.3 (45.9) | 23.3 (13.7) | 29.7 (13.9) | 31.6 (0.0) | **+10.1 ± 0.4** | **+19.0 ± 0.3** | **-8.9 ± 0.3** |
| New | Fast on/off, load 115% | 28.3 (43.2) | 29.1 (43.3) | 21.9 (20.6) | 16.4 (17.1) | 0.0 (0.0) | **+6.4 ± 0.7** | **+7.2 ± 0.7** | **-0.8 ± 0.3** |
| Beirut | Deadline 200 ms, load 95% | 65.1 (12.1) | 65.1 (12.1) | 59.6 (5.4) | 46.5 (0.8) | 42.4 (0.0) | **+5.5 ± 0.9** | **+5.5 ± 0.9** | same runs |
| 8 sites | Deadline 200 ms, load 95% | 68.2 (7.4) | 68.2 (7.4) | 68.1 (5.4) | 62.1 (0.7) | 60.3 (0.0) | +0.2 ± 0.2 | +0.2 ± 0.2 | same runs |
| New | Deadline 200 ms, load 95% | 50.6 (30.7) | 51.1 (30.4) | 52.5 (5.3) | 42.5 (0.7) | 39.5 (0.0) | **-1.9 ± 1.6** | **-1.4 ± 1.2** | -0.5 ± 0.7 |
| Beirut | Deadline 200 ms, load 115% | 54.8 (27.0) | 54.8 (27.0) | 50.5 (21.7) | 36.4 (17.3) | 0.0 (0.0) | **+4.3 ± 0.5** | **+4.3 ± 0.5** | same runs |
| 8 sites | Deadline 200 ms, load 115% | 57.3 (23.5) | 57.3 (23.5) | 57.1 (21.7) | 51.0 (17.4) | 9.8 (0.0) | +0.3 ± 0.3 | +0.3 ± 0.3 | same runs |
| New | Deadline 200 ms, load 115% | 43.1 (42.2) | 43.0 (42.3) | 44.4 (21.6) | 34.3 (17.3) | 0.0 (0.0) | **-1.3 ± 1.0** | **-1.4 ± 1.0** | +0.1 ± 0.2 |

| Scenarios | v6.2 − tuned | v6.1 − tuned | v6.2 − v6.1 | v6.2 − frozen rival |
|---|---|---|---|---|
| Fast on/off (6) | +11.1 ± 0.4 (6/0/0) | +14.8 ± 0.3 (6/0/0) | -3.7 ± 0.3 (0/5/1) | +13.7 ± 0.4 (6/0/0) |
| Deadline 200 ms (6) | +1.2 ± 0.5 (2/2/2) | +1.2 ± 0.5 (2/2/2) | -0.1 ± 0.1 (0/0/6) | +11.1 ± 1.0 (6/0/0) |
| All 12 | +6.1 ± 0.3 (8/2/2) | +8.0 ± 0.3 (8/2/2) | -1.9 ± 0.1 (0/5/7) | +12.4 ± 0.6 (12/0/0) |

- In brackets: scenarios clearly ahead / clearly behind / neither.

## Recovery after an event (the 20 s after it ends, 20 seeds)

**Table 8. Success % / rejected %, all frames generated in the 20 s after the event ends.**

| Network | Event | v6.2 | v6.1 | Tuned rival |
|---|---|---|---|---|
| Beirut | Burst: 85%, then 140% for 20 s (ends at 80.5 s) | 91.9 / 5.5 | 80.7 / 18.1 | 90.0 / 7.7 |
| New | Burst: 85%, then 140% for 20 s (ends at 80.5 s) | 90.6 / 4.8 | 83.5 / 13.2 | 90.8 / 4.8 |
| Beirut | Ingress A doubles for 50 s (ends at 100 s) | 92.1 / 4.4 | 87.4 / 10.8 | 90.3 / 6.3 |
| Beirut | Hamra loses 1 of 2 servers for 50 s (ends at 100 s) | 88.8 / 2.6 | 90.3 / 2.1 | 82.1 / 0.1 |
| Beirut | DC loses 4 of 8 servers for 60 s (ends at 110 s) | 73.5 / 21.1 | 72.7 / 21.6 | 94.7 / 0.1 |
| New | Regional DC loses 2 of 6 servers for 50 s (ends at 100 s) | 87.9 / 1.9 | 87.3 / 2.1 | 69.7 / 0.1 |

- v6.2's change targets the first three rows (the estimate after a burst). The DC row is the capacity meter's slow return, which v6.2 does not change (a known limit).

## Telemetry and denominators

**Table 9. Telemetry received, bytes per second per ingress (mean over the Batch A scenarios and seeds).**

| Rule | Beirut | 8 sites | New |
|---|---|---|---|
| v6.2 | 40.2 | 269.1 | 112.3 |
| v6.1 | 40.2 | 269.3 | 112.3 |
| v6 | 38.3 | 258.7 | 107.8 |
| RR + adm. (tuned) | 40.1 | 269.3 | 112.3 |
| RR + adm. (frozen) | 40.0 | 269.0 | 112.1 |
| Round-robin | 0.0 | 0.0 | 0.0 |

- Round-robin uses no telemetry. v6.1, v6.2 and both admission rivals receive the same reports and drop counter, so the same bytes.

**Denominators.** Each run counts every frame generated after the warm-up: Beirut 18,261 frames per run on average (13,075 to 27,536); 8 sites 28,157 frames per run on average (22,767 to 33,738); New 31,360 frames per run on average (26,128 to 40,875). Every rule sees exactly the same frames in a given scenario and seed. In total: 107.9 million frames simulated in Batch A (all rules and seeds); 7,280 runs over the three batches.

- Caution: the main tables hold about 114 intervals at 95%; about 6 would exclude 0 by chance alone. No correction for multiple comparisons is applied.

## Figures (`feedback/final/figures/`, PDF and PNG)

- `fig_forest_A`: v6.2 and v6.1 against the tuned rival, every Batch A scenario.
- `fig_forest_D`: the same for Batch D.
- `fig_recovery`: success second by second around a burst and around a server's return.
- `fig_estimate`: estimate ÷ truth for every ingress and run, v6, v6.1, v6.2.
