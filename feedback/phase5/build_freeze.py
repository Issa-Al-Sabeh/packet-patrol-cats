"""Writes FREEZE_v6.1.md: the parameters of ours v6.1 read from the classes, the evaluation set read from
catsim/v61.py, the seeds used so far read from every result file, and the fingerprints of the code.

    python3 feedback/phase5/build_freeze.py
"""
import csv
import glob
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from catsim import v61                                                  # noqa: E402
from catsim.baselines import AdmissionWrapper61, StaticDeadline, resolve_rule   # noqa: E402
from catsim.config import MAIN                                           # noqa: E402
from catsim.v6 import PILOT_TESTS_V6                                     # noqa: E402

V61 = resolve_rule("ours_v61")
V6 = resolve_rule("ours_v6")

# ---- parameters: every upper-case class attribute of ours_v61, with the class that sets it
MEANING = {
    "DROP_FROM": "overload threshold: above this share of the measured capacity, dropping is allowed and the plan is "
                 "used without the balance rule",
    "ECHO_FRAC": "an ingress sends its drop count at most every W × this",
    "KAPPA": "None = the penalty formula κ = ρ ÷ (1 − ρ); a number would replace it (checks only)",
    "U_LIMIT": "no site is planned above this share of its measured capacity",
    "RHO_MAX": "cap on ρ in κ, so κ ≤ 19",
    "GAIN": "below overload, keep the plan only if it predicts this much fewer late frames than the capacity split",
    "DROP_COST": "a dropped frame costs one miss",
    "LATE_SAFE": "risk tolerance in the safe queue length",
    "CAL_MIN": "answers needed before dropping is allowed",
    "RISE_Z": "a rise beyond this many sd is taken at once",
    "EWMA": "weight of a new value in the offered-traffic estimate",
}
rows = []
for name in sorted(n for n in dir(V61) if n.isupper() and not n.startswith("_")):
    val = getattr(V61, name)
    if callable(val):
        continue
    owner = next(c.__name__ for c in V61.__mro__ if name in vars(c))
    old = getattr(V6, name, "(new)")
    mark = "" if old == val else f"**changed** (v6: {old})" if old != "(new)" else "**new**"
    if name == "DROP_FROM":
        mark = "**changed** (v6: 0.95, the site limit)"
    rows.append(f"| `{name}` | {val} | `{owner}` | {mark} | {MEANING.get(name, '')} |")
flags = [f"`{n}` = {getattr(V61, n)}" for n in ("uses_drop_echo", "like_rise", "use_balance", "use_burst", "cal_split",
                                                 "allow_drop", "no_age", "tie_drop")]

# ---- seeds used so far, from every result file of the repository
used, files = {}, 0
for f in sorted(glob.glob(os.path.join(ROOT, "**", "*.csv"), recursive=True)):
    with open(f) as fh:
        rd = csv.DictReader(fh)
        if not rd.fieldnames or "seed" not in rd.fieldnames:
            continue
        files += 1
        for r in rd:
            try:
                used.setdefault(int(float(r["seed"])), set()).add(os.path.relpath(f, ROOT))
            except ValueError:
                pass
assert used and max(used) <= 210, max(used)
assert not any(s in used for s in v61.EVAL_SEEDS)
eight_rules = set()
for f in ("feedback/phase1/diagnose.csv", "feedback/phase3/lsq.csv"):
    with open(os.path.join(ROOT, f)) as fh:
        for r in csv.DictReader(fh):
            if r.get("net", "eight") == "eight":
                eight_rules.add(r["rule"])
assert not any(r.startswith("ours_v61") or r.startswith("est_") for r in eight_rules), eight_rules


# ---- the evaluation set
def sc_rows(scs):
    out = []
    for net, sc in scs:
        note = "pilot scenario" if net == "beirut" and sc.key in PILOT_TESTS_V6 else ""
        out.append(f"| {NET[net]} | `{sc.key}` | {sc.label if net != 'eight' else eight_label(sc)} | {note} |")
    return "\n".join(out)


