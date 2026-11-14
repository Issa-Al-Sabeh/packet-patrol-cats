### Main comparison: all (48 grid scenarios x 10 seeds)

| Algorithm | Deadline success (%) | Oracle gap (pp) | Gap to oracle + wrapper (pp) | p99 latency (ms) | Drop rate (%) | Expired (%) | Late (%) | Telemetry B/s per ingress |
|---|---|---|---|---|---|---|---|---|
| K Staleness-Aware CATS (ours v6) | 79.4 | -13.7 | -0.7 | 380 | 15.8 | 0.5 | 4.3 | 259 |
| L+ Fresh-state oracle + common wrapper (reference) | 78.7 | -13.0 | +0.0 | 407 | 10.2 | 2.9 | 8.2 | 259 |
| J Expected delay + drop | 74.3 | -8.6 | +4.4 | 419 | 10.9 | 0.8 | 14.0 | 259 |
| L Fresh-state oracle | 65.8 | +0.0 | +13.0 | 445 | 0.0 | 9.7 | 24.5 | 0 |
| I CATS-draft load sharing | 60.8 | +5.0 | +18.0 | 467 | 0.0 | 12.1 | 27.1 | 243 |
| E Dahlin (Basic LI) | 56.8 | +8.9 | +21.9 | 471 | 0.0 | 10.2 | 32.9 | 259 |
| B Capacity WRR | 55.2 | +10.5 | +23.5 | 456 | 0.0 | 9.4 | 35.4 | 0 |
| C Dynamic WRR (measured speeds) | 55.2 | +10.5 | +23.5 | 456 | 0.0 | 9.4 | 35.4 | 259 |
| F LSQ (shared periodic reports) | 55.1 | +10.6 | +23.6 | 470 | 0.0 | 10.6 | 34.3 | 243 |
| F2 LSQ-Sample (own random samples, supplementary) | 42.9 | +22.8 | +35.8 | 512 | 0.0 | 28.2 | 28.8 | 264 |
| H Liyanage et al. 2026 | 42.7 | +23.1 | +36.0 | 514 | 0.0 | 26.8 | 30.5 | 264 |
| D Weighted power-of-two | 40.6 | +25.2 | +38.2 | 516 | 0.0 | 23.9 | 35.5 | 243 |
| G Prequal (HCL) | 40.4 | +25.4 | +38.4 | 512 | 0.0 | 31.5 | 28.1 | 264 |
| A Nearest site | 5.4 | +60.3 | +73.3 | 532 | 0.0 | 73.5 | 21.0 | 0 |

### Main comparison: below capacity (60%, 90%) (24 grid scenarios x 10 seeds)

| Algorithm | Deadline success (%) | Oracle gap (pp) | Gap to oracle + wrapper (pp) | p99 latency (ms) | Drop rate (%) | Expired (%) | Late (%) | Telemetry B/s per ingress |
|---|---|---|---|---|---|---|---|---|
| B Capacity WRR | 91.4 | -0.8 | -1.1 | 377 | 0.0 | 1.7 | 6.9 | 0 |
| C Dynamic WRR (measured speeds) | 91.4 | -0.8 | -1.1 | 377 | 0.0 | 1.7 | 6.9 | 259 |
| K Staleness-Aware CATS (ours v6) | 91.3 | -0.7 | -1.0 | 365 | 4.4 | 0.3 | 3.9 | 259 |
| J Expected delay + drop | 91.1 | -0.5 | -0.8 | 380 | 2.6 | 0.4 | 5.9 | 259 |
| L Fresh-state oracle | 90.6 | +0.0 | -0.3 | 391 | 0.0 | 2.3 | 7.2 | 0 |
| L+ Fresh-state oracle + common wrapper (reference) | 90.3 | +0.3 | +0.0 | 391 | 0.6 | 2.1 | 7.1 | 259 |
| I CATS-draft load sharing | 86.5 | +4.1 | +3.8 | 409 | 0.0 | 2.9 | 10.6 | 243 |
| E Dahlin (Basic LI) | 85.8 | +4.8 | +4.5 | 416 | 0.0 | 2.5 | 11.7 | 259 |
| F LSQ (shared periodic reports) | 85.4 | +5.2 | +4.9 | 409 | 0.0 | 2.7 | 11.8 | 243 |
| H Liyanage et al. 2026 | 59.4 | +31.1 | +30.9 | 493 | 0.0 | 15.1 | 25.4 | 264 |
| D Weighted power-of-two | 58.7 | +31.9 | +31.6 | 495 | 0.0 | 13.0 | 28.3 | 243 |
| F2 LSQ-Sample (own random samples, supplementary) | 55.9 | +34.7 | +34.4 | 497 | 0.0 | 18.4 | 25.7 | 264 |
| G Prequal (HCL) | 52.2 | +38.4 | +38.1 | 498 | 0.0 | 22.2 | 25.6 | 264 |
| A Nearest site | 8.3 | +82.3 | +82.0 | 528 | 0.0 | 67.9 | 23.7 | 0 |

### Main comparison: overload (110%, 130%) (24 grid scenarios x 10 seeds)

| Algorithm | Deadline success (%) | Oracle gap (pp) | Gap to oracle + wrapper (pp) | p99 latency (ms) | Drop rate (%) | Expired (%) | Late (%) | Telemetry B/s per ingress |
|---|---|---|---|---|---|---|---|---|
| K Staleness-Aware CATS (ours v6) | 67.5 | -26.6 | -0.4 | 396 | 27.2 | 0.6 | 4.6 | 259 |
| L+ Fresh-state oracle + common wrapper (reference) | 67.2 | -26.3 | +0.0 | 423 | 19.8 | 3.7 | 9.4 | 259 |
| J Expected delay + drop | 57.6 | -16.7 | +9.6 | 459 | 19.1 | 1.2 | 22.1 | 259 |
| L Fresh-state oracle | 40.9 | +0.0 | +26.3 | 499 | 0.0 | 17.2 | 41.9 | 0 |
| I CATS-draft load sharing | 35.0 | +5.9 | +32.1 | 525 | 0.0 | 21.3 | 43.6 | 243 |
| F2 LSQ-Sample (own random samples, supplementary) | 29.9 | +11.0 | +37.2 | 526 | 0.0 | 38.1 | 32.0 | 264 |
| G Prequal (HCL) | 28.5 | +12.4 | +38.6 | 526 | 0.0 | 40.9 | 30.6 | 264 |
| E Dahlin (Basic LI) | 27.9 | +13.0 | +39.2 | 527 | 0.0 | 18.0 | 54.1 | 259 |
| H Liyanage et al. 2026 | 25.9 | +15.0 | +41.2 | 535 | 0.0 | 38.5 | 35.5 | 264 |
| F LSQ (shared periodic reports) | 24.8 | +16.1 | +42.4 | 531 | 0.0 | 18.5 | 56.8 | 243 |
| D Weighted power-of-two | 22.4 | +18.5 | +44.7 | 537 | 0.0 | 34.9 | 42.7 | 243 |
| B Capacity WRR | 19.1 | +21.8 | +48.1 | 535 | 0.0 | 17.1 | 63.8 | 0 |
| C Dynamic WRR (measured speeds) | 19.1 | +21.8 | +48.1 | 535 | 0.0 | 17.1 | 63.8 | 259 |
| A Nearest site | 2.6 | +38.3 | +64.6 | 537 | 0.0 | 79.1 | 18.3 | 0 |

