# v6.1: changes since the v6 freeze

- **The frozen v6 is the git tag `v6-frozen`.** `FREEZE.md` and its fingerprints describe that tag, not this branch.
- **v6.1 is not frozen yet.** It is frozen after the cost and planner checks (Phase 2) and the baseline audit (Phase 3).
- **Rule for every change:** it is off for the old rules. Any v6 or baseline run gives the same numbers as at the tag.
- **Seeds:** choices between options use pilot seeds 101 to 105 only. The final evaluation of v6.1 uses seeds 301 to 310.

## Changes

| # | Date | Change | Why | Files | Checked by |
|---|---|---|---|---|---|
| 1 | 14 Nov 2026 | **Aggregate drop counter.** An ingress may put a count of the frames it dropped on a frame it sends anyway. Each site reports the sum of the counts it received. Bytes are counted (2 per count, 2 more per report). Off for every rule that does not ask for it. | Phase 1: the offered-traffic estimate of v6 is wrong when ingresses drop different shares (`feedback/estimator.md`). | `catsim/engine.py`, `catsim/config.py` (`echo_bytes`), `catsim/rules.py` (base class: `uses_drop_echo`, `echo_out`, `on_report_e`) | `tests/test_v61.py`; 445 saved runs re-run and identical |
| 2 | 14 Nov 2026 | **Rule `ours_v61`.** v6 with the estimate taken from the drop counter, and the clear-rise test comparing arrivals with expected arrivals. `ours_v61_oldrise` keeps v6's rise test (ablation). | Same. | `catsim/rules_v61.py` | `tests/test_v61.py` (the counterexample; equal to v6 while nothing is dropped) |
| 3 | 14 Nov 2026 | **Wrapper `<rule>+adm61`.** The common rejection wrapper with the same corrected estimate, as the matched-admission rival of v6.1. | The old wrapper uses v6's estimate, so it has the same error. | `catsim/baselines.py` | `tests/test_v61.py` |

## Not changed

- `MODEL_VERSION` in `catsim/config.py`. Old rules behave exactly as before, so saved runs keep their file names.
- Every v6 rule, every baseline, every saved result.

## Known limits carried by v6.1 (until the phase named)

- **Overload threshold at 95%.** With the correct estimate, v6.1 is about 3.5 points lower than v6 at exactly 95% load (pilot seeds). Studied in Phase 2.
- **Capacity meter.** It measured a site one or two servers too low in 9 of 110 runs without any failure. Handled with the slow-recovery work (Batch C).
