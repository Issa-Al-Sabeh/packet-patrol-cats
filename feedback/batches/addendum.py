"""Two baselines questioned by Batch A, settled on pilot seeds. ADDED AFTER THE FREEZE of 15 Nov 2026.

    python3 feedback/batches/addendum.py pilot     seeds 101-105 -> addendum_pilot.csv, addendum_settings.json
    python3 feedback/batches/addendum.py pilot2    seeds 101-105, second step (rule E) -> addendum_pilot2.csv
    python3 feedback/batches/addendum.py eval      seeds 301-305, only what the pilots chose -> batch_A_added.csv

Why (feedback/batches.md, first pass of Batch A):
  1. "Round-robin + matched admission" admits 95% of the configured capacity. Ours v6.1 admitted about 91% in steady
     overload and less in bursts. So part of v6.1's lead could be the admission level, not the steering.
  2. The frozen static split (design load 95%, site limit 95%) falls back to the capacity shares on every network, so
     it is round-robin again and not a separate baseline.

What is tried, and nothing else (no frozen file changes; both are parameters the frozen code already has):
  1. the wrapper at four admission levels:  wrr+adm61@U=u,  u in 0.80, 0.85, 0.90, 0.95 (0.95 = the frozen one);
  2. the static split at four design loads: static_deadline@DESIGN_LOAD=x+adm61, x in 0.70, 0.85, 0.90, 0.95
     (0.95 = the frozen one = capacity shares).
  Scenarios: the 22 scenarios of Batch A. Seeds: 101 to 105 (pilot). Ours v6.1 is not run here and is not looked at:
  each baseline is tuned for its own best result.

Rules of the choice, WRITTEN BEFORE ANY OF THESE RUNS:
  A. Admission level. One level for all networks: the level with the highest mean deadline success over the 22
     scenarios (mean of the scenario means, pilot seeds). If it is not 0.95, "round-robin + admission at that level"
     is added as a baseline. One level, as v6.1 has one setting.
  B. Static split. One design load per network (a static split is designed offline for its network): the design load
     with the highest mean deadline success over that network's Batch A scenarios (pilot seeds). Where it is 0.95, the
     frozen baseline is already the best of the family and nothing is added for that network.
  C. Ties go to the frozen value, then to the value nearest to it.
  D. Whatever is chosen is then run once on seeds 301 to 305, on all its scenarios, and reported next to the frozen
     baselines, marked "added after the freeze". Nothing is removed. The frozen comparison stays the primary one in
     the sense of the freeze; the report shows both.

Second step, WRITTEN ON 16 NOV 2026 AFTER RULES A TO D WERE APPLIED (level 0.90 chosen and run on seeds 301 to 305),
AND BEFORE ANY RUN WITH ANOTHER SMOOTHING:
  Why: with the level settled, v6.1 stays ahead in bursts and surges. But the wrapper smooths its estimate slowly
  (the newest report weighs EWMA = 0.3) and v6.1 follows a clear rise at once and checks for bursts between reports.
  So the lead in bursts could be the wrapper's slow smoothing, the same kind of doubt as the admission level.
  E. Smoothing of the wrapper. With the admission level fixed by rule A, the weight of the newest report among 0.3
     (the frozen one), 0.6 and 1.0 (no smoothing): the one with the highest mean pilot success over the 22 scenarios.
     If it is not 0.3, "round-robin + admission at that level and that smoothing" is added too and run once on seeds
     301 to 305 (rule D). Ties: rule C.
  This is the last parameter of the wrapper that bears on how much and how fast it drops. Nothing else is tuned.
"""
import argparse
import csv
import json
import os
import sys
import time
from multiprocessing import get_context

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import run_batches as rb                                                # noqa: E402

PILOT_SEEDS = (101, 102, 103, 104, 105)
U_LEVELS = (0.80, 0.85, 0.90, 0.95)
DESIGN_LOADS = (0.70, 0.85, 0.90, 0.95)
EWMAS = (0.3, 0.6, 1.0)
FROZEN_U, FROZEN_LOAD, FROZEN_EWMA = 0.95, 0.95, 0.3
SETTINGS = os.path.join(HERE, "addendum_settings.json")


def u_rule(u):
    return "wrr+adm61" if u == FROZEN_U else f"wrr+adm61@U={u:g}"


def ue_rule(u, e):
    """Round-robin + admission at level u, the newest report weighing e."""
    if e == FROZEN_EWMA:
        return u_rule(u)
    return f"wrr+adm61@EWMA={e:g}" if u == FROZEN_U else f"wrr+adm61@U={u:g},EWMA={e:g}"


