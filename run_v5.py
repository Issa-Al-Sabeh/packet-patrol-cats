"""ONE COMMAND for the v5 study: ours v5 against v2 + measured speeds, v4 and the rivals that may drop.

    python run_v5.py --pilot          STEP 1: first look on SPARE seeds 101-105 (never used in the report); prints a
                                      table and saves results_v5/pilot/pilot_v5.csv. Decide, then freeze v5.
    python run_v5.py                  STEP 2: the full study (61 tests, 10 seeds), then results_v5/report_v5.html
    python run_v5.py --quick          Beirut main scenario + load 130%, 2 seeds - to try the pipeline
    python run_v5.py --workers 4      use 4 CPU cores (default: all but one, on machines with 4+ cores)
    python run_v5.py --seeds 5        fewer seeds (default 10)
    python run_v5.py --report-only    rebuild the report from the runs already on disk
    python run_v5.py --no-reuse       do not copy matching runs saved by run_all.py / run_large.py

Every run is saved the moment it finishes (results_v5/runs/): if it is interrupted, run the same command again and
it continues. Runs of the old rules that run_all.py (results/runs) or run_large.py (results_large/runs_large)
already made are copied instead of re-run (same settings code = same run), after a sample of them is re-run here
and found identical. The main study and the large-network study are not changed.
"""
import argparse
import json
import os
import platform
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SAVED = [os.path.join(HERE, "results", "runs"), os.path.join(HERE, "results_large", "runs_large")]


def reuse(steps, run_dir, log=print):
    """Copy runs of the earlier studies that are exactly the runs planned here. Returns the copied paths."""
    from catsim.experiments import run_path
    copied = []
    for _, tasks in steps:
        for sc, r, sd in tasks:
            p = run_path(run_dir, sc, r, sd)
            if os.path.exists(p):
                continue
            for d in SAVED:
                q = os.path.join(d, os.path.basename(p))
                if os.path.exists(q):
                    shutil.copyfile(q, p)
                    copied.append((sc, r, sd, p))
                    break
    if copied:
        log(f"    copied {len(copied)} matching runs saved by the earlier studies")
    return copied


def reproduce(copied, log=print, n=10):
    """Re-run a sample of the copied runs (different rules and tests) with this code: every number must match."""
    from catsim.engine import run
    if not copied:
        log("    no saved runs to compare with (skipped)")
        return [("Saved runs of the earlier studies reproduce exactly", "none copied, nothing to compare", None)]
    import numpy as np
    order = np.random.default_rng(0).permutation(len(copied))      # a varied sample: every rule, many tests
    seen_r, seen_t, sample = set(), set(), []
    for i in order:
        sc, r, sd, p = copied[i]
        if r not in seen_r and sc.key not in seen_t:
            seen_r.add(r)
            seen_t.add(sc.key)
            sample.append(copied[i])
    for i in order:
        sc, r, sd, p = copied[i]
        if len(sample) < n and sc.key not in seen_t:
            seen_t.add(sc.key)
            sample.append(copied[i])
    sample = sample[:n]
    same = 0
    for sc, r, sd, p in sample:
        with open(p) as f:
            old = json.load(f)
        new = run(sc, r, sd, keep_series="series" in old)
        diff = [k for k in old if k != "runtime_s" and old[k] != new.get(k)]
        same += not diff
        log(f"    {sc.key:22s} {r:15s} seed {sd}: {'identical' if not diff else 'DIFFERENT: ' + ', '.join(diff)}")
    if same != len(sample):
        raise SystemExit("A saved run did not reproduce: stop. (Use --no-reuse to run everything with this code.)")
    return [("Saved runs of the earlier studies reproduce exactly (re-run here, every number compared)",
             f"{same} of {len(sample)} re-run; {len(copied)} copied", True)]


