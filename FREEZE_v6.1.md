# v6.1 freeze

- **Frozen on 15 Nov 2026**, git tag `v6.1-frozen`, before any run on the evaluation seeds.
- **The frozen v6 stays what it was:** tag `v6-frozen`, described by `FREEZE.md`.
- **Rule from now on:** `ours_v61`, the wrapper `+adm61`, the static split, the simulator and the evaluation set below do not change. A later fix (Batch C) is a new version with its own note, designed on pilot seeds only and reported next to v6.1, not in its place.
- This file is written by `feedback/phase5/build_freeze.py` from the code and the result files.

## What is frozen

| Item | Where |
|---|---|
| The rule `ours_v61` | `catsim/rules_v61.py` (`SplitV61`), on top of `SplitV6` (`catsim/rules_v6.py`) |
| The matched-admission wrapper `<rule>+adm61` | `catsim/baselines.py` (`AdmissionWrapper61`) |
| The deadline-aware static split `static_deadline` | `catsim/baselines.py` (`StaticDeadline`), design load 0.95 |
| The simulator with the drop counter | `catsim/engine.py`, `catsim/config.py` (`echo_bytes` = 2) |
| The evaluation set: networks, scenarios, rules, seeds | `catsim/v61.py` |
| Every baseline of the v6 study, unchanged | `BASELINES.md`, `study_results/frozen_params.json` |

- Old results are untouched: 445 of 445 saved v6 runs, re-run on this code, match exactly (`feedback/phase5/repro_at_freeze.csv`).

## What v6.1 changes in v6

| # | Change | v6 | v6.1 | Chosen on | Evidence |
|---|---|---|---|---|---|
| 1 | Offered-traffic estimate | arrivals ÷ (1 − the ingress's own drop share) | arrivals ÷ (1 − everyone's drop share), from a drop counter carried in the reports | pilot seeds, Beirut | `feedback/estimator.md` |
| 2 | "Clear rise" test of the estimate | compares arrivals with offered traffic | compares arrivals with expected arrivals | pilot seeds, Beirut | `feedback/estimator.md`, section 4 |
| 3 | Overload threshold | overload mode (may drop; plan used without the balance rule) from 95% of measured capacity | from 90% (site limit still 95%) | pilot seeds, Beirut | `feedback/cost.md`, sections 5, 7, 8 |

- **Not changed:** the cost, the backlog penalty (formula and cap; only its name in the paper changes), the greedy planner, the 25% gain rule, the burst check, the calibration, the capacity meter.
- **Cost in telemetry:** 2 bytes per report and 2 bytes per drop count sent. Counted in every comparison.
- **Known limits, not fixed in v6.1:** the capacity meter can read a site too low without any failure (`feedback/estimator.md`, section 5), and recovery after a burst or a server's return is slow (`RESULTS.md`, Q9). Both go to Batch C.

## Parameters of `ours_v61`

Switches: `uses_drop_echo` = True, `like_rise` = True, `use_balance` = True, `use_burst` = True, `cal_split` = True, `allow_drop` = True, `no_age` = False, `tie_drop` = False.

