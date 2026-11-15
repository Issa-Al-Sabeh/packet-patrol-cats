"""Phase 1 measurements (feedback of 11 Nov 2026, traffic estimator).

    python3 run_phase1.py counter                 the counterexample, simulated (prints the estimates)
    python3 run_phase1.py diagnose  [--workers N] frozen v6 in the existing scenarios, seeds 201-205 -> diagnose.csv
    python3 run_phase1.py pilot     [--workers N] the candidates on pilot seeds 101-105          -> pilot.csv
    python3 run_phase1.py validate  [--workers N] ours v6.1 (catsim/rules_v61.py, the counter in the engine) on the
                                                  same pilot runs, against the emulated prototype     -> validate.csv

Which runs may choose a fix. The candidates are compared ONLY on pilot seeds 101-105, on v6's own pilot tests and on
new development scenarios (dev_*) on the Beirut network. The held-out tests, the large network and the 8-site network
take no part in the choice; 'diagnose' only measures the frozen rule there.
"""
import argparse
import csv
import json
import os
import sys
import time
from dataclasses import replace
from multiprocessing import get_context

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

BIN = 5.0                 # seconds: window for per-ingress drop shares


def scenarios_diagnose():
    from catsim import study as st
    from catsim.v5 import build_overload
    out = [("beirut", sc) for sc in build_overload()[0]]
    mk = st.make
    eight = [mk(1.1, 0.05, "steady"), mk(1.3, 0.05, "steady"), mk(1.3, 1.0, "steady"),
             mk(0.9, 0.05, "bursty"), mk(1.1, 0.05, "bursty"), mk(1.3, 0.05, "bursty"),
             mk(1.1, 0.05, "shifting"), mk(1.3, 0.05, "shifting"),
             mk(1.3, 0.05, "steady", R=16), mk(1.3, 0.05, "steady", W=10.0), mk(1.3, 0.05, "steady", W=0.5),
             mk(0.9, 0.05, "steady", extra=st.FAIL, tag="fail"), mk(0.9, 0.05, "steady", extra=st.SLOW, tag="slow"),
             mk(1.3, 0.05, "steady", extra=dict(report_loss=0.3), tag="loss")]
    return out + [("eight", sc) for sc in eight]


def scenarios_pilot():
    from catsim.config import MAIN, build_scenarios
    from catsim.v5 import build_overload
    _, sweeps, _ = build_scenarios()
    pool = {sc.key: sc for _, (_, _, pts) in sweeps.items() for sc in pts}
    pool.update({sc.key: sc for sc in build_overload()[0]})
    over = replace(MAIN, group="dev", site_discard=True)
    dev = [replace(over, key="dev_115", label="Dev: load 115%", load=1.15),
           replace(over, key="dev_surge_B", label="Dev: load 95%, Ingress B (30% of traffic) doubles 50-100 s",
                   load=0.95, surge=(1, 2.0, 50.0, 100.0)),
           replace(over, key="dev_stagger_125", label="Dev: load 125%, sites report at different moments",
                   load=1.25, stagger_reports=True),
           replace(over, key="dev_W1_120", label="Dev: load 120%, reports every 1 s", load=1.20, report_interval=1.0),
           replace(over, key="dev_loss_120", label="Dev: load 120%, 30% of reports lost", load=1.20, report_loss=0.3)]
    return [("pilot", MAIN), ("pilot", pool["load=95"]), ("pilot", pool["O_130"]), ("pilot", pool["O_burst"])] \
        + [("dev", sc) for sc in dev]


# ours v6.1 as it was when Phase 1 closed: dropping allowed from 95%, as in v6 (Phase 2 moved the default to 90%)
V61_PHASE1 = "ours_v61@DROP_FROM=0.95"
PILOT_RULES = ["ours_v6", "est_own_b1", "est_bound", "est_bound_b1", "est_echo", "est_echo_b1"]


