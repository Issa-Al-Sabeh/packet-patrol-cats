"""Phase 0 reproduction check: re-run a sample of the saved v6 runs from the FROZEN code and compare.

    python3 repro_check.py --frozen /path/to/v6-frozen --out repro_results.csv [--workers 2]

Study 1 (61 tests): each re-run's miss % is compared with the per-seed value saved in
results_v6/tables/summary_v6.csv (4 decimals, as saved).
Study 2 (11 baselines): each re-run is compared with its row in study_results/tables/runs_all.csv on
success, late, expired, rejected, mean and p99 response time, and telemetry bytes (full float precision).
The sample is fixed by SAMPLE_SEED, so the check itself is repeatable. Nothing is written to the frozen folder.
"""
import argparse
import csv
import os
import random
import sys
import time
from multiprocessing import get_context

SAMPLE_SEED = 20261114
S2_FIELDS = ["success", "late_completed", "expired", "rejected", "mean_ms", "p99_ms", "bytes_per_s"]
S2_PCT = {"success", "late_completed", "expired", "rejected"}


def sample_study1(rng):
    from catsim.v5 import test_id
    from catsim.v6 import V6_ALL, plan_v6
    saved = {}
    with open(os.path.join(FROZEN, "results_v6", "tables", "summary_v6.csv")) as f:
        for row in csv.DictReader(f):
            saved[(row["test"], row["rule"])] = [float(x) for x in row["seeds"].split()]
    tasks = [(sc, r, sd) for _, ts in plan_v6() for sc, r, sd in ts]
    by = {}
    for sc, r, sd in tasks:
        by.setdefault((test_id(sc), r), {})[sd] = sc
    tests = []
    for sc, _, _ in tasks:
        if test_id(sc) not in tests:
            tests.append(test_id(sc))
    pick = set()
    for k, t in enumerate(tests):                               # ours_v6 on every one of the 61 tests
        pick.add((t, "ours_v6", 201 + k % 10))
    for t in ("main", "O_130", "O_burst", "L:main", "L:O_130"):   # every rule on five anchor tests
        for r in V6_ALL:
            if (t, r) in by:
                pick.add((t, r, rng.choice(range(201, 211))))
    rest = [(t, r, sd) for (t, r), d in by.items() for sd in d]
    pick.update(rng.sample(rest, 60))
    out = []
    for t, r, sd in sorted(pick):
        out.append(("study1", t, r, sd, by[(t, r)][sd], r, {"miss_pct": saved[(t, r)][sd - 201]}))
    return out, len(tests)


def sample_study2(rng):
    from catsim import study as st
    saved = {}
    with open(os.path.join(FROZEN, "study_results", "tables", "runs_all.csv")) as f:
        for row in csv.DictReader(f):
            saved[(row["scenario"], row["alias"], int(row["seed"]))] = row
    frozen = st.load_frozen()
    scs = {}
    for _, _, lst in st.experiments(frozen):
        for sc, alias in lst:
            scs[(sc.key, alias)] = sc
    keys = sorted(saved)
    pick = set()
    aliases = sorted({a for _, a, _ in keys})
    for a in aliases:                                           # every rule string, three runs each
        pick.update(rng.sample([k for k in keys if k[1] == a], 3))
    v6 = [k for k in keys if k[1] == "ours_v6"]
    pick.update(rng.sample(v6, 60))                             # ours_v6 across the grid
    pick.update(rng.sample(keys, 120))
    out = []
    for key, alias, sd in sorted(pick):
        row = saved[(key, alias, sd)]
        rule = st.resolved(alias, frozen)
        assert rule == row["rule"], (rule, row["rule"])
        exp = {k: float(row[k]) for k in S2_FIELDS if row[k] != ""}
        out.append(("study2", key, alias, sd, scs[(key, alias)], rule, exp))
    return out, len(aliases)


def work(job):
    study, test, alias, seed, sc, rule, exp = job
    from catsim.engine import run
    o = run(sc, rule, seed)
    if study == "study1":
        got = {"miss_pct": round(o["miss"] * 100, 4)}
        ok = got["miss_pct"] == round(exp["miss_pct"], 4)
        worst = abs(got["miss_pct"] - exp["miss_pct"])
    else:
        got = {k: o[k] * (100.0 if k in S2_PCT else 1.0) for k in exp}
        diffs = [abs(got[k] - exp[k]) / max(1.0, abs(exp[k])) for k in exp]
        worst = max(diffs)
        ok = worst <= 1e-9
    return dict(study=study, test=test, rule=alias, seed=seed, match=ok, worst_diff=worst,
                saved=";".join(f"{k}={v:.10g}" for k, v in exp.items()),
                rerun=";".join(f"{k}={v:.10g}" for k, v in got.items()), runtime_s=o["runtime_s"])


def main():
    global FROZEN
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    FROZEN = os.path.abspath(a.frozen)
    sys.path.insert(0, FROZEN)
    os.environ["PYTHONPATH"] = FROZEN + os.pathsep + os.environ.get("PYTHONPATH", "")
    rng = random.Random(SAMPLE_SEED)
    j1, n_tests = sample_study1(rng)
    j2, n_alias = sample_study2(rng)
    jobs = j1 + j2
    print(f"Study 1: {len(j1)} runs ({n_tests} tests). Study 2: {len(j2)} runs ({n_alias} rule strings).", flush=True)
    t0 = time.time()
    rows = []
    with get_context("spawn").Pool(a.workers) as pool:
        for k, r in enumerate(pool.imap_unordered(work, jobs, chunksize=1), 1):
            rows.append(r)
            if k % 50 == 0:
                print(f"  {k}/{len(jobs)}  {time.time() - t0:.0f} s", flush=True)
    rows.sort(key=lambda r: (r["study"], r["test"], r["rule"], r["seed"]))
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for s in ("study1", "study2"):
        rs = [r for r in rows if r["study"] == s]
        bad = [r for r in rs if not r["match"]]
        print(f"{s}: {len(rs) - len(bad)} of {len(rs)} match; largest difference {max(r['worst_diff'] for r in rs):.3g}")
        for r in bad[:20]:
            print("   MISMATCH", r["test"], r["rule"], r["seed"], r["saved"], "->", r["rerun"])
    print(f"Done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
