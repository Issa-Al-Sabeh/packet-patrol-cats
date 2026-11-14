"""ONE COMMAND for the whole study.

    python run_all.py                 full study: checks, main scenario, sweeps, stress tests, real-life scenarios,
                                      held-out scenarios, ablations, report
    python run_all.py --quick         main scenario only, 2 seeds (under a minute) - to try the pipeline
    python run_all.py --pilot         first look at the new rules on SPARE seeds 101-105 (never used in the report)
    python run_all.py --workers 4     use 4 CPU cores (default: all but one, on machines with 4+ cores)
    python run_all.py --seeds 5       fewer seeds (default 10)
    python run_all.py --report-only   rebuild the report from the runs already on disk
    python run_all.py --fresh         delete earlier runs and start over

Every run is saved the moment it finishes (results/runs/). If the study is interrupted, run the same
command again: it continues where it stopped. The final result is results/report.html
(results/report_quick.html in quick mode), plus CSV tables and PNG charts in results/.
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


def main():
    ap = argparse.ArgumentParser(description="CATS site-selection study: every test, one command.")
    ap.add_argument("--quick", action="store_true", help="main scenario only, 2 seeds (under a minute)")
    ap.add_argument("--pilot", action="store_true",
                    help="first look at the new rules on spare seeds 101-105 (main + real-life scenarios); no report")
    ap.add_argument("--seeds", type=int, default=None, help="independent repetitions per test (default 10; quick: 2)")
    cpus = os.cpu_count() or 2
    ap.add_argument("--workers", type=int, default=cpus - 1 if cpus >= 4 else cpus,
                    help="CPU cores to use (default: all but one on 4+ cores)")
    ap.add_argument("--report-only", action="store_true", help="only rebuild the report from saved runs")
    ap.add_argument("--fresh", action="store_true", help="delete saved runs first")
    ap.add_argument("--out", default=os.path.join(HERE, "results"), help="output folder (default: results)")
    a = ap.parse_args()

    from catsim import experiments
    from catsim.checks import run_checks

    if a.pilot:
        return pilot(a, experiments)

    seeds = list(range(1, (a.seeds or (2 if a.quick else 10)) + 1))
    run_dir = os.path.join(a.out, "runs")
    if a.fresh and os.path.isdir(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir, exist_ok=True)
    t_start = time.time()
    steps = experiments.plan(seeds, quick=a.quick)
    n_total = len(steps) + 2
    print(f"CATS site-selection study - {'QUICK' if a.quick else 'FULL'} mode, {len(seeds)} seeds, "
          f"{a.workers} worker(s), {sum(len(t) for _, t in steps)} simulation runs")

    checks_file = os.path.join(a.out, "checks_quick.json" if a.quick else "checks.json")
    if not a.report_only or not os.path.exists(checks_file):
        print(f"\n[1/{n_total}] Built-in checks (simulator and formulas)")
        rows, detail = run_checks(quick=a.quick)
        with open(checks_file, "w") as f:
            json.dump({"rows": rows, "late_detail": detail}, f)

    for k, (name, tasks) in enumerate(steps, start=2):
        print(f"\n[{k}/{n_total}] {name}: {len(tasks)} runs")
        if a.report_only:
            print("    (skipped: --report-only)")
            continue
        experiments.execute(tasks, run_dir, a.workers)

    print(f"\n[{n_total}/{n_total}] Analysis, charts and report")
    if not any(f.endswith(".json") for f in os.listdir(run_dir)):
        print("    No saved runs yet: run the command without --report-only first.")
        return
    from catsim import report
    meta = dict(mode="quick" if a.quick else "full", seeds=len(seeds), workers=a.workers,
                python=platform.python_version(), machine=platform.platform(),
                wall_s=round(time.time() - t_start, 1), started=time.strftime("%Y-%m-%d %H:%M"))
    path = report.build(steps, run_dir, a.out, checks_file, meta)
    print(f"\nDone in {experiments.fmt_time(time.time() - t_start)}.  Open the final result:\n    {path}")


def pilot(a, experiments):
    """Runs the new rules (and the closest competitors) on spare seeds and prints a small table. These seeds are
    never used in the report, so looking at them cannot bias the final numbers."""
    import numpy as np
    from scipy import stats
    from catsim.config import LABELS, PILOT_RULES
    run_dir = os.path.join(a.out, "pilot", "runs")
    os.makedirs(run_dir, exist_ok=True)
    (name, tasks), = experiments.plan_pilot()
    print(f"{name}: {len(tasks)} runs, {a.workers} worker(s)")
    experiments.execute(tasks, run_dir, a.workers)
    res = {}
    for sc, r, sd in tasks:
        with open(experiments.run_path(run_dir, sc, r, sd)) as f:
            o = json.load(f)
        res.setdefault((sc.key, sc.label), {}).setdefault(r, []).append((o["miss"] * 100, o["p99_ms"]))
    lines = ["scenario,rule,miss_pct,ci95,p99_ms"]
    print()
    for (key, label), by_rule in res.items():
        print(label)
        for r in PILOT_RULES:
            xs = np.array([m for m, _ in by_rule[r]])
            h = stats.t.ppf(0.975, len(xs) - 1) * xs.std(ddof=1) / np.sqrt(len(xs)) if len(xs) > 1 else float("nan")
            p99 = np.mean([p for _, p in by_rule[r]])
            print(f"    {LABELS[r]:40s} {xs.mean():6.2f}% +/- {h:5.2f}   slowest 1%: {p99:8.0f} ms")
            lines.append(f"{key},{r},{xs.mean():.3f},{h:.3f},{p99:.0f}")
    out = os.path.join(a.out, "pilot", "pilot.csv")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSaved: {out}\n(Spare seeds only. The study itself: python run_all.py)")


if __name__ == "__main__":
    main()
