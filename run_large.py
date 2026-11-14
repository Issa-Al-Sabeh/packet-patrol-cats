"""ONE COMMAND for the large-network study (6 sites, 12 ingresses).

    python run_large.py                 every test of the large network, 10 seeds, then the report
    python run_large.py --quick         main scenario only, 2 seeds - to try the pipeline
    python run_large.py --workers 4     use 4 CPU cores (default: all but one, on machines with 4+ cores)
    python run_large.py --seeds 5       fewer seeds (default 10)
    python run_large.py --report-only   rebuild the report from the runs already on disk

Every run is saved the moment it finishes (results_large/runs_large/): if it is interrupted, run the same command
again and it continues. The final result is results_large/report_large.html. The rules are the ones of the main
study, unchanged; the main study (run_all.py) is not touched.
"""
import argparse
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    ap = argparse.ArgumentParser(description="CATS site selection: the large network (6 sites, 12 ingresses).")
    ap.add_argument("--quick", action="store_true", help="main scenario only, 2 seeds")
    ap.add_argument("--seeds", type=int, default=None, help="repetitions per test (default 10; quick: 2)")
    cpus = os.cpu_count() or 2
    ap.add_argument("--workers", type=int, default=cpus - 1 if cpus >= 4 else cpus, help="CPU cores to use")
    ap.add_argument("--report-only", action="store_true", help="only rebuild the report from saved runs")
    ap.add_argument("--out", default=os.path.join(HERE, "results_large"), help="output folder")
    a = ap.parse_args()

    from catsim import experiments
    from catsim.large import plan_large

    seeds = list(range(1, (a.seeds or (2 if a.quick else 10)) + 1))
    steps = plan_large(seeds)
    if a.quick:
        steps = steps[:1]
    run_dir = os.path.join(a.out, "runs_large")
    os.makedirs(run_dir, exist_ok=True)
    t0 = time.time()
    n = len(steps) + 1
    print(f"CATS large network - {len(seeds)} seeds, {a.workers} worker(s), {sum(len(t) for _, t in steps)} runs")
    for k, (name, tasks) in enumerate(steps, start=1):
        print(f"\n[{k}/{n}] {name}: {len(tasks)} runs")
        if a.report_only:
            print("    (skipped: --report-only)")
            continue
        experiments.execute(tasks, run_dir, a.workers)
    print(f"\n[{n}/{n}] Analysis, charts and report")
    from catsim import large_report
    meta = dict(seeds=len(seeds), python=platform.python_version(), started=time.strftime("%Y-%m-%d %H:%M"))
    path = large_report.build(steps, run_dir, a.out, meta)
    print(f"\nDone in {experiments.fmt_time(time.time() - t0)}.  Open the final result:\n    {path}")


if __name__ == "__main__":
    main()
