# v6.1: changes since the v6 freeze

- **The frozen v6 is the git tag `v6-frozen`.** `FREEZE.md` and its fingerprints describe that tag, not this branch.
- **v6.1 is frozen: git tag `v6.1-frozen`, described by `FREEZE_v6.1.md`** (15 Nov 2026). Its evaluation set is fixed in `catsim/v61.py`.
- **Rule for every change:** it is off for the old rules. Any v6 or baseline run gives the same numbers as at the tag.
- **Seeds:** choices between options use pilot seeds 101 to 105 only. The final evaluation of v6.1 uses seeds 301 to 310.

## Changes

| # | Date | Change | Why | Files | Checked by |
|---|---|---|---|---|---|
| 1 | 14 Nov 2026 | **Aggregate drop counter.** An ingress may put a count of the frames it dropped on a frame it sends anyway. Each site reports the sum of the counts it received. Bytes are counted (2 per count, 2 more per report). Off for every rule that does not ask for it. | Phase 1: the offered-traffic estimate of v6 is wrong when ingresses drop different shares (`feedback/estimator.md`). | `catsim/engine.py`, `catsim/config.py` (`echo_bytes`), `catsim/rules.py` (base class: `uses_drop_echo`, `echo_out`, `on_report_e`) | `tests/test_v61.py`; 445 saved runs re-run and identical |
| 2 | 14 Nov 2026 | **Rule `ours_v61`.** v6 with the estimate taken from the drop counter, and the clear-rise test comparing arrivals with expected arrivals. `ours_v61_oldrise` keeps v6's rise test (ablation). | Same. | `catsim/rules_v61.py` | `tests/test_v61.py` (the counterexample; equal to v6 while nothing is dropped) |
| 3 | 14 Nov 2026 | **Wrapper `<rule>+adm61`.** The common rejection wrapper with the same corrected estimate, as the matched-admission rival of v6.1. | The old wrapper uses v6's estimate, so it has the same error. | `catsim/baselines.py` | `tests/test_v61.py` |
| 4 | 15 Nov 2026 | **Three neutral hooks in the v6 planner:** the backlog penalty as a method (`_kappa`), the drop threshold as a setting (`DROP_FROM`, off), a diagnostic hook after the greedy loop (`_after_greedy`, `trace`). `KAPPA` (off) in v6.1 for the constant-penalty check. | Phase 2: sensitivity of the caps and the greedy check (`feedback/cost.md`). | `catsim/rules_v6.py`, `catsim/rules_v61.py` | 445 saved runs re-run and identical; 69 tests |
| 5 | 15 Nov 2026 | **`ours_v61` is in overload mode from 90% of the measured capacity** (`DROP_FROM = 0.90`; v6: 95%): it may drop, and it uses its plan without the balance rule. The site limit stays at 95%. | Phase 2: better in 2 of 16 pilot scenarios, worse in none; it removes the loss at 95% load that the corrected estimate caused (`feedback/cost.md`, sections 5, 7, 8). | `catsim/rules_v61.py` | `test_drop_threshold_of_v61`; `feedback/phase2/sens.csv`, `sens_final.csv` |
| 6 | 15 Nov 2026 | **Baseline `static_deadline`.** A split fixed in advance from capacities, deadline and round trips, used with `+adm61`. Design load 0.95, chosen on pilot seeds. | Phase 3: the feedback asks for a stronger static baseline (`feedback/baselines.md`, section 6). | `catsim/baselines.py` | `test_static_deadline_split`; `feedback/phase3/static.csv` |
| 7 | 15 Nov 2026 | **"Oracle" is renamed "fresh-state greedy selection"** in labels and titles. The run name `oracle` and every number are unchanged. | Phase 3: it is a per-frame greedy rule on the true state, not an upper bound. | `catsim/study.py`, `v5.py`, `v6.py`, `v6_analysis.py`, `plots.py`, `config.py`, `BASELINES.md` | 445 saved runs re-run and identical |
| 8 | 15 Nov 2026 | **The evaluation set of v6.1:** a new network, Batches A and B, seeds 301 to 310. | The freeze (`FREEZE_v6.1.md`). | `catsim/v61.py` | `test_evaluation_set_of_the_freeze` |

- The LSQ variants of the diagnostic (`feedback/phase3/lsq_variants.py`) and the best-plan planner (`feedback/phase2/planner_opt.py`) are diagnostics. They are not rules of the study.

## Not changed

- `MODEL_VERSION` in `catsim/config.py`. Old rules behave exactly as before, so saved runs keep their file names.
- Every v6 rule, every baseline, every saved result.

## Known limits carried by v6.1 (until the phase named)

- **Capacity meter.** It measured a site one or two servers too low in 9 of 110 runs without any failure. Handled with the slow-recovery work (Batch C).
- **Slow recovery** after a burst ends or a server returns (`RESULTS.md`, Q9). Batch C.
- **The backlog penalty has no measurable effect at the frozen settings** on pilot seeds (`feedback/cost.md`, section 8). Batch A measures it on the evaluation seeds.
- **Resolved:** the loss at exactly 95% load (change 5).