| Parameter | Value | Set in | Against v6 | Meaning |
|---|---|---|---|---|
| `BURST_GAP` | 0.5 | `SplitV6` |  |  |
| `BURST_REL` | 0.25 | `SplitV6` |  |  |
| `BURST_WIN` | 2.0 | `SplitV6` |  |  |
| `BURST_Z` | 4.0 | `SplitV6` |  |  |
| `CAL_MIN` | 100 | `SplitDrop` |  | answers needed before dropping is allowed |
| `CHECK_EPS` | 0.005 | `SplitRule` |  |  |
| `CHECK_EVERY` | 0.25 | `SplitV6` |  |  |
| `CHECK_MAX` | 20.0 | `SplitRule` |  |  |
| `CHECK_MIN` | 0.05 | `SplitRule` |  |  |
| `CHECK_PRIOR` | 0.02 | `SplitRule` |  |  |
| `CHECK_RATE` | 0.01 | `SplitRule` |  |  |
| `CHUNKS` | 100 | `SplitRule` |  |  |
| `DROP_COST` | 1.0 | `SplitDrop` |  | a dropped frame costs one miss |
| `DROP_FROM` | 0.9 | `SplitV61` | **changed** (v6: 0.95, the site limit) | overload threshold: above this share of the measured capacity, dropping is allowed and the plan is used without the balance rule |
| `ECHO_FRAC` | 0.25 | `SplitV61` | **new** | an ingress sends its drop count at most every W × this |
| `EWMA` | 0.3 | `SplitRule` |  | weight of a new value in the offered-traffic estimate |
| `GAIN` | 0.25 | `SplitV6` |  | below overload, keep the plan only if it predicts this much fewer late frames than the capacity split |
| `GRID` | 13 | `SplitRule` |  |  |
| `KAPPA` | None | `SplitV61` | **new** | None = the penalty formula κ = ρ ÷ (1 − ρ); a number would replace it (checks only) |
| `LATE_SAFE` | 0.5 | `SplitSpeed` |  | risk tolerance in the safe queue length |
| `MIN_COUNT` | 20.0 | `SplitV6` |  |  |
| `POINTS` | 4 | `SplitRule` |  |  |
| `RHO_MAX` | 0.95 | `SplitSpeed` |  | cap on ρ in κ, so κ ≤ 19 |
| `RISE_Z` | 3.0 | `SplitV6` |  | a rise beyond this many sd is taken at once |
| `SETTLE` | 0.05 | `SplitRule` |  |  |
| `TIE_TOL` | 1e-09 | `SplitV6` |  |  |
| `U_LIMIT` | 0.95 | `SplitDrop` |  | no site is planned above this share of its measured capacity |
| `U_MAX` | 0.95 | `SplitRule` |  |  |

- Parameters without a note are described in `FREEZE.md` (the v6 table) and `feedback/cost.md` (section 4).
- `+adm61`: admits up to 0.95 of the configured capacity, with the estimate of change 1.

## Seeds

| Seeds | Role | Used so far by |
|---|---|---|
| 101 to 105 | pilot: every choice of v6 and of v6.1 | the pilots of Phases 1, 2 and 3 (Beirut only) |
| 201 to 210 | the final results of v6 | the v6 studies; since the v6 freeze: reproduction, the diagnosis of v6's estimate, the LSQ diagnostic |
| 301 to 310 | **evaluation of v6.1** | nothing |

- Checked on 14 result files: the largest seed in any of them is 210.
- One exception to "v6.1 never ran on 201 to 210": a unit test runs v6.1 on seed 201 in the main scenario, to check that it equals v6 while nothing is dropped.
- First pass: seeds 301 to 305. Seeds 306 to 310 complete it to ten.

## Was the 8-site network used?

- **Yes, to diagnose. No, to choose.**
- Phase 1 measured the frozen v6 on it (seeds 201 to 205). It showed the largest estimate error we found (3.1 times the truth with reports every 0.5 s; `feedback/estimator.md`, section 3).
- Phase 3 diagnosed the LSQ baseline on it (same seeds).
- Rules run on it since the v6 freeze: `lsq`, `lsq_poll_phase`, `lsq_poll_site`, `lsq_poll_sync`, `lsq_randtie`, `lsq_sample`, `ours_v6`, `wrr`, `wrr_phase`. No version of v6.1.
- Every option and setting of v6.1 was chosen on Beirut with seeds 101 to 105.
- Still, we looked at where v6 was most wrong on it. By the rule of `FREEZE.md`, we no longer call it fully held out, and the evaluation uses a fresh set: new seeds everywhere, and a network that was never run.

## The evaluation set

**Networks**