### v6 against each rival, scenario by scenario (paired 95% CI over seeds)

| Rival | Regime | v6 − rival (pp, mean) | v6 better | same | v6 worse | scenarios |
|---|---|---|---|---|---|---|
| A Nearest site | below | +83.0 | 24 | 0 | 0 | 24 |
| A Nearest site | overload | +64.9 | 24 | 0 | 0 | 24 |
| B Capacity WRR | below | -0.1 | 8 | 8 | 8 | 24 |
| B Capacity WRR | overload | +48.4 | 24 | 0 | 0 | 24 |
| C Dynamic WRR (measured speeds) | below | -0.1 | 8 | 8 | 8 | 24 |
| C Dynamic WRR (measured speeds) | overload | +48.4 | 24 | 0 | 0 | 24 |
| D Weighted power-of-two | below | +32.6 | 24 | 0 | 0 | 24 |
| D Weighted power-of-two | overload | +45.1 | 24 | 0 | 0 | 24 |
| E Dahlin (Basic LI) | below | +5.5 | 20 | 4 | 0 | 24 |
| E Dahlin (Basic LI) | overload | +39.6 | 24 | 0 | 0 | 24 |
| F LSQ (shared periodic reports) | below | +5.9 | 20 | 1 | 3 | 24 |
| F LSQ (shared periodic reports) | overload | +42.8 | 24 | 0 | 0 | 24 |
| G Prequal (HCL) | below | +39.1 | 24 | 0 | 0 | 24 |
| G Prequal (HCL) | overload | +39.0 | 24 | 0 | 0 | 24 |
| H Liyanage et al. 2026 | below | +31.9 | 24 | 0 | 0 | 24 |
| H Liyanage et al. 2026 | overload | +41.6 | 24 | 0 | 0 | 24 |
| I CATS-draft load sharing | below | +4.8 | 20 | 4 | 0 | 24 |
| I CATS-draft load sharing | overload | +32.5 | 24 | 0 | 0 | 24 |
| J Expected delay + drop | below | +0.2 | 14 | 1 | 9 | 24 |
| J Expected delay + drop | overload | +10.0 | 19 | 0 | 5 | 24 |
| L Fresh-state oracle | below | +0.7 | 18 | 2 | 4 | 24 |
| L Fresh-state oracle | overload | +26.6 | 20 | 0 | 4 | 24 |
| F2 LSQ-Sample (own random samples, supplementary) | below | +35.4 | 24 | 0 | 0 | 24 |
| F2 LSQ-Sample (own random samples, supplementary) | overload | +37.6 | 24 | 0 | 0 | 24 |

### Telemetry delay: deadline success (%) at 0 / 50 / 200 / 1000 ms (steady)