def static_rule(x):
    return "static_deadline+adm61" if x == FROZEN_LOAD else f"static_deadline@DESIGN_LOAD={x:g}+adm61"


def run_jobs(tag, jobs, workers):
    """Run the missing jobs (resumable, as run_batches.py) and return the rows in the order of the jobs."""
    work_dir = os.path.join(HERE, "_work")
    os.makedirs(work_dir, exist_ok=True)
    journal = os.path.join(work_dir, f"addendum_{tag}.jsonl")
    done = rb.load_journal(journal)
    todo = [j for j in jobs if rb.key_of(j) not in done]
    print(f"{tag}: {len(jobs)} runs, {len(jobs) - len(todo)} already done, {len(todo)} to run", flush=True)
    t0 = time.time()
    if todo:
        with open(journal, "a", encoding="utf-8") as jf, get_context("spawn").Pool(workers) as pool:
            for k, (row, detail) in enumerate(pool.imap_unordered(rb.work, todo, chunksize=1), 1):
                rec = {"key": detail["key"], "row": row, "detail": detail}
                jf.write(json.dumps(rec, default=rb._json_default) + "\n")
                jf.flush()
                done[rec["key"]] = rec
                if k % 50 == 0 or k == len(todo):
                    print(f"  {k}/{len(todo)}  {time.time() - t0:.0f} s", flush=True)
    return [done[rb.key_of(j)]["row"] for j in jobs], [done[rb.key_of(j)]["detail"] for j in jobs]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _pick(means, frozen):
    """The value with the highest mean; ties to the frozen value, then to the value nearest to it (rule C)."""
    best = max(means.values())
    tied = [k for k, v in means.items() if v == best]
    return min(tied, key=lambda k: (k != frozen, abs(k - frozen)))


def choose(rows):
    """Rules A, B and C of the docstring, applied to the pilot rows."""
    import numpy as np
    import pandas as pd
    df = pd.DataFrame(rows)
    sc_mean = df.groupby(["net", "scenario", "rule"]).success.mean()
    nets = list(dict.fromkeys(df.net))

    def mean_over(rule, net=None):
        m = sc_mean.xs(rule, level="rule")
        if net is not None:
            m = m.xs(net, level="net")
        return float(m.mean())

    def paired_vs(rule, ref, net=None):                       # mean difference by seed, pooled over the scenarios
        d = df[df.rule.isin([rule, ref])]
        if net is not None:
            d = d[d.net == net]
        p = d.pivot_table(index=["net", "scenario", "seed"], columns="rule", values="success")
        by_seed = (p[rule] - p[ref]).groupby("seed").mean().to_numpy()
        from scipy import stats
        half = float(stats.t.ppf(0.975, len(by_seed) - 1) * by_seed.std(ddof=1) / np.sqrt(len(by_seed)))
        return float(by_seed.mean()), half

    u_means = {u: mean_over(u_rule(u)) for u in U_LEVELS}
    u_best = _pick(u_means, FROZEN_U)
    out = dict(seeds=list(PILOT_SEEDS), scenarios=int(sc_mean.index.droplevel("rule").nunique()),
               admission=dict(levels={f"{u:g}": u_means[u] for u in U_LEVELS},
                              by_network={n: {f"{u:g}": mean_over(u_rule(u), n) for u in U_LEVELS} for n in nets},
                              chosen=u_best, rule=u_rule(u_best), added=u_best != FROZEN_U),
               static={})
    if u_best != FROZEN_U:
        m, h = paired_vs(u_rule(u_best), u_rule(FROZEN_U))
        out["admission"]["chosen_minus_frozen"] = dict(mean=m, half=h)
    for n in nets:
        s_means = {x: mean_over(static_rule(x), n) for x in DESIGN_LOADS}
        x_best = _pick(s_means, FROZEN_LOAD)
        entry = dict(loads={f"{x:g}": s_means[x] for x in DESIGN_LOADS}, chosen=x_best, rule=static_rule(x_best),
                     added=x_best != FROZEN_LOAD)
        if x_best != FROZEN_LOAD:
            m, h = paired_vs(static_rule(x_best), static_rule(FROZEN_LOAD), n)
            entry["chosen_minus_frozen"] = dict(mean=m, half=h)
        out["static"][n] = entry
    return out


