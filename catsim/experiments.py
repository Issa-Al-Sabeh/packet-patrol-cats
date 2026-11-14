"""Runs the simulations of the study in parallel and keeps every result on disk.

Each run (scenario, rule, seed) is saved as results/runs/<scenario>__<rule>__s<seed>__<settings>.json the
moment it finishes, so an interrupted study simply continues where it stopped. <settings> is a short code of
every setting of that scenario: change a number in config.py and the affected runs are redone automatically.
After changing the CODE of a rule, use --fresh (or bump MODEL_VERSION in config.py).
"""
import hashlib
import json
import os
import re
import time
from multiprocessing import get_context

from .config import (ABLATIONS, MODEL_VERSION, PILOT_EXTRA, PILOT_RULES, PILOT_SEEDS, RULES, build_held_out,
                     build_real_life, build_scenarios)
from .engine import run

# rough seconds of work per simulated second at 100 frames/s (for ordering the work and the time estimate)
COST = {"ours": 1.4, "expected_delay": 1.0, "ours_no_counting": 1.0, "ours_no_ageing": 0.4,
        "ours_exp_late": 1.3, "ours_no_ties": 1.0, "liyanage": 0.8, "wpow2_stale": 0.5,
        "ours_v2": 0.5, "ours_v2_check": 0.55, "ours_v2_speed": 0.6,
        # v5 study
        "ours_v5": 0.65, "ours_v5_raw": 0.6, "expected_delay_drop": 1.0, "v4": 0.35, "v4_nodrop": 0.35}


def file_key(key):
    return re.sub(r"[^A-Za-z0-9.=_-]+", "_", key).strip("_")


def settings_code(sc):
    return hashlib.sha1(repr((MODEL_VERSION, sc.physics())).encode()).hexdigest()[:8]


def run_path(run_dir, sc, rule, seed):
    return os.path.join(run_dir, f"{file_key(sc.key)}__{rule}__s{seed}__{settings_code(sc)}.json")


def cost(sc, rule):
    rate = sc.load * sum(sc.servers) * sc.mu
    if sc.load_jump_to > 0:
        rate = (sc.load + sc.load_jump_to) / 2 * sum(sc.servers) * sc.mu
    per_report = 5.0 / sc.report_interval if rule.startswith(("ours_v2", "ours_v5")) else 1.0   # plans per report
    return sc.duration() * rate / 100.0 * COST.get(rule, 0.15) * (1 + 0.02 * sc.ingresses) * max(1.0, per_report ** 0.5)


def plan(seeds, quick=False):
    """The study as an ordered list of steps: (step name, [(scenario, rule, seed), ...])."""
    main, sweeps, stress = build_scenarios()
    real = build_real_life(main)
    seen = set()

    def tasks(scs, rules):
        out = []
        for sc in scs:
            for r in rules:
                for sd in seeds:
                    k = (sc.key, r, sd)
                    if k not in seen:
                        seen.add(k)
                        out.append((sc, r, sd))
        return out

    steps = [("Main scenario (Beirut): all rules", tasks([main], RULES))]
    if quick:
        steps.append(("Ablations of our rule (main scenario)", tasks([main], ABLATIONS)))
        return steps
    sweep_scs = [sc for _, (_, _, pts) in sweeps.items() for sc in pts]
    steps.append(("Sweeps: one factor at a time", tasks(sweep_scs, RULES)))
    steps.append(("Stress tests", tasks(stress, RULES)))
    steps.append(("Real-life scenarios", tasks(real, RULES)))
    steps.append(("Held-out scenarios (never used to design or tune a rule)", tasks(build_held_out(main), RULES)))
    steps.append(("Ablations of ours v1 (for every report interval)",
                  tasks(sweeps["report_interval"][2], ABLATIONS)))
    return steps


def plan_pilot():
    """A first look at the new rules on SPARE seeds (101-105), never used in the report. Main scenario, the
    real-life scenarios and a few settings where measuring speeds is hardest; never the held-out scenarios."""
    main, sweeps, stress = build_scenarios()
    pool = {sc.key: sc for _, (_, _, pts) in sweeps.items() for sc in pts}
    pool.update({sc.key: sc for sc in stress})
    scs = [main] + build_real_life(main) + [pool[k] for k in PILOT_EXTRA if k in pool]
    return [("Pilot: new rules on spare seeds 101-105 (not used in the report)",
             [(sc, r, sd) for sc in scs for r in PILOT_RULES for sd in PILOT_SEEDS])]


def _work(args):
    sc, rule, seed, path = args
    out = run(sc, rule, seed, keep_series=(sc.key == "main" and seed == 1))
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(out, f)
    os.replace(tmp, path)
    return path


def fmt_time(s):
    s = int(s)
    return f"{s // 3600}h{s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}m{s % 60:02d}s"


def execute(task_list, run_dir, workers, log=print):
    """Run the tasks that are not on disk yet. Heaviest first, so the workers finish together."""
    os.makedirs(run_dir, exist_ok=True)
    todo = [(sc, r, sd, run_path(run_dir, sc, r, sd)) for sc, r, sd in task_list]
    todo = [t for t in todo if not os.path.exists(t[3])]
    done_before = len(task_list) - len(todo)
    if not todo:
        log(f"    all {len(task_list)} runs already on disk")
        return
    if done_before:
        log(f"    {done_before} of {len(task_list)} runs already on disk; running the other {len(todo)}")
    todo.sort(key=lambda t: -cost(t[0], t[1]))
    total = sum(cost(t[0], t[1]) for t in todo)
    costs = {t[3]: cost(t[0], t[1]) for t in todo}
    t0 = time.time()
    done_cost, n_done, last = 0.0, 0, 0.0
    ctx = get_context("spawn")
    with ctx.Pool(workers) as pool:
        for path in pool.imap_unordered(_work, todo, chunksize=1):
            n_done += 1
            done_cost += costs[path]
            el = time.time() - t0
            if el - last > 20 or n_done == len(todo):
                last = el
                eta = el / max(done_cost, 1e-9) * (total - done_cost)
                log(f"    {n_done}/{len(todo)} runs  ({done_cost / total:4.0%})  elapsed {fmt_time(el)}"
                    f"  about {fmt_time(eta)} left")