| Load | Algorithm | 0 ms | 50 ms | 200 ms | 1000 ms | 1000 − 0 ms (pp) |
|---|---|---|---|---|---|---|
| 60% | Nearest | 11.7 | 11.7 | 11.7 | 11.7 | +0.0 |
| 60% | WRR | 98.9 | 98.9 | 98.9 | 98.9 | +0.0 |
| 60% | DWRR | 98.9 | 98.9 | 98.9 | 98.9 | +0.0 |
| 60% | W-Po2 | 78.1 | 78.6 | 78.3 | 78.0 | -0.1 |
| 60% | Dahlin LI | 97.8 | 97.8 | 97.8 | 97.8 | +0.0 |
| 60% | LSQ | 98.4 | 98.4 | 98.4 | 98.4 | -0.1 |
| 60% | Prequal | 62.7 | 62.7 | 62.7 | 62.7 | +0.0 |
| 60% | Liyanage | 81.9 | 81.9 | 81.9 | 81.9 | +0.0 |
| 60% | CATS-LB | 98.5 | 98.5 | 98.5 | 98.4 | -0.0 |
| 60% | ED+drop | 98.2 | 98.4 | 98.5 | 99.1 | +0.9 |
| 60% | SA-CATS (v6) | 99.0 | 99.0 | 99.1 | 99.1 | +0.0 |
| 60% | Oracle | 96.5 | 96.5 | 96.5 | 96.5 | +0.0 |
| 90% | Nearest | 7.6 | 7.6 | 7.6 | 7.6 | +0.0 |
| 90% | WRR | 95.1 | 95.1 | 95.1 | 95.1 | +0.0 |
| 90% | DWRR | 95.1 | 95.1 | 95.1 | 95.1 | +0.0 |
| 90% | W-Po2 | 40.7 | 40.0 | 41.2 | 40.6 | -0.1 |
| 90% | Dahlin LI | 82.7 | 82.5 | 82.2 | 81.9 | -0.8 |
| 90% | LSQ | 88.8 | 88.5 | 87.8 | 54.0 | -34.8 |
| 90% | Prequal | 39.4 | 39.4 | 39.4 | 39.4 | +0.0 |
| 90% | Liyanage | 45.4 | 45.4 | 45.4 | 45.4 | +0.0 |
| 90% | CATS-LB | 85.5 | 84.3 | 84.2 | 82.4 | -3.1 |
| 90% | ED+drop | 92.3 | 92.7 | 92.0 | 94.6 | +2.3 |
| 90% | SA-CATS (v6) | 95.0 | 94.9 | 95.0 | 95.0 | -0.0 |
| 90% | Oracle | 93.0 | 93.0 | 93.0 | 93.0 | +0.0 |
| 110% | Nearest | 3.7 | 3.7 | 3.7 | 3.7 | +0.0 |
| 110% | WRR | 16.8 | 16.8 | 16.8 | 16.8 | +0.0 |
| 110% | DWRR | 16.8 | 16.8 | 16.8 | 16.8 | +0.0 |
| 110% | W-Po2 | 25.7 | 25.4 | 25.0 | 26.0 | +0.3 |
| 110% | Dahlin LI | 33.5 | 33.7 | 33.5 | 33.8 | +0.3 |
| 110% | LSQ | 28.7 | 30.2 | 31.4 | 38.8 | +10.1 |
| 110% | Prequal | 30.8 | 30.8 | 30.8 | 30.8 | +0.0 |
| 110% | Liyanage | 30.3 | 30.3 | 30.3 | 30.3 | +0.0 |
| 110% | CATS-LB | 40.1 | 40.3 | 40.1 | 38.6 | -1.5 |
| 110% | ED+drop | 56.4 | 56.5 | 56.2 | 75.8 | +19.4 |
| 110% | SA-CATS (v6) | 78.2 | 78.2 | 78.1 | 78.0 | -0.2 |
| 110% | Oracle | 45.0 | 45.0 | 45.0 | 45.0 | +0.0 |
| 130% | Nearest | 1.7 | 1.7 | 1.7 | 1.7 | +0.0 |
| 130% | WRR | 3.9 | 3.9 | 3.9 | 3.9 | +0.0 |
| 130% | DWRR | 3.9 | 3.9 | 3.9 | 3.9 | +0.0 |
| 130% | W-Po2 | 17.1 | 17.4 | 17.4 | 17.2 | +0.1 |
| 130% | Dahlin LI | 11.8 | 11.9 | 12.0 | 11.8 | +0.0 |
| 130% | LSQ | 5.3 | 5.2 | 5.4 | 6.0 | +0.6 |
| 130% | Prequal | 24.9 | 24.9 | 24.9 | 24.9 | +0.0 |
| 130% | Liyanage | 17.7 | 17.7 | 17.7 | 17.7 | +0.0 |
| 130% | CATS-LB | 25.4 | 24.0 | 24.1 | 24.8 | -0.6 |
| 130% | ED+drop | 40.1 | 40.2 | 40.3 | 61.4 | +21.3 |
| 130% | SA-CATS (v6) | 66.2 | 66.0 | 65.9 | 66.1 | -0.1 |
| 130% | Oracle | 25.7 | 25.7 | 25.7 | 25.7 | +0.0 |

### Traffic patterns: deadline success (%) (50 ms telemetry delay)

| Load | Algorithm | Steady | Bursty | Shifting | Recovery after a burst (s) |
|---|---|---|---|---|---|
| 60% | Nearest | 11.7 | 11.2 | 9.1 | 0.0 |
| 60% | WRR | 98.9 | 91.8 | 98.9 | 0.1 |
| 60% | DWRR | 98.9 | 91.8 | 98.9 | 0.1 |
| 60% | W-Po2 | 78.6 | 73.0 | 78.4 | 0.7 |
| 60% | Dahlin LI | 97.8 | 87.7 | 97.6 | 0.2 |
| 60% | LSQ | 98.4 | 89.6 | 98.5 | 0.1 |
| 60% | Prequal | 62.7 | 61.9 | 65.4 | 1.7 |
| 60% | Liyanage | 81.9 | 74.8 | 72.6 | 3.5 |
| 60% | CATS-LB | 98.5 | 88.8 | 98.4 | 0.4 |
| 60% | ED+drop | 98.4 | 90.9 | 98.0 | 0.0 |
| 60% | SA-CATS (v6) | 99.0 | 87.8 | 98.9 | 2.0 |
| 60% | Oracle | 96.5 | 92.4 | 96.4 | 0.0 |
| 90% | Nearest | 7.6 | 6.9 | 3.3 | 0.0 |
| 90% | WRR | 95.1 | 68.5 | 95.1 | 1.0 |
| 90% | DWRR | 95.1 | 68.5 | 95.1 | 1.0 |
| 90% | W-Po2 | 40.0 | 41.7 | 40.5 | 0.8 |
| 90% | Dahlin LI | 82.5 | 66.8 | 82.6 | 1.0 |
| 90% | LSQ | 88.5 | 67.9 | 89.0 | 1.0 |
| 90% | Prequal | 39.4 | 40.5 | 43.3 | 1.0 |
| 90% | Liyanage | 45.4 | 41.8 | 40.2 | 3.9 |
| 90% | CATS-LB | 84.3 | 65.5 | 84.6 | 6.1 |
| 90% | ED+drop | 92.7 | 77.0 | 88.5 | 0.4 |
| 90% | SA-CATS (v6) | 94.9 | 73.2 | 94.9 | 7.5 |
| 90% | Oracle | 93.0 | 72.1 | 93.1 | 0.6 |
| 110% | Nearest | 3.7 | 4.9 | 1.7 | 0.0 |
| 110% | WRR | 16.8 | 61.5 | 17.1 | 2.6 |
| 110% | DWRR | 16.8 | 61.5 | 17.1 | 2.6 |
| 110% | W-Po2 | 25.4 | 28.1 | 26.5 | 0.6 |
| 110% | Dahlin LI | 33.7 | 53.1 | 33.6 | 2.2 |
| 110% | LSQ | 30.2 | 55.3 | 31.2 | 3.0 |
| 110% | Prequal | 30.8 | 31.1 | 33.1 | 1.4 |
| 110% | Liyanage | 30.3 | 33.1 | 31.0 | 1.6 |
| 110% | CATS-LB | 40.3 | 52.5 | 39.8 | 3.7 |
| 110% | ED+drop | 56.5 | 68.0 | 65.2 | 0.8 |
| 110% | SA-CATS (v6) | 78.2 | 63.6 | 78.0 | 12.5 |
| 110% | Oracle | 45.0 | 67.4 | 45.9 | 1.0 |
| 130% | Nearest | 1.7 | 2.7 | 0.7 | 0.0 |
| 130% | WRR | 3.9 | 11.2 | 4.0 | 1.8 |
| 130% | DWRR | 3.9 | 11.2 | 4.0 | 1.8 |
| 130% | W-Po2 | 17.4 | 19.3 | 17.8 | 0.4 |
| 130% | Dahlin LI | 11.9 | 23.4 | 12.0 | 2.2 |
| 130% | LSQ | 5.2 | 19.5 | 5.5 | 4.3 |
| 130% | Prequal | 24.9 | 24.8 | 26.6 | 0.6 |
| 130% | Liyanage | 17.7 | 22.6 | 20.9 | 1.8 |
| 130% | CATS-LB | 24.0 | 28.8 | 24.1 | 2.4 |
| 130% | ED+drop | 40.2 | 45.3 | 47.5 | 2.4 |
| 130% | SA-CATS (v6) | 66.0 | 54.1 | 66.0 | 10.5 |
| 130% | Oracle | 25.7 | 35.6 | 25.9 | 1.8 |

