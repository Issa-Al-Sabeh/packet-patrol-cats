"""ONE COMMAND for the v6 study.

    python run_v6.py --pilot      STEP 1: candidate thresholds on spare seeds 101-105; prints the decision
    python run_v6.py              STEP 2: the full study on fresh seeds 201-210 (every rule re-run), then the tables
    python run_v6.py --tables     rebuild the tables from the saved runs

Every run is saved the moment it finishes (results_v6/runs/); run the same command again to continue.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(tasks, run_dir):
    from catsim.experiments import run_path
    out = {}
    for sc, r, sd in tasks:
        p = run_path(run_dir, sc, r, sd)
        if os.path.exists(p):
            with open(p) as f:
                out[(sc, r, sd)] = json.load(f)
    return out


def pilot(workers):
    import numpy as np
    from scipy import stats
    from catsim import experiments
    from catsim.v6 import PILOT_GAINS, PILOT_RULES_V6, SHORT_V6, plan_pilot_v6
    run_dir = os.path.join(HERE, "results_v6", "pilot", "runs")
    (name, tasks), = plan_pilot_v6()
    print(f"{name}: {len(tasks)} runs")
    experiments.execute(tasks, run_dir, workers)
    runs = load(tasks, run_dir)
    tests = []
    for sc, _, _ in tasks:
        if sc not in tests:
            tests.append(sc)
    seeds = sorted({sd for _, _, sd in tasks})
    miss = {(sc.key, r): np.array([runs[(sc, r, sd)]["miss"] * 100 for sd in seeds]) for sc in tests
            for r in PILOT_RULES_V6}
    lines = ["test," + ",".join(PILOT_RULES_V6)]
    regret = {g: [] for g in PILOT_GAINS}
    for sc in tests:
        row = [f"{miss[(sc.key, r)].mean():.3f}" for r in PILOT_RULES_V6]
        lines.append(f"{sc.key}," + ",".join(row))
        best = min(miss[(sc.key, g)].mean() for g in PILOT_GAINS)
        for g in PILOT_GAINS:
            regret[g].append(miss[(sc.key, g)].mean() - best)
        print(f"  {sc.key:22s} " + "  ".join(f"{SHORT_V6[r]} {miss[(sc.key, r)].mean():6.2f}" for r in PILOT_RULES_V6))
    avg = {g: float(np.mean(v)) for g, v in regret.items()}
    print("\n  average regret: " + ", ".join(f"{SHORT_V6[g]} {v:.3f}" for g, v in avg.items()))
    low = min(avg.values())
    chosen = max((g for g in PILOT_GAINS if avg[g] <= low + 0.01), key=PILOT_GAINS.index)   # larger G on a tie
    print(f"  decision rule 1 -> {SHORT_V6[chosen]}")
    flags = []
    for sc in tests:
        for rival in ("ours_v5", "wrr_speed"):
            d = miss[(sc.key, chosen)] - miss[(sc.key, rival)]
            h = stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d))
            if d.mean() - h > 0:
                flags.append(f"{sc.key}: clearly worse than {SHORT_V6[rival]} ({d.mean():+.2f} +/- {h:.2f} pts)")
    print("  decision rule 2 -> " + ("; ".join(flags) if flags else "never clearly worse than v5 or RR + speeds"))
    os.makedirs(os.path.join(HERE, "results_v6", "pilot"), exist_ok=True)
    with open(os.path.join(HERE, "results_v6", "pilot", "pilot_v6.csv"), "w") as f:
        f.write("\n".join(lines) + "\n")
        f.write("average_regret," + ",".join(f"{g}={v:.4f}" for g, v in avg.items()) + "\n")
        f.write(f"chosen,{chosen}\nflags,{' | '.join(flags) if flags else 'none'}\n")


def tables():
    import csv
    import numpy as np
    from scipy import stats
    from catsim.v5 import FAMILY, test_id
    from catsim.v6 import SHORT_V6, V6_ALL, plan_v6
    run_dir = os.path.join(HERE, "results_v6", "runs")
    steps = plan_v6()
    tasks = [t for _, ts in steps for t in ts]
    runs = load(tasks, run_dir)
    tests, seeds = [], sorted({sd for _, _, sd in tasks})
    for sc, _, _ in tasks:
        if sc not in tests:
            tests.append(sc)
    rows = []
    for sc in tests:
        for r in V6_ALL:
            xs = [runs[(sc, r, sd)] for sd in seeds if (sc, r, sd) in runs]
            if len(xs) < len(seeds):
                continue
            m = np.array([o["miss"] * 100 for o in xs])
            rows.append(dict(test=test_id(sc), label=sc.label, group=sc.group, family=FAMILY[sc.group], rule=r,
                             miss=round(float(m.mean()), 3),
                             ci95=round(float(stats.t.ppf(0.975, len(m) - 1) * m.std(ddof=1) / np.sqrt(len(m))), 3),
                             dropped=round(float(np.mean([o.get("dropped", 0) for o in xs]) * 100), 3),
                             seeds=" ".join(f"{v:.4f}" for v in m)))
    out = os.path.join(HERE, "results_v6", "tables")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "summary_v6.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} test x rule rows -> results_v6/tables/summary_v6.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--tables", action="store_true")
    cpus = os.cpu_count() or 2
    ap.add_argument("--workers", type=int, default=cpus)
    a = ap.parse_args()
    if a.pilot:
        return pilot(a.workers)
    if a.tables:
        return tables()
    from catsim import experiments
    from catsim.v6 import plan_v6
    run_dir = os.path.join(HERE, "results_v6", "runs")
    t0 = time.time()
    steps = plan_v6()
    print(f"v6 study: {sum(len(t) for _, t in steps)} runs on fresh seeds 201-210, {a.workers} worker(s)")
    for k, (name, tasks) in enumerate(steps, 1):
        print(f"\n[{k}/{len(steps)}] {name}: {len(tasks)} runs", flush=True)
        experiments.execute(tasks, run_dir, a.workers)
    tables()
    print(f"\nDone in {experiments.fmt_time(time.time() - t0)}")


if __name__ == "__main__":
    main()
