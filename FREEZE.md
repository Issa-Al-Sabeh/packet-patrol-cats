# v6 freeze (checkpoint)

Frozen on 12 Nov 2026, before the revision the professor asked for (feedback of 11 Nov 2026).

**Rule from now on:** this folder is never edited. Any change is a new version, **v6.1**, kept in a separate folder or branch and tested on new seeds **301–310**. If the 8-site network influences a change, it is no longer fully held out, and a fresh evaluation set is used.

## What is frozen

- The rule `SplitV6` (`ours_v6`) in `catsim/rules_v6.py`, built on `SplitDrop` (`catsim/rules_v5.py`) and `SplitSpeed`/`SpeedMeter` (`catsim/rules.py`).
- The simulator (`catsim/engine.py`, `catsim/queueing.py`, `catsim/config.py`).
- The 11 baselines and the common drop wrapper (`catsim/baselines.py`, documented in `BASELINES.md`).
- Study 1, the 61 tests (`catsim/v5.py`, `catsim/v6.py`, `run_v6.py`, `README_v6.md`).
- Study 2, the 11-baseline study (`catsim/study.py`, `run_study.py`, `study_config.json`, `STUDY_README.md`, `RESULTS.md`).

The ablation switches in `rules_v6.py` (no aging, no drop, without A/B/C) are off by default. With them off, v6's decisions are the same as in the 61-test study.

## v6 parameters

| Parameter | Value | Where | Meaning |
|---|---|---|---|
| U_MAX | 0.95 | rules.py | Never plan a site above 95% of its measured capacity; also the overload test |
| RHO_MAX | 0.95 | rules.py | ρ in κ = ρ/(1−ρ) is capped here, so κ ≤ 19 |
| LATE_SAFE | 0.5 | rules.py | n_safe = largest queue with late chance ≤ 0.5; sites with late(0) > 0.5 are skipped |
| CHUNKS | 100 | rules.py | Traffic shared out in 1% pieces |
| POINTS | 4 | rules.py | Moments of the next interval at which the late chance is averaged |
| EWMA | 0.3 | rules.py | Weight of a new counter value in the offered-traffic estimate |
| SETTLE | 0.05 s | rules.py | Plan 50 ms after the last report of a round arrived |
| CHECK_RATE | 0.01 | rules.py | Calibration weight per answer (about the last 100 answers) |
| CHECK_MIN, CHECK_MAX, CHECK_EPS | 0.05, 20, 0.005 | rules.py | Limits and smoothing of the calibration factor |
| CAL_MIN | 100 | rules_v5.py | Answers needed before the drop option is used |
| DROP_COST | 1.0 | rules_v5.py | A dropped frame costs one miss |
| OwnDrops.MAX | 0.9 | rules_v5.py | Own drop share capped at 90% in the estimator |
| GAIN | 0.25 | rules_v6.py | A: use the risk plan only if it predicts ≥ 25% fewer late frames (chosen on pilot seeds) |
| RISE_Z | 3.0 | rules_v6.py | B1: take a site's count at once if > 3 sd above the estimate |
| BURST_WIN, CHECK_EVERY | 2.0 s, 0.25 s | rules_v6.py | B2: own count over the last 2 s, checked every 0.25 s |
| BURST_Z, BURST_REL | 4.0, 0.25 | rules_v6.py | B2: re-plan if > 4 sd and > 25% different |
| BURST_GAP, MIN_COUNT | 0.5 s, 20 | rules_v6.py | B2: at most one re-plan per 0.5 s; needs ≥ 20 expected frames |
| SpeedMeter BUSY, MIN_SPAN, MAX_SPAN, Z | 2.0, 5 s, 10 s, 2.0 | rules.py | Capacity measured only while the queue is ≥ 2× the servers |
| SpeedMeter BACK_BASE, BACK_CAP | 20 s, 8 | rules.py | Quiet spell of max(20 s, 4W) before a server is restored |

The baselines' tuned settings are in `study_results/frozen_params.json` (frozen 3 Nov 2026).

## Seeds

- Pilot (tuning only): 101–105.
- Final results: 201–210.
- Reserved for v6.1 and any revised evaluation: 301–310.

## Reproduce

```
pip install -r requirements.txt
python3 -m pytest tests -q              # simulator and baseline checks
python3 run_v6.py                       # Study 1: 61 tests, 8,230 runs (seeds 201-210)
python3 -m catsim.v6_analysis           # Study 1 tables
python3 run_study.py --run              # Study 2: 10,110 runs (seeds 201-210)
python3 run_study.py --tables --plots   # Study 2 tables and figures
python3 -m catsim.study_writeup > RESULTS.md
```

## Fingerprints (SHA-256)

Key files:

