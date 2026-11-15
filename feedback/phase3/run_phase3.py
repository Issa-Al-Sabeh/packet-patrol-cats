"""Phase 3 measurements (feedback of 11 Nov 2026: the baselines).

    python3 run_phase3.py lsq    [--workers N]  the LSQ diagnostic: 8 sites, 90% load, reports every 0.5 s and 10 s,
                                                seeds 201-205                                   -> lsq.csv, lsq_traj.npz
    python3 run_phase3.py static [--workers N]  the deadline-aware static split: its design load, pilot seeds
                                                101-105, Beirut                                 -> static.csv

The LSQ diagnostic re-measures a BASELINE where its collapse was reported (the 8-site network, seeds of the saved
study). It chooses nothing about ours v6.1. The static split is tuned on pilot seeds on the Beirut network only.
"""
import argparse
import csv
import os
import sys
import time
from multiprocessing import get_context

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, HERE, os.path.join(os.path.dirname(HERE), "phase1"), os.path.join(os.path.dirname(HERE), "phase2")):
    sys.path.insert(0, p)

LSQ_RULES = ["lsq", "lsq_randtie", "lsq_poll_sync", "lsq_poll_phase", "lsq_poll_site", "lsq_sample", "wrr", "wrr_phase"]
LSQ_W = (0.5, 10.0)
TRAJ = {("lsq", 0.5), ("lsq_poll_phase", 0.5), ("lsq", 10.0)}       # queue trajectories kept for the figure (seed 201)
T0, T1, DT = 40.0, 60.0, 0.05
WIN = 0.5
STATIC_LOADS = (0.70, 0.85, 0.95)


def lsq_job(job):
    rule, W, seed = job
    import lsq_variants  # noqa: F401
    from catsim import study as st
    from catsim.engine import run
    sc = st.make(0.9, 0.05, "steady", W=W)
    box = {}
    o = run(sc, rule, seed, hook=lambda d: box.update(d))
    created, site, arr, fin = (np.asarray(box[k]) for k in ("created", "site_of", "arr_t", "finish"))
    dropped = np.asarray(box["dropped"], dtype=bool)
    warm, T = box["warm"], box["T"]
    S = len(sc.servers)
    cap = np.asarray(sc.servers, float) * sc.mu
    keep = (created >= warm) & ~dropped
    edges = np.arange(warm, T + 1e-9, WIN)
    idx = np.clip(np.searchsorted(edges, created[keep], side="right") - 1, 0, len(edges) - 2)
    counts = np.zeros((len(edges) - 1, S))
    np.add.at(counts, (idx, site[keep]), 1)
    load = counts / (cap * WIN)                                   # arrivals of each half second over the site's capacity
    row = dict(rule=rule, W=W, seed=seed, success=o["success"] * 100, late=o["late_completed"] * 100,
               expired=o["expired"] * 100, peak_site_load=float(load.max(axis=1).mean()),
               idle_site_share=float((load.min(axis=1) < 0.25).mean()),
               bytes_per_s_per_ingress=o["bytes_per_s_per_ingress"])
    traj = None
    if seed == 201 and (rule, W) in TRAJ:
        t = np.arange(T0, T1 + 1e-9, DT)
        traj = np.zeros((S, len(t)))
        # a frame leaves the site when it is finished, or (deadline-aware sites) when it is thrown away: that happens
        # once its deadline has passed and it is at the head of the queue, so created + D is its leaving time
        leave = np.where(np.asarray(box["discarded"], dtype=bool), created + box["D"], fin)
        for s in range(S):
            m = (site == s) & ~dropped & np.isfinite(arr)
            a, f = np.sort(arr[m]), np.sort(leave[m][np.isfinite(leave[m])])
            traj[s] = (np.searchsorted(a, t, side="right") - np.searchsorted(f, t, side="right")) / sc.servers[s]
    return row, (rule, W, traj)


def static_job(job):
    net, sc, label, rule, seed = job
    from catsim.engine import run
    o = run(sc, rule, seed)
    return dict(net=net, scenario=sc.key, label=sc.label, variant=label, rule=rule, seed=seed,
                success=o["success"] * 100, rejected=o["rejected"] * 100, expired=o["expired"] * 100,
                late=o["late_completed"] * 100, bytes_per_s_per_ingress=o["bytes_per_s_per_ingress"])


def write(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} runs -> {os.path.relpath(path, ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["lsq", "static"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    t0 = time.time()
    with get_context("spawn").Pool(a.workers) as pool:
        if a.what == "lsq":
            jobs = [(r, W, sd) for W in LSQ_W for r in LSQ_RULES for sd in range(201, 206)]
            rows, traj = [], {}
            for k, (row, (rule, W, tr)) in enumerate(pool.imap_unordered(lsq_job, jobs, chunksize=1), 1):
                rows.append(row)
                if tr is not None:
                    traj[f"{rule}|{W:g}"] = tr
                if k % 20 == 0 or k == len(jobs):
                    print(f"  {k}/{len(jobs)}  {time.time() - t0:.0f} s", flush=True)
            rows.sort(key=lambda r: (r["W"], LSQ_RULES.index(r["rule"]), r["seed"]))
            write(rows, os.path.join(HERE, "lsq.csv"))
            np.savez_compressed(os.path.join(HERE, "lsq_traj.npz"), t=np.arange(T0, T1 + 1e-9, DT), **traj)
        else:
            import run_phase2 as p2
            variants = [(f"static {int(d * 100)}% + admission", f"static_deadline@DESIGN_LOAD={d}+adm61")
                        for d in STATIC_LOADS]
            variants += [("round-robin + admission", "wrr+adm61"), ("ours v6.1", "ours_v61"),
                         ("static 85%, no admission", "static_deadline@DESIGN_LOAD=0.85"), ("round-robin", "wrr")]
            jobs = [(net, sc, lab, rule, sd) for net, sc in p2.scenarios() for lab, rule in variants for sd in p2.SEEDS]
            rows = []
            for k, r in enumerate(pool.imap_unordered(static_job, jobs, chunksize=1), 1):
                rows.append(r)
                if k % 100 == 0 or k == len(jobs):
                    print(f"  {k}/{len(jobs)}  {time.time() - t0:.0f} s", flush=True)
            order = {lab: k for k, (lab, _) in enumerate(variants)}
            rows.sort(key=lambda r: (r["net"], r["scenario"], order[r["variant"]], r["seed"]))
            write(rows, os.path.join(HERE, "static.csv"))


if __name__ == "__main__":
    main()