def eight_label(sc):
    import json
    m = json.loads(sc.factor)
    extra = "" if m["R"] == 4 else f", {m['R']} ingresses"
    return f"Load {int(round(m['load'] * 100))}%, {m['pattern']}, reports every {m['W']:g} s{extra}"


NET = {"beirut": "Beirut", "eight": "8 sites", "new": "New"}
A, B = v61.batch_a(), v61.batch_b()
n = v61.NEW_MAIN
cap = sum(n.servers) * n.mu
shares = [x / sum(range(1, n.ingresses + 1)) for x in range(n.ingresses, 0, -1)]

# ---- fingerprints
FILES = sorted(glob.glob(os.path.join(ROOT, "catsim", "*.py"))) + [os.path.join(ROOT, f) for f in (
    "study_config.json", "study_results/frozen_params.json", "tests/test_simulator.py", "tests/test_v61.py")]
fp = []
for f in FILES:
    with open(f, "rb") as fh:
        fp.append(f"| `{os.path.relpath(f, ROOT)}` | `{hashlib.sha256(fh.read()).hexdigest()}` |")

rep_path = os.path.join(HERE, "repro_at_freeze.csv")
if os.path.exists(rep_path):
    with open(rep_path) as fh:
        rep = list(csv.DictReader(fh))
    rep_txt = f"{sum(r['match'] == 'True' for r in rep)} of {len(rep)}"
else:
    rep_txt = "(not run yet)"