def main():
    ap = argparse.ArgumentParser(description="CATS site selection: the v5 study, one command.")
    ap.add_argument("--pilot", action="store_true", help="first look on spare seeds 101-105; no report")
    ap.add_argument("--quick", action="store_true", help="Beirut main scenario + load 130%%, 2 seeds")
    ap.add_argument("--seeds", type=int, default=None, help="repetitions per test (default 10; quick: 2)")
    cpus = os.cpu_count() or 2
    ap.add_argument("--workers", type=int, default=cpus - 1 if cpus >= 4 else cpus, help="CPU cores to use")
    ap.add_argument("--report-only", action="store_true", help="only rebuild the report from saved runs")
    ap.add_argument("--no-reuse", action="store_true", help="do not copy runs saved by the earlier studies")
    ap.add_argument("--out", default=os.path.join(HERE, "results_v5"), help="output folder (default: results_v5)")
    a = ap.parse_args()

    from catsim import experiments
    from catsim.v5 import plan_v5

    if a.pilot:
        return pilot(a, experiments)
    seeds = list(range(1, (a.seeds or (2 if a.quick else 10)) + 1))
    steps = plan_v5(seeds, quick=a.quick)
    run_dir = os.path.join(a.out, "runs")
    os.makedirs(run_dir, exist_ok=True)
    t0 = time.time()
    n = len(steps) + 2
    print(f"CATS v5 study - {'QUICK' if a.quick else 'FULL'} mode, {len(seeds)} seeds, {a.workers} worker(s), "
          f"{sum(len(t) for _, t in steps)} simulation runs")
    checks_file = os.path.join(a.out, "checks_v5_quick.json" if a.quick else "checks_v5.json")
    print(f"\n[1/{n}] Saved runs of the earlier studies: copy and check they reproduce")
    if a.report_only and os.path.exists(checks_file):
        print("    (skipped: --report-only)")
    else:
        copied = [] if a.no_reuse else reuse(steps, run_dir)
        rows = reproduce(copied)
        with open(checks_file, "w") as f:
            json.dump(rows, f)
    for k, (name, tasks) in enumerate(steps, start=2):
        print(f"\n[{k}/{n}] {name}: {len(tasks)} runs")
        if a.report_only:
            print("    (skipped: --report-only)")
            continue
        experiments.execute(tasks, run_dir, a.workers)
    print(f"\n[{n}/{n}] Analysis, charts and report")
    from catsim import v5_report
    extra = [tuple(x) for x in json.load(open(checks_file))] if os.path.exists(checks_file) else []
    meta = dict(seeds=len(seeds), python=platform.python_version(), started=time.strftime("%Y-%m-%d %H:%M"))
    path, st = v5_report.build(steps, run_dir, a.out, meta, extra)
    for what, res, ok in st.check_rows:
        print(f"    check: {what}: {res}{'' if ok else '   <-- CHECK'}")
    print(f"\nDone in {experiments.fmt_time(time.time() - t0)}.  Open the final result:\n    {path}")


def pilot(a, experiments):
    """The candidate versions of v5 and the closest rivals on SPARE seeds; prints a small table. These seeds are
    never used in the report, so looking at them cannot bias the final numbers."""
    import numpy as np
    from scipy import stats
    from catsim.v5 import PILOT_RULES_V5, SHORT_V5, plan_pilot_v5
    run_dir = os.path.join(a.out, "pilot", "runs")
    os.makedirs(run_dir, exist_ok=True)
    (name, tasks), = plan_pilot_v5()
    print(f"{name}: {len(tasks)} runs, {a.workers} worker(s)")
    experiments.execute(tasks, run_dir, a.workers)
    res = {}
    for sc, r, sd in tasks:
        with open(experiments.run_path(run_dir, sc, r, sd)) as f:
            o = json.load(f)
        res.setdefault((sc.key, sc.label), {}).setdefault(r, []).append(o)
    lines = ["test,rule,miss_pct,ci95,dropped_pct,discarded_pct,p99_ms"]
    print()
    for (key, label), by_rule in res.items():
        print(label)
        for r in PILOT_RULES_V5:
            outs = by_rule[r]
            xs = np.array([o["miss"] * 100 for o in outs])
            h = stats.t.ppf(0.975, len(xs) - 1) * xs.std(ddof=1) / np.sqrt(len(xs)) if len(xs) > 1 else float("nan")
            dr = np.mean([o.get("dropped", 0) for o in outs]) * 100
            dc = np.mean([o.get("discarded", 0) for o in outs]) * 100
            p99 = np.nanmean([o["p99_ms"] for o in outs])
            print(f"    {SHORT_V5[r]:20s} {xs.mean():6.2f}% +/- {h:5.2f}   dropped {dr:5.2f}%  discarded {dc:5.2f}%"
                  f"   slowest 1%: {p99:6.0f} ms")
            lines.append(f"{label.replace(',', ';')},{r},{xs.mean():.3f},{h:.3f},{dr:.3f},{dc:.3f},{p99:.0f}")
    out = os.path.join(a.out, "pilot", "pilot_v5.csv")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSaved: {out}\n(Spare seeds only. The study itself: python run_v5.py)")


if __name__ == "__main__":
    main()
