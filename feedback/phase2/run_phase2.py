"""Phase 2 measurements (feedback of 11 Nov 2026: the cost and the planner of ours v6.1).

    python3 run_phase2.py sens   [--workers N]   one-at-a-time sensitivity of the caps and of the backlog penalty -> sens.csv
    python3 run_phase2.py greedy [--workers N]   the greedy plan against the best plan on the same grid          -> greedy.csv
    python3 run_phase2.py planner [--workers N]  ours v6.1 run with the best plan on the grid instead of greedy  -> planner.csv
    python3 run_phase2.py final  [--workers N]   the penalty and planner checks again, at the frozen threshold   -> sens_final.csv

Runs: pilot seeds 101-105 only, Beirut network only. Scenarios: the 11 pilot tests of v6, the 5 development scenarios
of Phase 1 and, for the greedy check, two 2-site instances. The held-out tests, the large network and the 8-site
network take no part.
"""
import argparse
import csv
import os
import sys
import time
from dataclasses import replace
from multiprocessing import get_context

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "phase1"))
sys.path.insert(0, HERE)

SEEDS = (101, 102, 103, 104, 105)
# Every rule string pins the drop threshold: these runs describe v6.1 as it was during Phase 2 (dropping from 95%,
# as in v6). The default of ours_v61 became 90% afterwards, as a result of this check.
P2 = "DROP_FROM=0.95"
VARIANTS = [                                   # (label, rule string); every one differs from the base in ONE setting
    ("base", f"ours_v61@{P2}"),
    ("penalty cap 0.90", f"ours_v61@RHO_MAX=0.9,{P2}"),          # kappa <= 9
    ("penalty cap 0.98", f"ours_v61@RHO_MAX=0.98,{P2}"),         # kappa <= 49
    ("no penalty", f"ours_v61@KAPPA=0,{P2}"),
    ("constant penalty 5", f"ours_v61@KAPPA=5,{P2}"),
    ("constant penalty 19", f"ours_v61@KAPPA=19,{P2}"),
    ("drop from 85%", "ours_v61@DROP_FROM=0.85"),
    ("drop from 90%", "ours_v61@DROP_FROM=0.9"),
    ("limit 90%", "ours_v61@U_LIMIT=0.9,DROP_FROM=0.9"),         # site limit and drop threshold together
    ("limit 100%", "ours_v61@U_LIMIT=1.0,DROP_FROM=1.0"),
    ("v6 (frozen)", "ours_v6"),
]

# The same checks around v6.1 as frozen (dropping from 90%), to confirm that the conclusions on the penalty and on
# the planner still hold after the threshold was moved.
F = "DROP_FROM=0.9"
VARIANTS_FINAL = [
    ("v6.1 (frozen)", f"ours_v61@{F}"),
    ("penalty cap 0.90", f"ours_v61@RHO_MAX=0.9,{F}"),
    ("penalty cap 0.98", f"ours_v61@RHO_MAX=0.98,{F}"),
    ("no penalty", f"ours_v61@KAPPA=0,{F}"),
    ("constant penalty 19", f"ours_v61@KAPPA=19,{F}"),
    ("best plan on the grid", f"ours_v61_gridopt@{F}"),
]


def scenarios(two_sites=False):
    import run_phase1 as p1
    from catsim.config import MAIN
    from catsim.v5 import build_overload
    from catsim.v6 import PILOT_TESTS_V6, beirut_tests
    pool = {sc.key: sc for sc in beirut_tests() + build_overload()[0]}
    out = [("pilot", pool[k]) for k in PILOT_TESTS_V6] + [x for x in p1.scenarios_pilot() if x[0] == "dev"]
    if two_sites:
        two = replace(MAIN, group="dev", servers=(4, 8), base_delay_ms=(16.0, 60.0), site_discard=True)
        out += [("dev2", replace(two, key="dev2_85", label="Dev, 2 sites (4 and 8 servers): load 85%", load=0.85)),
                ("dev2", replace(two, key="dev2_115", label="Dev, 2 sites (4 and 8 servers): load 115%", load=1.15))]
    return out