doc = f"""# v6.1 freeze

- **Frozen on 15 Nov 2026**, git tag `v6.1-frozen`, before any run on the evaluation seeds.
- **The frozen v6 stays what it was:** tag `v6-frozen`, described by `FREEZE.md`.
- **Rule from now on:** `ours_v61`, the wrapper `+adm61`, the static split, the simulator and the evaluation set below do not change. A later fix (Batch C) is a new version with its own note, designed on pilot seeds only and reported next to v6.1, not in its place.
- This file is written by `feedback/phase5/build_freeze.py` from the code and the result files.

## What is frozen

| Item | Where |
|---|---|
| The rule `ours_v61` | `catsim/rules_v61.py` (`SplitV61`), on top of `SplitV6` (`catsim/rules_v6.py`) |
| The matched-admission wrapper `<rule>+adm61` | `catsim/baselines.py` (`AdmissionWrapper61`) |
| The deadline-aware static split `static_deadline` | `catsim/baselines.py` (`StaticDeadline`), design load {StaticDeadline.DESIGN_LOAD} |
| The simulator with the drop counter | `catsim/engine.py`, `catsim/config.py` (`echo_bytes` = {MAIN.echo_bytes}) |
| The evaluation set: networks, scenarios, rules, seeds | `catsim/v61.py` |
| Every baseline of the v6 study, unchanged | `BASELINES.md`, `study_results/frozen_params.json` |

- Old results are untouched: {rep_txt} saved v6 runs, re-run on this code, match exactly (`feedback/phase5/repro_at_freeze.csv`).

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

Switches: {', '.join(flags)}.

| Parameter | Value | Set in | Against v6 | Meaning |
|---|---|---|---|---|
{chr(10).join(rows)}

- Parameters without a note are described in `FREEZE.md` (the v6 table) and `feedback/cost.md` (section 4).
- `+adm61`: admits up to {AdmissionWrapper61.U:g} of the configured capacity, with the estimate of change 1.

## Seeds

| Seeds | Role | Used so far by |
|---|---|---|
| 101 to 105 | pilot: every choice of v6 and of v6.1 | the pilots of Phases 1, 2 and 3 (Beirut only) |
| 201 to 210 | the final results of v6 | the v6 studies; since the v6 freeze: reproduction, the diagnosis of v6's estimate, the LSQ diagnostic |
| 301 to 310 | **evaluation of v6.1** | nothing |

- Checked on {files} result files: the largest seed in any of them is {max(used)}.
- One exception to "v6.1 never ran on 201 to 210": a unit test runs v6.1 on seed 201 in the main scenario, to check that it equals v6 while nothing is dropped.
- First pass: seeds {v61.FIRST_SEEDS[0]} to {v61.FIRST_SEEDS[-1]}. Seeds {v61.EVAL_SEEDS[5]} to {v61.EVAL_SEEDS[-1]} complete it to ten.

## Was the 8-site network used?

- **Yes, to diagnose. No, to choose.**
- Phase 1 measured the frozen v6 on it (seeds 201 to 205). It showed the largest estimate error we found (3.1 times the truth with reports every 0.5 s; `feedback/estimator.md`, section 3).
- Phase 3 diagnosed the LSQ baseline on it (same seeds).
- Rules run on it since the v6 freeze: {', '.join(f'`{r}`' for r in sorted(eight_rules))}. No version of v6.1.
- Every option and setting of v6.1 was chosen on Beirut with seeds 101 to 105.
- Still, we looked at where v6 was most wrong on it. By the rule of `FREEZE.md`, we no longer call it fully held out, and the evaluation uses a fresh set: new seeds everywhere, and a network that was never run.

## The evaluation set

**Networks**

| Network | Sites (GPUs) | Ingresses | Reports | Status |
|---|---|---|---|---|
| Beirut | 3 (2, 4, 8) | 4 | every 5 s | the design network; new seeds only |
| 8 sites | 8 (1, 2, 2, 3, 4, 5, 7, 8) | 4 | every 2 s | diagnosed, not designed on; new seeds |
| New | {len(n.servers)} ({', '.join(str(x) for x in n.servers)}) | {n.ingresses} | every {n.report_interval:g} s | **never run** |

**The new network** (`catsim/v61.py`)

| Site | {' | '.join(v61.NEW_SITE_NAMES)} |
|---|{'---|' * len(n.servers)}
| GPUs | {' | '.join(str(x) for x in n.servers)} |
| Round trip from Ingress A (ms) | {' | '.join(f'{x:g}' for x in n.base_delay_ms)} |

- {sum(n.servers)} GPUs, {cap:g} frames/s. Same application: {n.mu:g} frames/s per GPU, {n.deadline_ms:g} ms deadline.
- {n.ingresses} ingresses with shares {', '.join(f'{100 * s:.0f}%' for s in shares)}. Their round trips are up to {100 * n.delay_spread:.0f}% shorter or longer than Ingress A's.
- **Why this one:** the largest site is far. Its round trip is {100 * n.base_delay_ms[-1] / n.deadline_ms:.0f}% of the deadline (Beirut's farthest: {100 * MAIN.base_delay_ms[-1] / MAIN.deadline_ms:.0f}%), so sending by capacity alone is no longer free. This is where a deadline-aware rule and a capacity rule should differ.
- It was defined without running anything on it. One 30-second run on seed 1 checks that it executes; its results are not read.

**Batch A: where does the gain come from?** ({len(A)} scenarios × {len(v61.BATCH_A_RULES)} rules × 5 seeds = {len(v61.plan('A'))} runs)

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
{sc_rows(A)}

**Batch B: does the estimate hold when ingresses differ?** ({len(B)} scenarios × {len(v61.BATCH_B_RULES)} rules × 5 seeds = {len(v61.plan('B'))} runs)

| Rule | Run name |
|---|---|
{chr(10).join(f'| {lab} | `{r}` |' for r, lab in v61.BATCH_B_RULES)}

| Network | Scenario | What it is | |
|---|---|---|---|
{sc_rows(B)}

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
{chr(10).join(fp)}
"""
with open(os.path.join(ROOT, "FREEZE_v6.1.md"), "w") as f:
    f.write(doc)
print("FREEZE_v6.1.md written,", len(doc.splitlines()), "lines; seeds used:", min(used), "to", max(used), "in", files,
      "files; rules on the 8-site network:", sorted(eight_rules))