### Telemetry budget: deadline success (%) and realized bytes/s per ingress

| Load | Algorithm | Budget | Success (%) | ± 95% CI | B/s per ingress | Mean info age (s) |
|---|---|---|---|---|---|---|
| 60% | CATS-LB | medium (2 s) | 98.5 | 0.1 | 243 | 1.07 |
| 60% | Dahlin LI | medium (2 s) | 97.8 | 0.2 | 259 | 1.07 |
| 60% | ED+drop | medium (2 s) | 98.4 | 0.2 | 259 | 1.06 |
| 60% | Liyanage | medium (2 s) | 81.9 | 7.4 | 264 | 3.35 |
| 60% | LSQ | medium (2 s) | 98.4 | 0.1 | 243 | 1.05 |
| 60% | LSQ-Sample | medium (2 s) | 68.0 | 0.8 | 264 | 0.81 |
| 60% | Nearest | medium (2 s) | 11.7 | 0.1 | 0 | – |
| 60% | Oracle | medium (2 s) | 96.5 | 0.1 | 0 | – |
| 60% | SA-CATS (v6) | medium (2 s) | 99.0 | 0.0 | 259 | 1.07 |
| 60% | Prequal | medium (2 s) | 62.7 | 1.4 | 264 | 0.96 |
| 60% | W-Po2 | medium (2 s) | 78.6 | 1.4 | 243 | 1.07 |
| 60% | WRR | medium (2 s) | 98.9 | 0.0 | 0 | – |
| 60% | DWRR | medium (2 s) | 98.9 | 0.0 | 259 | 1.07 |
| 90% | CATS-LB | low (10 s) | 71.0 | 4.0 | 45 | 5.08 |
| 90% | CATS-LB | medium (2 s) | 84.3 | 2.7 | 243 | 1.07 |
| 90% | CATS-LB | threshold (0.5 s checks) | 85.2 | 2.1 | 317 | 1.02 |
| 90% | CATS-LB | high (0.5 s) | 88.1 | 1.7 | 987 | 0.32 |
| 90% | Dahlin LI | low (10 s) | 82.4 | 1.2 | 48 | 5.08 |
| 90% | Dahlin LI | medium (2 s) | 82.5 | 1.2 | 259 | 1.07 |
| 90% | Dahlin LI | threshold (0.5 s checks) | 81.6 | 1.3 | 429 | 0.93 |
| 90% | Dahlin LI | high (0.5 s) | 85.3 | 1.2 | 1051 | 0.32 |
| 90% | ED+drop | low (10 s) | 86.1 | 2.1 | 48 | 5.03 |
| 90% | ED+drop | medium (2 s) | 92.7 | 0.6 | 259 | 1.06 |
| 90% | ED+drop | threshold (0.5 s checks) | 92.4 | 1.0 | 360 | 0.99 |
| 90% | ED+drop | high (0.5 s) | 94.2 | 0.5 | 1051 | 0.31 |
| 90% | Liyanage | low (10 s) | 30.1 | 6.1 | 53 | 14.54 |
| 90% | Liyanage | medium (2 s) | 45.4 | 5.9 | 264 | 3.45 |
| 90% | Liyanage | high (0.5 s) | 34.1 | 5.8 | 1056 | 0.86 |
| 90% | LSQ | low (10 s) | 93.9 | 1.1 | 45 | 5.07 |
| 90% | LSQ | medium (2 s) | 88.5 | 2.1 | 243 | 1.06 |
| 90% | LSQ | threshold (0.5 s checks) | 49.1 | 1.3 | 874 | 0.34 |
| 90% | LSQ | high (0.5 s) | 49.0 | 0.8 | 987 | 0.31 |
| 90% | LSQ-Sample | low (10 s) | 30.2 | 1.5 | 53 | 3.79 |
| 90% | LSQ-Sample | medium (2 s) | 42.8 | 1.1 | 264 | 0.83 |
| 90% | LSQ-Sample | high (0.5 s) | 62.6 | 1.0 | 1056 | 0.28 |
| 90% | Nearest | high (0.5 s) | 7.6 | 0.3 | 0 | – |
| 90% | Nearest | low (10 s) | 7.6 | 0.3 | 0 | – |
| 90% | Nearest | medium (2 s) | 7.6 | 0.3 | 0 | – |
| 90% | Oracle | high (0.5 s) | 93.1 | 0.3 | 0 | – |
| 90% | Oracle | low (10 s) | 93.0 | 0.4 | 0 | – |
| 90% | Oracle | medium (2 s) | 93.0 | 0.4 | 0 | – |
| 90% | SA-CATS (v6) | low (10 s) | 95.0 | 0.8 | 48 | 5.08 |
| 90% | SA-CATS (v6) | medium (2 s) | 94.9 | 0.9 | 259 | 1.07 |
| 90% | SA-CATS (v6) | threshold (0.5 s checks) | 95.2 | 0.7 | 295 | 1.06 |
| 90% | SA-CATS (v6) | high (0.5 s) | 95.6 | 0.7 | 1051 | 0.32 |
| 90% | Prequal | low (10 s) | 82.2 | 1.4 | 53 | 15.08 |
| 90% | Prequal | medium (2 s) | 39.4 | 0.9 | 264 | 0.93 |
| 90% | Prequal | high (0.5 s) | 51.4 | 0.9 | 1056 | 0.17 |
| 90% | Prequal native | medium (2 s) | 89.4 | 0.5 | 26814 | 0.03 |
| 90% | W-Po2 | low (10 s) | 31.9 | 1.9 | 45 | 5.08 |
| 90% | W-Po2 | medium (2 s) | 40.0 | 0.9 | 243 | 1.07 |
| 90% | W-Po2 | threshold (0.5 s checks) | 63.1 | 0.9 | 696 | 0.61 |
| 90% | W-Po2 | high (0.5 s) | 67.7 | 0.8 | 987 | 0.32 |
| 90% | WRR | high (0.5 s) | 95.1 | 0.9 | 0 | – |
| 90% | WRR | low (10 s) | 95.1 | 0.9 | 0 | – |
| 90% | WRR | medium (2 s) | 95.1 | 0.9 | 0 | – |
| 90% | DWRR | low (10 s) | 95.1 | 0.9 | 48 | 5.08 |
| 90% | DWRR | medium (2 s) | 95.1 | 0.9 | 259 | 1.07 |
| 90% | DWRR | threshold (0.5 s checks) | 95.1 | 0.9 | 289 | 1.06 |
| 90% | DWRR | high (0.5 s) | 95.1 | 0.9 | 1051 | 0.32 |
| 110% | CATS-LB | medium (2 s) | 40.3 | 1.3 | 243 | 1.07 |
| 110% | Dahlin LI | medium (2 s) | 33.7 | 1.4 | 259 | 1.07 |
| 110% | ED+drop | medium (2 s) | 56.5 | 1.4 | 259 | 1.06 |
| 110% | Liyanage | medium (2 s) | 30.3 | 5.2 | 264 | 3.41 |
| 110% | LSQ | medium (2 s) | 30.2 | 2.1 | 243 | 1.05 |
| 110% | LSQ-Sample | medium (2 s) | 33.2 | 0.5 | 264 | 0.82 |
| 110% | Nearest | medium (2 s) | 3.7 | 0.3 | 0 | – |
| 110% | Oracle | medium (2 s) | 45.0 | 1.4 | 0 | – |
| 110% | SA-CATS (v6) | medium (2 s) | 78.2 | 0.5 | 259 | 1.07 |
| 110% | Prequal | medium (2 s) | 30.8 | 0.8 | 264 | 0.93 |
| 110% | W-Po2 | medium (2 s) | 25.4 | 0.8 | 243 | 1.07 |
| 110% | WRR | medium (2 s) | 16.8 | 1.5 | 0 | – |
| 110% | DWRR | medium (2 s) | 16.8 | 1.5 | 259 | 1.07 |
| 130% | CATS-LB | low (10 s) | 28.4 | 1.6 | 45 | 5.07 |
| 130% | CATS-LB | medium (2 s) | 24.0 | 1.0 | 243 | 1.07 |
| 130% | CATS-LB | threshold (0.5 s checks) | 23.1 | 0.9 | 420 | 0.87 |
| 130% | CATS-LB | high (0.5 s) | 22.5 | 0.9 | 987 | 0.32 |
| 130% | Dahlin LI | low (10 s) | 11.7 | 0.4 | 48 | 5.08 |
| 130% | Dahlin LI | medium (2 s) | 11.9 | 0.4 | 259 | 1.07 |
| 130% | Dahlin LI | threshold (0.5 s checks) | 13.1 | 0.4 | 549 | 0.80 |
| 130% | Dahlin LI | high (0.5 s) | 12.6 | 0.3 | 1051 | 0.32 |
| 130% | ED+drop | low (10 s) | 46.7 | 1.3 | 48 | 4.98 |
| 130% | ED+drop | medium (2 s) | 40.2 | 0.8 | 259 | 1.05 |
| 130% | ED+drop | threshold (0.5 s checks) | 40.4 | 0.4 | 420 | 0.93 |
| 130% | ED+drop | high (0.5 s) | 42.5 | 0.4 | 1051 | 0.31 |
| 130% | Liyanage | low (10 s) | 11.4 | 2.7 | 53 | 14.31 |
| 130% | Liyanage | medium (2 s) | 17.7 | 5.2 | 264 | 3.55 |
| 130% | Liyanage | high (0.5 s) | 17.3 | 2.9 | 1056 | 0.86 |
| 130% | LSQ | low (10 s) | 4.3 | 0.2 | 45 | 5.06 |
| 130% | LSQ | medium (2 s) | 5.2 | 0.3 | 243 | 1.05 |
| 130% | LSQ | threshold (0.5 s checks) | 25.8 | 0.4 | 976 | 0.31 |
| 130% | LSQ | high (0.5 s) | 25.7 | 0.3 | 987 | 0.31 |
| 130% | LSQ-Sample | low (10 s) | 19.0 | 0.6 | 53 | 3.84 |
| 130% | LSQ-Sample | medium (2 s) | 26.6 | 0.7 | 264 | 0.81 |
| 130% | LSQ-Sample | high (0.5 s) | 29.7 | 0.6 | 1056 | 0.28 |
| 130% | Nearest | high (0.5 s) | 1.7 | 0.1 | 0 | – |
| 130% | Nearest | low (10 s) | 1.7 | 0.1 | 0 | – |
| 130% | Nearest | medium (2 s) | 1.7 | 0.1 | 0 | – |
| 130% | Oracle | high (0.5 s) | 25.6 | 0.3 | 0 | – |
| 130% | Oracle | low (10 s) | 25.5 | 0.2 | 0 | – |
| 130% | Oracle | medium (2 s) | 25.7 | 0.3 | 0 | – |
| 130% | SA-CATS (v6) | low (10 s) | 64.0 | 0.6 | 48 | 5.08 |
| 130% | SA-CATS (v6) | medium (2 s) | 66.0 | 0.3 | 259 | 1.07 |
| 130% | SA-CATS (v6) | threshold (0.5 s checks) | 65.6 | 0.5 | 293 | 1.06 |
| 130% | SA-CATS (v6) | high (0.5 s) | 64.8 | 1.0 | 1051 | 0.32 |
| 130% | Prequal | low (10 s) | 11.6 | 0.4 | 53 | 14.45 |
| 130% | Prequal | medium (2 s) | 24.9 | 0.4 | 264 | 0.94 |
| 130% | Prequal | high (0.5 s) | 29.1 | 0.6 | 1056 | 0.17 |
| 130% | Prequal native | medium (2 s) | 20.8 | 0.5 | 38717 | 0.03 |
| 130% | W-Po2 | low (10 s) | 16.0 | 1.0 | 45 | 5.07 |
| 130% | W-Po2 | medium (2 s) | 17.4 | 1.0 | 243 | 1.07 |
| 130% | W-Po2 | threshold (0.5 s checks) | 25.3 | 0.3 | 825 | 0.48 |
| 130% | W-Po2 | high (0.5 s) | 24.8 | 0.3 | 987 | 0.32 |
| 130% | WRR | high (0.5 s) | 3.9 | 0.1 | 0 | – |
| 130% | WRR | low (10 s) | 3.9 | 0.1 | 0 | – |
| 130% | WRR | medium (2 s) | 3.9 | 0.1 | 0 | – |
| 130% | DWRR | low (10 s) | 3.9 | 0.1 | 48 | 5.07 |
| 130% | DWRR | medium (2 s) | 3.9 | 0.1 | 259 | 1.07 |
| 130% | DWRR | threshold (0.5 s checks) | 3.9 | 0.1 | 296 | 1.06 |
| 130% | DWRR | high (0.5 s) | 3.9 | 0.1 | 1051 | 0.32 |