| Network | Sites (GPUs) | Ingresses | Reports | Status |
|---|---|---|---|---|
| Beirut | 3 (2, 4, 8) | 4 | every 5 s | the design network; new seeds only |
| 8 sites | 8 (1, 2, 2, 3, 4, 5, 7, 8) | 4 | every 2 s | diagnosed, not designed on; new seeds |
| New | 5 (2, 3, 5, 6, 8) | 6 | every 3 s | **never run** |

**The new network** (`catsim/v61.py`)

| Site | Edge 1 | Edge 2 | Metro | Regional DC | Remote DC |
|---|---|---|---|---|---|
| GPUs | 2 | 3 | 5 | 6 | 8 |
| Round trip from Ingress A (ms) | 6 | 14 | 28 | 45 | 120 |

- 24 GPUs, 240 frames/s. Same application: 10 frames/s per GPU, 300 ms deadline.
- 6 ingresses with shares 29%, 24%, 19%, 14%, 10%, 5%. Their round trips are up to 30% shorter or longer than Ingress A's.
- **Why this one:** the largest site is far. Its round trip is 40% of the deadline (Beirut's farthest: 20%), so sending by capacity alone is no longer free. This is where a deadline-aware rule and a capacity rule should differ.
- It was defined without running anything on it. One 30-second run on seed 1 checks that it executes; its results are not read.

**Batch A: where does the gain come from?** (22 scenarios × 7 rules × 5 seeds = 770 runs)

| Rule | Run name | What the comparison with v6.1 shows |
|---|---|---|
| Ours v6.1 | `ours_v61` | |
| Round-robin + matched admission | `wrr+adm61` | **primary comparison:** the gain over no steering, at equal telemetry and equal chance to drop |
| Static split + matched admission | `static_deadline+adm61` | the gain over the best split that needs no reports |
| v6.1 without the backlog penalty | `ours_v61@KAPPA=0` | what the penalty adds |
| v6.1 without dropping | `ours_v61@allow_drop=False` | what admission adds to v6.1's routing |
| Ours v6 (frozen) | `ours_v6` | what the three changes did |
| Round-robin | `wrr` | the floor; with the row above, what routing adds without admission |

| Network | Scenario | What it is | |
|---|---|---|---|
| Beirut | `main` | Main scenario (Beirut) | pilot scenario |
| Beirut | `load=95` | Load (%): 95 | pilot scenario |
| Beirut | `O_110` | Load 110% |  |
| Beirut | `O_130` | Load 130% | pilot scenario |
| Beirut | `O_150` | Load 150% |  |
| Beirut | `O_burst` | Burst: 85% load, 140% from 60 s to 80 s | pilot scenario |
| Beirut | `O_surge` | Incident: Ingress A doubles its frames from 50 s to 100 s (load 119%) |  |
| Beirut | `server_fail_recover` | Server failure: Hamra loses 1 of its 2 servers at 50 s, gets it back at 100 s | pilot scenario |
| Beirut | `O_dc_half` | DC failure: the DC loses 4 of its 8 servers from 50 s to 110 s (119% of what works) |  |
| Beirut | `wrong_weights` | Wrong weights: rules are told the DC has 8 servers, only 6 work | pilot scenario |
| 8 sites | `L90_d50_steady_W2_R4_het_D300` | Load 90%, steady, reports every 2 s |  |
| 8 sites | `L110_d50_steady_W2_R4_het_D300` | Load 110%, steady, reports every 2 s |  |
| 8 sites | `L130_d50_steady_W2_R4_het_D300` | Load 130%, steady, reports every 2 s |  |
| 8 sites | `L90_d50_bursty_W2_R4_het_D300` | Load 90%, bursty, reports every 2 s |  |
| 8 sites | `L110_d50_bursty_W2_R4_het_D300` | Load 110%, bursty, reports every 2 s |  |
| 8 sites | `L130_d50_bursty_W2_R4_het_D300` | Load 130%, bursty, reports every 2 s |  |
| New | `N_85` | New network: load 85% |  |
| New | `N_95` | New network: load 95% |  |
| New | `N_115` | New network: load 115% |  |
| New | `N_130` | New network: load 130% |  |
| New | `N_burst` | New network: burst, 85% load, 140% from 60 s to 80 s |  |
| New | `N_fail` | New network: the Regional DC loses 2 of its 6 servers at 50 s, gets them back at 100 s |  |

**Batch B: does the estimate hold when ingresses differ?** (14 scenarios × 4 rules × 5 seeds = 280 runs)

| Rule | Run name |
|---|---|
| Ours v6.1 (drop counter) | `ours_v61` |
| Ours v6 (own drop share) | `ours_v6` |
| Round-robin + admission, drop counter | `wrr+adm61` |
| Round-robin + admission, own drop share | `wrr+adm` |

| Network | Scenario | What it is | |
|---|---|---|---|
| Beirut | `O_130` | Load 130% | pilot scenario |
| Beirut | `B_130_equal` | Load 130%, equal shares |  |
| Beirut | `B_130_stagger` | Load 130%, sites report at different moments |  |
| Beirut | `B_130_loss` | Load 130%, 30% of reports lost |  |
| Beirut | `O_130_W1` | Load 130%, reports every 1 s |  |
| Beirut | `O_surge` | Incident: Ingress A doubles its frames from 50 s to 100 s (load 119%) |  |
| 8 sites | `L130_d50_steady_W2_R4_het_D300` | Load 130%, steady, reports every 2 s |  |
| 8 sites | `L130_d50_shifting_W2_R4_het_D300` | Load 130%, shifting, reports every 2 s |  |
| 8 sites | `L110_d50_bursty_W2_R4_het_D300` | Load 110%, bursty, reports every 2 s |  |
| 8 sites | `L130_d50_steady_W0.5_R4_het_D300` | Load 130%, steady, reports every 0.5 s |  |
| 8 sites | `L130_d50_steady_W2_R16_het_D300` | Load 130%, steady, reports every 2 s, 16 ingresses |  |
| New | `N_130` | New network: load 130% |  |
| New | `N_130_stagger` | New network: load 130%, sites report at different moments |  |
| New | `N_surge` | New network: load 95%, the largest ingress doubles its frames from 50 s to 100 s |  |

- Measured in each run, besides deadline success: the estimate ÷ the true offered traffic at each ingress, the drop share of each ingress, the admitted traffic ÷ capacity, and the telemetry bytes.

**Rules of the analysis, fixed now**
- **Deadline success** = frames answered within the deadline ÷ all frames generated after the warm-up. A frame dropped at the ingress, discarded at a site or answered late counts as a miss.
- Differences are paired by seed, with a 95% interval (t, 4 degrees of freedom on five seeds).
- Every scenario is reported, losses included. The rejected share is shown next to success.
- No scenario, rule or seed is removed after the runs. Anything added later is marked "added after the freeze".
- "Pilot scenario" above = v6.1's settings were chosen on that scenario (with other seeds). Results on those and on the others are shown separately.

## Reproduce

```
pip install -r requirements.txt
python3 -m pytest tests feedback/phase1/test_estimator.py -q    # 72 tests
python3 feedback/repro_check.py --frozen . --out /tmp/repro.csv # the 445 saved v6 runs, on this code
python3 feedback/phase5/build_freeze.py                         # this file
```

## Fingerprints (SHA-256)

| File | SHA-256 |
|---|---|
| `catsim/__init__.py` | `6b2c8ea67a5cc6b1a85d666e71862506679845bd3130fdce2a6a66b909134201` |
| `catsim/analysis.py` | `8751f613c08ed5dd535988dba762918d8559f4dc758a4836b9a271aa19370ffc` |
| `catsim/baselines.py` | `c106fe527123ee660fa80df45699fa93aed839c2bdd45d77d21769246f03e881` |
| `catsim/checks.py` | `d54f4e0140040feaa6501cc7b6da7d3e10b470f6cc91cb64db175d567014bfa5` |
| `catsim/config.py` | `896fde12d80e584b2715d20c70c27b9e900059018aceb293c32d27bddefb2065` |
| `catsim/engine.py` | `3f89e395bb637d1646b443ab95e9b401abcd50959142c829b8c3629318bacc9e` |
| `catsim/experiments.py` | `3cbc382bb38b3dfafe862f6a32dd57ecd3272c1031138566fc9e10e4c67a8bc7` |
| `catsim/large.py` | `e4402c15148b89a4ee12852988d2fdffe952f077171dc5bfa87e8f573579504c` |
| `catsim/large_report.py` | `251847b5915bb54833534fd67441791ce0abe8899fcf846194a71baca911c339` |
| `catsim/plots.py` | `bcff4f997c51a0de7b39b2ad155e347194d694ec35666472c68b2cf7d8187f8d` |
| `catsim/queueing.py` | `452a2131079b044a2390893d6f4b9db4bd4287201835909c1f507f92749cbc5e` |
| `catsim/report.py` | `84559e08015a75829f41654afa78cc68108f1857b0350af5798cda67c93610d6` |
| `catsim/rules.py` | `2a67887e5e4ae663b67c57f5cc676830707fdfcb8ea6701b9e54ec912d44be9e` |
| `catsim/rules_v5.py` | `9afb0dc60d366f0654195ebe990c602bea947477fa8ec3051d1b7a2aba33f061` |
| `catsim/rules_v6.py` | `433afc01be809758b657a25f7b107d7cf8bf2139f6c305e08b360be962b4e751` |
| `catsim/rules_v61.py` | `4a82cde097ea8d9eb588a7127c93d1343641552d71305d580808b96f0bfb9967` |
| `catsim/study.py` | `6728503cc94198903ebdfae4ce7d35ddb755d790d2c5cf24e7d88655e4747826` |
| `catsim/study_analysis.py` | `efd87328fdf24744a34962439706936ca8457ff79069591229acd8f328c86ca0` |
| `catsim/study_diagnostics.py` | `19a04b2663c669cc38c54f71d19d8f5081c54a84e618b70cd85ad294cb195737` |
| `catsim/study_plots.py` | `48a19e1b8e030726d8005ef1047094ffcc83e3c8040a6377c67e1a1a3f22f632` |
| `catsim/study_report.py` | `bd29a9fa26cef8a3f358ed31e65f2b10ca4cbc4f4cf999b909ed383bfd78efca` |
| `catsim/study_writeup.py` | `951665398c057ea240f1305036def67bff9e9641f58c9ad34ca479612fd228bd` |
| `catsim/v5.py` | `5285e8984fcb5c81f7607c075a0e430f328b864a6576316bb3933990ff3a7531` |
| `catsim/v5_report.py` | `d15b7d29317f11a47818bfd7713b40c2f6790b27f5a8e7496bb3d3be0507cea3` |
| `catsim/v6.py` | `90e7345f43b5ea30eba9125995bb1e58ccff80ea12be5214557c8ae1d4819c29` |
| `catsim/v61.py` | `5edbcd96f0994c657b827e5fb4c4ce0534ed2ed3e87b0626793b5ca4393fd0d5` |
| `catsim/v6_analysis.py` | `566918c1ac3a0d1240cddf0b950dc8788c3cdf1c73085373f88bbb4dacb689cf` |
| `study_config.json` | `3e303c8b9e179b83da48be6ffcd1e03ff306e60386845e1205fd86cfc616a09d` |
| `study_results/frozen_params.json` | `6efb86af1aae4c1c7db63dca6a3eabf82632b0cf32fa8aed34e610a16a66708b` |
| `tests/test_simulator.py` | `e622f595ba9555229ad39fd26c637848af7705bca9bdbb0d35db1e5068e923b8` |
| `tests/test_v61.py` | `9077f31439f8d11221f256c44f774dbfe5d548b1c7d4eb20a5bad79ed9b5464b` |