| File | SHA-256 |
|---|---|
| `catsim/baselines.py` | `23975aaa1acd26277ed1782e084b2c06f86133e6fd11f42e465ccd6b6171c9d3` |
| `catsim/config.py` | `0589fd1c315df2930dba99ad57b6ff0534543051b22e96b1ce3336a77bdc40fa` |
| `catsim/engine.py` | `d14d2c59d74481a1cc50df5257c2247e9a31da1b76dd64a450987eb8b6315cf3` |
| `catsim/queueing.py` | `452a2131079b044a2390893d6f4b9db4bd4287201835909c1f507f92749cbc5e` |
| `catsim/rules.py` | `9c96532e227ec256e87b6ea73ab22b26a3c5bde39a0be2df6e2832e9ec19c527` |
| `catsim/rules_v5.py` | `9afb0dc60d366f0654195ebe990c602bea947477fa8ec3051d1b7a2aba33f061` |
| `catsim/rules_v6.py` | `b9193c0cbfe1dcd8dcf2e95f417671fbcac5a69f9a6b4d38ed66c6c1ee026f4a` |
| `catsim/study.py` | `f3701300136577636b851a0beaaf8c6d3672cdc8c1277a36f3c1c3f920084456` |
| `catsim/v5.py` | `22a00f6d9579a4925933d849da28c045e3fd78b32f010b77fdf6c4d667247580` |
| `catsim/v6.py` | `9ff41984e175adcbf5141a9cd23d9d308dd619146521a6de5af916aa917e14b8` |
| `study_results/frozen_params.json` | `6efb86af1aae4c1c7db63dca6a3eabf82632b0cf32fa8aed34e610a16a66708b` |

Other files:

| File | SHA-256 |
|---|---|
| `catsim/__init__.py` | `6b2c8ea67a5cc6b1a85d666e71862506679845bd3130fdce2a6a66b909134201` |
| `catsim/analysis.py` | `8751f613c08ed5dd535988dba762918d8559f4dc758a4836b9a271aa19370ffc` |
| `catsim/checks.py` | `d54f4e0140040feaa6501cc7b6da7d3e10b470f6cc91cb64db175d567014bfa5` |
| `catsim/experiments.py` | `3cbc382bb38b3dfafe862f6a32dd57ecd3272c1031138566fc9e10e4c67a8bc7` |
| `catsim/large.py` | `e4402c15148b89a4ee12852988d2fdffe952f077171dc5bfa87e8f573579504c` |
| `catsim/large_report.py` | `251847b5915bb54833534fd67441791ce0abe8899fcf846194a71baca911c339` |
| `catsim/plots.py` | `1434262b0d9f74d0464651754ff31cd63346be6479a644b592728957536aa0f2` |
| `catsim/report.py` | `84559e08015a75829f41654afa78cc68108f1857b0350af5798cda67c93610d6` |
| `catsim/study_analysis.py` | `efd87328fdf24744a34962439706936ca8457ff79069591229acd8f328c86ca0` |
| `catsim/study_diagnostics.py` | `19a04b2663c669cc38c54f71d19d8f5081c54a84e618b70cd85ad294cb195737` |
| `catsim/study_plots.py` | `48a19e1b8e030726d8005ef1047094ffcc83e3c8040a6377c67e1a1a3f22f632` |
| `catsim/study_report.py` | `bd29a9fa26cef8a3f358ed31e65f2b10ca4cbc4f4cf999b909ed383bfd78efca` |
| `catsim/study_writeup.py` | `951665398c057ea240f1305036def67bff9e9641f58c9ad34ca479612fd228bd` |
| `catsim/v5_report.py` | `d15b7d29317f11a47818bfd7713b40c2f6790b27f5a8e7496bb3d3be0507cea3` |
| `catsim/v6_analysis.py` | `0413d9982d04724c8b68a71557eb4b54158893f6d8b281d329939af158ecf69d` |
| `run_all.py` | `d22885635d5d4426a4a63b506f35c44d3104d4fe8027dde75610b5011fc8f063` |
| `run_large.py` | `14dc2a59f59b5599a58e5bab76f3d590e83de09d3e6ecef1d18f117d86bbcbec` |
| `run_study.py` | `0761eb20041b10c33b2be5ebbf11ddea1f84fa036c97b84bae1763a4cfa26626` |
| `run_v5.py` | `b5eeabbcc4fc40bbe8f67282cc49f3218e321dec9ae5c8a300987afdf3586fcd` |
| `run_v6.py` | `10677692742109f50680888cbc82d3ebea016e04e8c061cc7c18734f829788b6` |
| `study_config.json` | `3e303c8b9e179b83da48be6ffcd1e03ff306e60386845e1205fd86cfc616a09d` |

Check with: `sha256sum -c` on these lines, or compare after any copy.