### Admission fairness: native vs the common rejection wrapper

| Load | Algorithm | Kind | Native success (%) | With wrapper (%) | Gain (pp) | Rejected (%) |
|---|---|---|---|---|---|---|
| 60% | A Nearest site | routing + common wrapper | 11.7 | 11.7 | +0.0 | 0.0 |
| 60% | B Capacity WRR | routing + common wrapper | 98.9 | 98.9 | +0.0 | 0.0 |
| 60% | C Dynamic WRR (measured speeds) | routing + common wrapper | 98.9 | 98.9 | +0.0 | 0.0 |
| 60% | D Weighted power-of-two | routing + common wrapper | 78.6 | 78.6 | +0.0 | 0.0 |
| 60% | E Dahlin (Basic LI) | routing + common wrapper | 97.8 | 97.8 | +0.0 | 0.0 |
| 60% | F LSQ (shared periodic reports) | routing + common wrapper | 98.4 | 98.4 | +0.0 | 0.0 |
| 60% | G Prequal (HCL) | routing + common wrapper | 62.7 | 62.7 | +0.0 | 0.0 |
| 60% | H Liyanage et al. 2026 | routing + common wrapper | 81.9 | 81.9 | +0.0 | 0.0 |
| 60% | I CATS-draft load sharing | routing + common wrapper | 98.5 | 98.5 | +0.0 | 0.0 |
| 60% | L Fresh-state oracle | routing + common wrapper | 96.5 | 96.5 | +0.0 | 0.0 |
| 60% | J Expected delay + drop | native admission control | 98.4 | – | – | 0.0 |
| 60% | K Staleness-Aware CATS (ours v6) | native admission control | 99.0 | – | – | 0.0 |
| 60% | Oracle + fresh-state admission | native admission control | 96.5 | – | – | 0.0 |
| 90% | A Nearest site | routing + common wrapper | 7.6 | 7.6 | +0.0 | 0.0 |
| 90% | B Capacity WRR | routing + common wrapper | 95.1 | 95.1 | +0.0 | 0.0 |
| 90% | C Dynamic WRR (measured speeds) | routing + common wrapper | 95.1 | 95.1 | +0.0 | 0.0 |
| 90% | D Weighted power-of-two | routing + common wrapper | 40.0 | 40.1 | +0.1 | 0.0 |
| 90% | E Dahlin (Basic LI) | routing + common wrapper | 82.5 | 82.5 | +0.0 | 0.0 |
| 90% | F LSQ (shared periodic reports) | routing + common wrapper | 88.5 | 88.5 | +0.0 | 0.0 |
| 90% | G Prequal (HCL) | routing + common wrapper | 39.4 | 39.4 | +0.0 | 0.0 |
| 90% | H Liyanage et al. 2026 | routing + common wrapper | 45.4 | 45.4 | +0.0 | 0.0 |
| 90% | I CATS-draft load sharing | routing + common wrapper | 84.3 | 84.3 | +0.0 | 0.0 |
| 90% | L Fresh-state oracle | routing + common wrapper | 93.0 | 93.0 | +0.0 | 0.0 |
| 90% | J Expected delay + drop | native admission control | 92.7 | – | – | 0.1 |
| 90% | K Staleness-Aware CATS (ours v6) | native admission control | 94.9 | – | – | 0.0 |
| 90% | Oracle + fresh-state admission | native admission control | 93.0 | – | – | 0.0 |
| 110% | A Nearest site | routing + common wrapper | 3.7 | 5.5 | +1.8 | 13.7 |
| 110% | B Capacity WRR | routing + common wrapper | 16.8 | 76.0 | +59.2 | 13.7 |
| 110% | C Dynamic WRR (measured speeds) | routing + common wrapper | 16.8 | 76.0 | +59.2 | 13.7 |
| 110% | D Weighted power-of-two | routing + common wrapper | 25.4 | 31.1 | +5.8 | 13.7 |
| 110% | E Dahlin (Basic LI) | routing + common wrapper | 33.7 | 62.5 | +28.9 | 13.7 |
| 110% | F LSQ (shared periodic reports) | routing + common wrapper | 30.2 | 62.1 | +31.9 | 13.7 |
| 110% | G Prequal (HCL) | routing + common wrapper | 30.8 | 32.0 | +1.1 | 13.7 |
| 110% | H Liyanage et al. 2026 | routing + common wrapper | 30.3 | 37.0 | +6.7 | 13.7 |
| 110% | I CATS-draft load sharing | routing + common wrapper | 40.3 | 57.9 | +17.6 | 13.7 |
| 110% | L Fresh-state oracle | routing + common wrapper | 45.0 | 77.6 | +32.6 | 13.7 |
| 110% | J Expected delay + drop | native admission control | 56.5 | – | – | 8.4 |
| 110% | K Staleness-Aware CATS (ours v6) | native admission control | 78.2 | – | – | 17.7 |
| 110% | Oracle + fresh-state admission | native admission control | 56.8 | – | – | 4.8 |
| 130% | A Nearest site | routing + common wrapper | 1.7 | 4.9 | +3.2 | 27.0 |
| 130% | B Capacity WRR | routing + common wrapper | 3.9 | 64.9 | +61.0 | 27.0 |
| 130% | C Dynamic WRR (measured speeds) | routing + common wrapper | 3.9 | 64.9 | +61.0 | 27.0 |
| 130% | D Weighted power-of-two | routing + common wrapper | 17.4 | 26.8 | +9.5 | 27.0 |
| 130% | E Dahlin (Basic LI) | routing + common wrapper | 11.9 | 52.7 | +40.8 | 27.0 |
| 130% | F LSQ (shared periodic reports) | routing + common wrapper | 5.2 | 54.1 | +48.9 | 27.0 |
| 130% | G Prequal (HCL) | routing + common wrapper | 24.9 | 26.9 | +2.0 | 27.0 |
| 130% | H Liyanage et al. 2026 | routing + common wrapper | 17.7 | 27.2 | +9.4 | 27.0 |
| 130% | I CATS-draft load sharing | routing + common wrapper | 24.0 | 48.9 | +24.9 | 27.0 |
| 130% | L Fresh-state oracle | routing + common wrapper | 25.7 | 66.4 | +40.7 | 27.0 |
| 130% | J Expected delay + drop | native admission control | 40.2 | – | – | 21.4 |
| 130% | K Staleness-Aware CATS (ours v6) | native admission control | 66.0 | – | – | 31.0 |
| 130% | Oracle + fresh-state admission | native admission control | 40.9 | – | – | 16.0 |