def measure(job):
    net, sc, rule, seed = job
    import candidates as cd
    from catsim.engine import run
    box = {}
    out = run(sc, cd.register(rule, "rec"), seed, hook=lambda d: box.update(d))
    created = np.asarray(box["created"])
    ing = np.asarray(box["ing"])
    dropped = np.asarray(box["dropped"], dtype=bool)
    site = np.asarray(box["site_of"])
    warm, T = box["warm"], box["T"]
    R, S, W, mu = sc.ingresses, len(sc.servers), sc.report_interval, sc.mu
    keep = created >= warm
    span = T - warm
    cap_site = np.asarray(sc.servers, float) * mu
    # ---- per-ingress drop shares, whole run and per BIN seconds
    share = [float(dropped[keep & (ing == i)].mean()) if (keep & (ing == i)).any() else float("nan") for i in range(R)]
    edges = np.arange(warm, T + 1e-9, BIN)
    spread, hi, lo = [], [], []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (created >= a) & (created < b)
        if dropped[m].mean() < 0.01:
            continue
        ps = [dropped[m & (ing == i)].mean() for i in range(R) if (m & (ing == i)).sum() >= 20]
        if len(ps) >= 2:
            spread.append(max(ps) - min(ps))
            hi.append(max(ps))
            lo.append(min(ps))
    # ---- what each ingress believed at its plans against the truth
    ratio, belief = [], np.zeros((R, S))
    pdrop_plan = []
    for i, r in enumerate(box["rules"]):
        rec = np.array([x for x in r.rec if x[0] >= warm], float)
        if len(rec) == 0:
            ratio.append(float("nan"))
            pdrop_plan.append(float("nan"))
            continue
        t = rec[:, 0]
        true = (np.searchsorted(created, t, side="right") - np.searchsorted(created, t - W, side="right")) / W
        dt = np.diff(np.append(t, T))                         # each plan holds until the next one
        ratio.append(float(np.sum(rec[:, 1] / np.maximum(true, 1e-9) * dt) / dt.sum()))
        pdrop_plan.append(float(np.sum(rec[:, 2] * dt) / dt.sum()))
        belief[i] = (rec[:, 1:2] * rec[:, 6:6 + S] * dt[:, None]).sum(axis=0) / dt.sum()
    realized = np.array([((site == s) & keep).sum() / span for s in range(S)])
    sent = (keep & ~dropped).sum() / span
    meters = [len(r.meter.log) for r in box["rules"]]
    echo = sum(getattr(r, "echo_msgs", 0) for r in box["rules"])
    is_echo = getattr(box["rules"][0], "share_mode", "own") == "echo"
    return dict(
        net=net, scenario=sc.key, label=sc.label, rule=rule, seed=seed, R=R, W=W,
        success=out["success"] * 100, rejected=out["rejected"] * 100, expired=out["expired"] * 100,
        late=out["late_completed"] * 100,
        admitted_over_capacity=float(sent / cap_site.sum()),
        share_min=float(np.nanmin(share)) * 100, share_max=float(np.nanmax(share)) * 100,
        share_by_ingress=json.dumps([round(x * 100, 3) for x in share]),
        spread_mean=float(np.mean(spread)) * 100 if spread else 0.0,
        spread_max=float(np.max(spread)) * 100 if spread else 0.0, bins_dropping=len(spread),
        est_min=float(np.nanmin(ratio)), est_max=float(np.nanmax(ratio)),
        est_by_ingress=json.dumps([round(x, 4) for x in ratio]),
        plan_drop_by_ingress=json.dumps([round(x * 100, 3) for x in pdrop_plan]),
        site_load=json.dumps([round(float(x), 4) for x in realized / cap_site]),
        belief_over_realized=json.dumps([round(float(x), 4) for x in belief.mean(axis=0) / np.maximum(realized, 1e-9)]),
        meter_changes=json.dumps(meters),
        extra_bytes_per_s_per_ingress=(echo * cd.ECHO_BYTES / T / R + S * cd.ECHO_BYTES / W) if is_echo else 0.0,
        base_bytes_per_s_per_ingress=out["bytes_per_s_per_ingress"], runtime_s=out["runtime_s"])


def execute(jobs, path, workers):
    t0, rows = time.time(), []
    with get_context("spawn").Pool(workers) as pool:
        for k, r in enumerate(pool.imap_unordered(measure, jobs, chunksize=1), 1):
            rows.append(r)
            if k % 25 == 0 or k == len(jobs):
                print(f"  {k}/{len(jobs)}  {time.time() - t0:.0f} s", flush=True)
    rows.sort(key=lambda r: (r["net"], r["scenario"], r["rule"], r["seed"]))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} runs -> {os.path.relpath(path, ROOT)}  ({time.time() - t0:.0f} s)")


def compare_with_prototype():
    """ours_v61 (real counter) against est_echo_b1 (emulated counter) on the same runs."""
    def rows(name, rule):
        with open(os.path.join(HERE, name)) as f:
            return {(r["scenario"], int(r["seed"])): r for r in csv.DictReader(f) if r["rule"] == rule}
    real, proto = rows("validate.csv", V61_PHASE1), rows("pilot.csv", "est_echo_b1")
    assert real.keys() == proto.keys()
    cols = ("success", "rejected", "expired", "late", "share_by_ingress", "est_by_ingress")
    same = sum(all(real[k][c] == proto[k][c] for c in cols) for k in real)
    worst = max(abs(float(real[k]["success"]) - float(proto[k]["success"])) for k in real)
    print(f"ours_v61 against the emulated prototype: {same} of {len(real)} runs identical; "
          f"largest difference in success {worst:.4f} points")


def counter():
    import test_estimator as te
    for rule in ("ours_v6", "est_bound", "est_echo"):
        print(f"{rule:10s} estimates at the two ingresses: " + ", ".join(f"{x:6.1f}" for x in te._estimates(rule))
              + f"   (truth {te.TRUTH:.0f})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["counter", "diagnose", "pilot", "validate"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    if a.what == "counter":
        return counter()
    if a.what == "diagnose":
        jobs = [(net, sc, "ours_v6", sd) for net, sc in scenarios_diagnose() for sd in range(201, 206)]
        return execute(jobs, os.path.join(HERE, "diagnose.csv"), a.workers)
    if a.what == "validate":
        jobs = [(net, sc, V61_PHASE1, sd) for net, sc in scenarios_pilot() for sd in range(101, 106)]
        execute(jobs, os.path.join(HERE, "validate.csv"), a.workers)
        return compare_with_prototype()
    jobs = [(net, sc, r, sd) for net, sc in scenarios_pilot() for r in PILOT_RULES for sd in range(101, 106)]
    execute(jobs, os.path.join(HERE, "pilot.csv"), a.workers)


if __name__ == "__main__":
    main()