def sens_job(job):
    net, sc, label, rule, seed = job
    import planner_opt  # noqa: F401  (registers ours_v61_gridopt)
    from catsim.engine import run
    o = run(sc, rule, seed)
    return dict(net=net, scenario=sc.key, label=sc.label, variant=label, rule=rule, seed=seed,
                success=o["success"] * 100, rejected=o["rejected"] * 100, expired=o["expired"] * 100,
                late=o["late_completed"] * 100, runtime_s=o["runtime_s"])


def minplus(a, b):
    """c[n] = min over i + j = n of a[i] + b[j]: the best split of n pieces between two groups of sites."""
    n = len(a)
    out = np.full(n, np.inf)
    for i in range(n):
        if np.isfinite(a[i]):
            out[i:] = np.minimum(out[i:], a[i] + b[:n - i])
    return out


def check_plan(tr, N=100):
    """Greedy plan of one _plan call against the best plan on the same grid of N pieces (exact: every split is
    covered by the min-plus recursion). Returns None for plans that used the 'every site is full' fallback."""
    step, S = tr["step"], len(tr["levels"])
    x = np.arange(N + 1) * step
    C, convex, capped = [], True, False
    for s in range(S):
        lv, c = tr["levels"][s], tr["sel_c"][s]
        v = np.where(x <= lv[-1], np.interp(x, lv, c), c[-1] + tr["slope"] * (x - lv[-1]))
        ok = x <= tr["limit"][s] + 1e-9
        fin = v[ok]
        if len(fin) >= 3:
            d2 = np.diff(fin, 2)
            if (d2 < -1e-7 * max(1.0, float(np.abs(fin).max()))).any():
                convex = False
                if (tr["ks"] * tr["risks"][s][lv <= tr["limit"][s] + 1e-9] >= 1.0).any():
                    capped = True
        v = v.copy()
        v[~ok] = np.inf
        C.append(v)
    kg = np.rint(tr["lam"] / step).astype(int)
    dg = int(round(tr["drop"] / step))
    if kg.sum() + dg != N or (kg * step > tr["limit"] + 1e-6).any():
        return None
    greedy = float(sum(C[s][kg[s]] for s in range(S))) + dg * step
    best = C[0]
    for s in range(1, S):
        best = minplus(best, C[s])
    opt = float(np.min(best[::-1] + np.arange(N + 1) * step)) if tr["may_drop"] else float(best[N])
    if not np.isfinite(opt):
        return None
    return dict(gap=max(0.0, greedy - opt), opt=opt, total=tr["total"], convex=convex, capped=capped,
                may_drop=bool(tr["may_drop"]), same=bool(tr["may_drop"] is False or all(
                    np.array_equal(a, b) for a, b in zip(tr["sel_c"], tr["cal_c"]))))