### Ablation: v6 minus v6-without-mechanism (pp; > 0 means the mechanism helps)

| Pattern | Load | Mechanism switched off | v6 − ablation (pp) | ± 95% CI | Verdict |
|---|---|---|---|---|---|
| steady | 60% | v6 without A (balance) | +0.00 | 0.04 | same |
| steady | 60% | v6 without B (burst re-plan) | -0.00 | 0.03 | same |
| steady | 60% | v6 without C (corrected risk) | +0.00 | 0.00 | same |
| steady | 60% | v6 without staleness (no ageing) | -0.02 | 0.03 | same |
| steady | 60% | v6 without admission (no drop) | +0.00 | 0.00 | same |
| steady | 90% | v6 without A (balance) | -0.00 | 0.24 | same |
| steady | 90% | v6 without B (burst re-plan) | +0.00 | 0.00 | same |
| steady | 90% | v6 without C (corrected risk) | -0.02 | 0.05 | same |
| steady | 90% | v6 without staleness (no ageing) | -0.10 | 0.17 | same |
| steady | 90% | v6 without admission (no drop) | +0.00 | 0.00 | same |
| steady | 110% | v6 without A (balance) | +0.10 | 0.22 | same |
| steady | 110% | v6 without B (burst re-plan) | +0.00 | 0.00 | same |
| steady | 110% | v6 without C (corrected risk) | +0.00 | 0.00 | same |
| steady | 110% | v6 without staleness (no ageing) | -0.03 | 0.29 | same |
| steady | 110% | v6 without admission (no drop) | +61.30 | 0.77 | better |
| steady | 130% | v6 without A (balance) | +0.00 | 0.00 | same |
| steady | 130% | v6 without B (burst re-plan) | +0.00 | 0.00 | same |
| steady | 130% | v6 without C (corrected risk) | +0.00 | 0.00 | same |
| steady | 130% | v6 without staleness (no ageing) | -0.02 | 0.16 | same |
| steady | 130% | v6 without admission (no drop) | +61.34 | 0.36 | better |
| bursty | 60% | v6 without A (balance) | +0.35 | 0.67 | same |
| bursty | 60% | v6 without B (burst re-plan) | +1.35 | 1.15 | better |
| bursty | 60% | v6 without C (corrected risk) | +0.06 | 0.43 | same |
| bursty | 60% | v6 without staleness (no ageing) | +1.07 | 0.83 | better |
| bursty | 60% | v6 without admission (no drop) | +0.66 | 1.00 | same |
| bursty | 90% | v6 without A (balance) | -0.05 | 0.52 | same |
| bursty | 90% | v6 without B (burst re-plan) | +6.29 | 1.20 | better |
| bursty | 90% | v6 without C (corrected risk) | +0.40 | 0.48 | same |
| bursty | 90% | v6 without staleness (no ageing) | +3.10 | 0.60 | better |
| bursty | 90% | v6 without admission (no drop) | +4.62 | 0.80 | better |
| bursty | 110% | v6 without A (balance) | -0.17 | 0.32 | same |
| bursty | 110% | v6 without B (burst re-plan) | +2.40 | 0.45 | better |
| bursty | 110% | v6 without C (corrected risk) | -0.06 | 0.31 | same |
| bursty | 110% | v6 without staleness (no ageing) | +2.46 | 0.55 | better |
| bursty | 110% | v6 without admission (no drop) | +3.32 | 1.16 | better |
| bursty | 130% | v6 without A (balance) | +0.01 | 0.56 | same |
| bursty | 130% | v6 without B (burst re-plan) | +2.25 | 0.85 | better |
| bursty | 130% | v6 without C (corrected risk) | +0.18 | 0.70 | same |
| bursty | 130% | v6 without staleness (no ageing) | +1.30 | 0.73 | better |
| bursty | 130% | v6 without admission (no drop) | +42.29 | 0.98 | better |