def pilot(workers):
    from catsim import v61
    n, changed, _ = rb.check_frozen()
    if changed:
        raise SystemExit("frozen files differ from FREEZE_v6.1.md: " + ", ".join(changed))
    rules = [u_rule(u) for u in U_LEVELS] + [static_rule(x) for x in DESIGN_LOADS]
    jobs = [("P", net, sc, rule, sd) for net, sc in v61.batch_a() for rule in rules for sd in PILOT_SEEDS]
    rows, _ = run_jobs("pilot", jobs, workers)
    write_csv(os.path.join(HERE, "addendum_pilot.csv"), rows)
    settings = choose(rows)
    settings["rules_of_the_choice"] = "docstring of feedback/batches/addendum.py (A, B, C), fixed before the pilot runs"
    settings["chosen_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=1)
    print(json.dumps(settings, indent=1))


def pilot2(workers):
    """Rule E: the smoothing of the wrapper, at the admission level already chosen by rule A."""
    import pandas as pd
    from catsim import v61
    n, changed, _ = rb.check_frozen()
    if changed:
        raise SystemExit("frozen files differ from FREEZE_v6.1.md: " + ", ".join(changed))
    with open(SETTINGS, encoding="utf-8") as f:
        st = json.load(f)
    u = st["admission"]["chosen"]
    rules = [ue_rule(u, e) for e in EWMAS if e != FROZEN_EWMA]
    jobs = [("P", net, sc, rule, sd) for net, sc in v61.batch_a() for rule in rules for sd in PILOT_SEEDS]
    rows, _ = run_jobs("pilot2", jobs, workers)
    write_csv(os.path.join(HERE, "addendum_pilot2.csv"), rows)
    first = pd.read_csv(os.path.join(HERE, "addendum_pilot.csv"), float_precision="round_trip")
    df = pd.concat([first[first.rule == u_rule(u)], pd.DataFrame(rows)], ignore_index=True)
    sc_mean = df.groupby(["net", "scenario", "rule"]).success.mean()
    nets = list(dict.fromkeys(df.net))
    means = {e: float(sc_mean.xs(ue_rule(u, e), level="rule").mean()) for e in EWMAS}
    e_best = _pick(means, FROZEN_EWMA)
    st["smoothing"] = dict(
        at_level=u, weights={f"{e:g}": means[e] for e in EWMAS},
        by_network={n: {f"{e:g}": float(sc_mean.xs(ue_rule(u, e), level="rule").xs(n, level="net").mean())
                        for e in EWMAS} for n in nets},
        chosen=e_best, rule=ue_rule(u, e_best), added=e_best != FROZEN_EWMA,
        chosen_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)
    print(json.dumps(st["smoothing"], indent=1))


def evaluate(workers, seeds):
    from catsim import v61
    n, changed, _ = rb.check_frozen()
    if changed:
        raise SystemExit("frozen files differ from FREEZE_v6.1.md: " + ", ".join(changed))
    bad = [s for s in seeds if s not in v61.EVAL_SEEDS]
    if bad:
        raise SystemExit(f"seeds {bad} are not evaluation seeds")
    if not os.path.exists(SETTINGS):
        raise SystemExit("run the pilot first: the rules to run come from addendum_settings.json")
    with open(SETTINGS, encoding="utf-8") as f:
        st = json.load(f)
    jobs = []
    for net, sc in v61.batch_a():
        if st["admission"]["added"]:
            jobs += [("A+", net, sc, st["admission"]["rule"], sd) for sd in seeds]
        if st["static"][net]["added"]:
            jobs += [("A+", net, sc, st["static"][net]["rule"], sd) for sd in seeds]
        if st.get("smoothing", {}).get("added"):
            jobs += [("A+", net, sc, st["smoothing"]["rule"], sd) for sd in seeds]
    if not jobs:
        print("the pilot chose the frozen values everywhere: nothing to run")
        return
    rows, details = run_jobs("eval", jobs, workers)
    write_csv(os.path.join(HERE, "batch_A_added.csv"), rows)
    import gzip
    with gzip.open(os.path.join(HERE, "batch_A_added_detail.jsonl.gz"), "wt", encoding="utf-8") as f:
        for d in details:
            f.write(json.dumps(d, default=rb._json_default) + "\n")
    print(f"{len(rows)} runs -> feedback/batches/batch_A_added.csv; rules: {sorted({r['rule'] for r in rows})}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["pilot", "pilot2", "eval"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--seeds", default="301-305")
    a = ap.parse_args()
    if a.what == "pilot":
        pilot(a.workers)
    elif a.what == "pilot2":
        pilot2(a.workers)
    else:
        evaluate(a.workers, rb.parse_seeds(a.seeds))


if __name__ == "__main__":
    main()