def greedy_job(job):
    net, sc, seed = job
    from catsim.baselines import resolve_rule
    from catsim.engine import run
    from catsim.rules import RULE_CLASSES
    base = resolve_rule(f"ours_v61@{P2}")
    res = []

    class Traced(base):
        def __init__(self, ctx, i):
            super().__init__(ctx, i)
            self.trace = lambda tr: res.append(check_plan(tr))
    name = f"_traced_v61_{sc.key}_{seed}"                         # a fresh name: resolved rule classes are cached
    RULE_CLASSES[name] = Traced
    o = run(sc, name, seed)
    ok = [r for r in res if r is not None]
    if not ok:                                                    # no plan on the grid (every plan used the fallback)
        return dict(net=net, scenario=sc.key, label=sc.label, sites=len(sc.servers), seed=seed,
                    success=o["success"] * 100, plans=len(res), fallback=len(res), compared=0, plans_may_drop=0,
                    optimal=0, nonconvex=0, nonconvex_cap=0, nonconvex_and_gap=0, convex_and_gap=0, gap_max_pts=0.0,
                    gap_mean_pts=0.0, gap_max_frames=0.0, gap_max_rel_opt=0.0, curves_differ=0)
    gap = np.array([r["gap"] for r in ok])
    rel_tr = gap / np.array([r["total"] for r in ok])            # extra predicted misses, as a share of the traffic
    rel_opt = gap / np.maximum(np.array([r["opt"] for r in ok]), 1e-9)
    tol = 1e-9 * np.maximum(1.0, np.array([r["opt"] for r in ok]))
    drop = np.array([r["may_drop"] for r in ok])
    return dict(net=net, scenario=sc.key, label=sc.label, sites=len(sc.servers), seed=seed, success=o["success"] * 100,
                plans=len(res), fallback=len(res) - len(ok), compared=len(ok), plans_may_drop=int(drop.sum()),
                optimal=int((gap <= tol).sum()), nonconvex=int(sum(not r["convex"] for r in ok)),
                nonconvex_cap=int(sum((not r["convex"]) and r["capped"] for r in ok)),
                nonconvex_and_gap=int(sum((not r["convex"]) and g > t for r, g, t in zip(ok, gap, tol))),
                convex_and_gap=int(sum(r["convex"] and g > t for r, g, t in zip(ok, gap, tol))),
                gap_max_pts=float(rel_tr.max() * 100), gap_mean_pts=float(rel_tr.mean() * 100),
                gap_max_frames=float(gap.max()), gap_max_rel_opt=float(rel_opt[gap > tol].max()) if (gap > tol).any() else 0.0,
                curves_differ=int(sum(not r["same"] for r in ok)))


def execute(fn, jobs, path, workers, key):
    t0, rows = time.time(), []
    with get_context("spawn").Pool(workers) as pool:
        for k, r in enumerate(pool.imap_unordered(fn, jobs, chunksize=1), 1):
            rows.append(r)
            if k % 50 == 0 or k == len(jobs):
                print(f"  {k}/{len(jobs)}  {time.time() - t0:.0f} s", flush=True)
    rows.sort(key=key)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} runs -> {os.path.relpath(path, ROOT)}  ({time.time() - t0:.0f} s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["sens", "greedy", "planner", "final"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    if a.what == "sens":
        order = {lab: k for k, (lab, _) in enumerate(VARIANTS)}
        jobs = [(net, sc, lab, rule, sd) for net, sc in scenarios() for lab, rule in VARIANTS for sd in SEEDS]
        return execute(sens_job, jobs, os.path.join(HERE, "sens.csv"), a.workers,
                       lambda r: (r["net"], r["scenario"], order[r["variant"]], r["seed"]))
    if a.what == "final":
        order = {lab: k for k, (lab, _) in enumerate(VARIANTS_FINAL)}
        jobs = [(net, sc, lab, rule, sd) for net, sc in scenarios() for lab, rule in VARIANTS_FINAL for sd in SEEDS]
        return execute(sens_job, jobs, os.path.join(HERE, "sens_final.csv"), a.workers,
                       lambda r: (r["net"], r["scenario"], order[r["variant"]], r["seed"]))
    if a.what == "planner":
        jobs = [(net, sc, "best plan on the grid", f"ours_v61_gridopt@{P2}", sd) for net, sc in scenarios(two_sites=True)
                for sd in SEEDS] + [(net, sc, "base", f"ours_v61@{P2}", sd) for net, sc in scenarios(two_sites=True)
                                    if net == "dev2" for sd in SEEDS]
        return execute(sens_job, jobs, os.path.join(HERE, "planner.csv"), a.workers,
                       lambda r: (r["net"], r["scenario"], r["variant"], r["seed"]))
    jobs = [(net, sc, sd) for net, sc in scenarios(two_sites=True) for sd in SEEDS]
    execute(greedy_job, jobs, os.path.join(HERE, "greedy.csv"), a.workers, lambda r: (r["net"], r["scenario"], r["seed"]))


if __name__ == "__main__":
    main()