### Scalability: deadline success (%) with 1 / 4 / 16 ingresses

| Load | Algorithm | 1 ingress | 4 ingresses | 16 ingresses |
|---|---|---|---|---|
| 90% | Nearest | 0.0 | 7.6 | 0.9 |
| 90% | WRR | 95.7 | 95.1 | 93.3 |
| 90% | DWRR | 95.7 | 95.1 | 93.3 |
| 90% | W-Po2 | 40.5 | 40.0 | 40.4 |
| 90% | Dahlin LI | 82.6 | 82.5 | 82.4 |
| 90% | LSQ | 96.2 | 88.5 | 14.2 |
| 90% | Prequal | 21.0 | 39.4 | 60.1 |
| 90% | Liyanage | 33.3 | 45.4 | 60.5 |
| 90% | CATS-LB | 79.1 | 84.3 | 86.7 |
| 90% | ED+drop | 96.1 | 92.7 | 83.4 |
| 90% | SA-CATS (v6) | 95.7 | 94.9 | 93.2 |
| 90% | Oracle | 91.4 | 93.0 | 93.1 |
| 130% | Nearest | 0.0 | 1.7 | 0.2 |
| 130% | WRR | 2.2 | 3.9 | 6.5 |
| 130% | DWRR | 2.2 | 3.9 | 6.5 |
| 130% | W-Po2 | 17.2 | 17.4 | 17.3 |
| 130% | Dahlin LI | 11.5 | 11.9 | 11.7 |
| 130% | LSQ | 2.5 | 5.2 | 7.2 |
| 130% | Prequal | 15.5 | 24.9 | 30.4 |
| 130% | Liyanage | 19.2 | 17.7 | 19.6 |
| 130% | CATS-LB | 25.1 | 24.0 | 24.3 |
| 130% | ED+drop | 53.0 | 40.2 | 40.1 |
| 130% | SA-CATS (v6) | 66.2 | 66.0 | 64.8 |
| 130% | Oracle | 26.9 | 25.7 | 25.7 |

### Failures and slowdowns (load 90%): success over the run, recovery after the event

| Event | Algorithm | Success (%) | ± 95% CI | Recovery (s) | Impact during event (pp) |
|---|---|---|---|---|---|
| fail | Nearest | 7.6 | 0.3 | 0.0 | +0.2 |
| fail | WRR | 85.9 | 0.8 | 0.8 | -22.1 |
| fail | DWRR | 83.2 | 1.2 | 2.7 | -24.1 |
| fail | W-Po2 | 37.2 | 1.3 | 0.4 | -6.3 |
| fail | Dahlin LI | 74.4 | 1.1 | 0.5 | -18.4 |
| fail | LSQ | 78.0 | 1.7 | 3.1 | -24.8 |
| fail | Prequal | 37.4 | 0.7 | 1.2 | -7.1 |
| fail | Liyanage | 40.3 | 5.7 | 3.3 | -6.0 |
| fail | CATS-LB | 72.2 | 1.8 | 2.9 | -28.7 |
| fail | ED+drop | 81.8 | 1.2 | 2.9 | -24.3 |
| fail | SA-CATS (v6) | 85.4 | 1.0 | 28.7 | -16.2 |
| fail | Oracle | 84.7 | 1.1 | 0.3 | -19.9 |
| slow | Nearest | 7.6 | 0.3 | 0.0 | +0.3 |
| slow | WRR | 83.1 | 0.7 | 1.1 | -23.7 |
| slow | DWRR | 80.8 | 1.2 | 1.4 | -25.6 |
| slow | W-Po2 | 34.9 | 1.4 | 0.2 | -11.8 |
| slow | Dahlin LI | 72.1 | 1.2 | 0.7 | -17.7 |
| slow | LSQ | 72.6 | 1.3 | 1.3 | -29.3 |
| slow | Prequal | 36.4 | 0.7 | 1.4 | -6.8 |
| slow | Liyanage | 38.3 | 7.5 | 0.4 | -7.5 |
| slow | CATS-LB | 67.7 | 2.3 | 3.4 | -31.4 |
| slow | ED+drop | 79.0 | 1.1 | 1.0 | -25.7 |
| slow | SA-CATS (v6) | 81.8 | 0.8 | 20.6 | -19.6 |
| slow | Oracle | 76.1 | 1.0 | 0.4 | -33.3 |
| congest | Nearest | 7.6 | 0.3 | 0.0 | +0.2 |
| congest | WRR | 94.2 | 0.9 | 0.0 | -3.0 |
| congest | DWRR | 94.2 | 0.9 | 0.0 | -3.0 |
| congest | W-Po2 | 39.3 | 1.1 | 1.0 | -1.5 |
| congest | Dahlin LI | 81.0 | 1.2 | 0.4 | -3.2 |
| congest | LSQ | 87.5 | 2.2 | 0.6 | -3.2 |
| congest | Prequal | 38.8 | 1.0 | 3.3 | -3.5 |
| congest | Liyanage | 43.9 | 5.6 | 3.3 | +1.2 |
| congest | CATS-LB | 82.9 | 2.6 | 1.8 | -4.4 |
| congest | ED+drop | 92.1 | 0.7 | 0.3 | -3.1 |
| congest | SA-CATS (v6) | 94.0 | 1.0 | 0.0 | -3.5 |
| congest | Oracle | 91.9 | 0.5 | 0.0 | -4.0 |
| fail | LSQ-Sample | 39.4 | 1.0 | 1.2 | -7.7 |
| slow | LSQ-Sample | 38.6 | 0.9 | 1.8 | -7.2 |
| congest | LSQ-Sample | 41.9 | 1.1 | 1.8 | -2.2 |

### Homogeneous sites and the relaxed deadline: deadline success (%)

| Load | Algorithm | Heterogeneous, 300 ms | Homogeneous, 300 ms | Heterogeneous, 500 ms |
|---|---|---|---|---|
| 90% | Nearest | 7.6 | 12.1 | 8.9 |
| 90% | WRR | 95.1 | 95.3 | 99.8 |
| 90% | DWRR | 95.1 | 95.3 | 99.8 |
| 90% | W-Po2 | 40.0 | 43.4 | 57.1 |
| 90% | Dahlin LI | 82.5 | 80.8 | 96.8 |
| 90% | LSQ | 88.5 | 86.4 | 79.9 |
| 90% | Prequal | 39.4 | 37.4 | 52.5 |
| 90% | Liyanage | 45.4 | 41.1 | 58.1 |
| 90% | CATS-LB | 84.3 | 83.4 | 98.0 |
| 90% | ED+drop | 92.7 | 93.0 | 99.6 |
| 90% | SA-CATS (v6) | 94.9 | 95.3 | 99.7 |
| 90% | Oracle | 93.0 | 94.9 | 99.7 |
| 130% | Nearest | 1.7 | 6.2 | 1.8 |
| 130% | WRR | 3.9 | 2.9 | 4.0 |
| 130% | DWRR | 3.9 | 2.9 | 4.0 |
| 130% | W-Po2 | 17.4 | 18.6 | 22.7 |
| 130% | Dahlin LI | 11.9 | 14.5 | 12.7 |
| 130% | LSQ | 5.2 | 6.2 | 5.4 |
| 130% | Prequal | 24.9 | 24.3 | 33.2 |
| 130% | Liyanage | 17.7 | 19.4 | 29.3 |
| 130% | CATS-LB | 24.0 | 20.7 | 29.0 |
| 130% | ED+drop | 40.2 | 38.8 | 42.7 |
| 130% | SA-CATS (v6) | 66.0 | 66.0 | 69.0 |
| 130% | Oracle | 25.7 | 29.4 | 27.8 |

