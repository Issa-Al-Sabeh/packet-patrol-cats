"""ONE COMMAND per step of the staleness-aware CATS study (Nov 2026). See STUDY_README.md.

    python3 run_study.py --smoke            every main rule once (seed 101, true-state guard on), a few seconds each
    python3 -m pytest tests -q              unit and integration tests
    python3 run_study.py --pilot            tuning on pilot seeds 101-105, then FREEZE (writes frozen_params.json)
    python3 run_study.py --run              every experiment on seeds 201-210, in priority order (resumable)
    python3 run_study.py --run exp7_admission grid_core_load      only these experiments
    python3 run_study.py --status           completed vs pending runs per experiment
    python3 run_study.py --tables           CSV tables from the saved runs (completed runs only)
    python3 run_study.py --plots            figures (PNG + PDF) from the tables

Every run is saved as one JSON file the moment it finishes (study_results/runs/); an interrupted batch continues
where it stopped. Parameters are frozen by the pilot and never changed after the final seeds start.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "study_results")
RUNS = os.path.join(OUT, "runs")
PILOT_RUNS = os.path.join(OUT, "pilot_runs")


def _load(path):
    with open(path) as f:
        return json.load(f)


def smoke():
    from catsim.engine import run
    from catsim import study as st
    sc = st.make(0.9, 0.05, "steady")
    for alias in st.MAIN_RULES + ["oracle_adm"]:
        t0 = time.time()
        o = run(sc, st.resolved(alias), 101, guard=True)
        print(f"  {st.SHORT.get(alias, alias):14s} success {o['success'] * 100:6.2f}%  rejected {o['rejected'] * 100:5.2f}%"
              f"  telemetry {o['bytes_per_s_per_ingress']:7.1f} B/s/ingress  {time.time() - t0:4.1f} s", flush=True)


def pilot(workers, force=False):
    import numpy as np
    from catsim import experiments, study as st
    if os.path.exists(st.PARAMS_FILE) and not force:
        print("Parameters are already frozen (study_results/frozen_params.json); use --force to redo the pilot.")
        return
    scs = st.pilot_scenarios()
    tasks = []
    for alias, cands in st.PILOT_CANDIDATES.items():
        for cand in cands:
            for sc in scs:
                for sd in st.SEEDS_PILOT:
                    tasks.append((sc, f"{alias}@{cand}", sd))
    thr_scs = {th: st.make(0.9, 0.05, "steady", W=0.5, extra=dict(report_mode="threshold", report_threshold=th),
                           tag=f"thr{th:g}") for th in st.PILOT_THRESHOLDS}
    for th, sc in thr_scs.items():
        for r in ("ours_v6", "wrr_speed"):
            for sd in st.SEEDS_PILOT:
                tasks.append((sc, r, sd))
    # sanity of the time scales: the main rules once per pilot scenario
    for sc in scs:
        for r in ("wrr", "ours_v6", "oracle", "lsq"):
            for sd in st.SEEDS_PILOT:
                tasks.append((sc, r, sd))
    print(f"Pilot: {len(tasks)} runs on seeds {st.SEEDS_PILOT}", flush=True)
    experiments.execute(tasks, PILOT_RUNS, workers)
    res = {}
    lines = ["rule,candidate,mean_success_pct," + ",".join(sc.key for sc in scs)]
    frozen = {}
    for alias, cands in st.PILOT_CANDIDATES.items():
        best, best_v = None, -1.0
        for cand in cands:
            per = []
            for sc in scs:
                v = [_load(experiments.run_path(PILOT_RUNS, sc, f"{alias}@{cand}", sd))["success"] for sd in st.SEEDS_PILOT]
                per.append(float(np.mean(v)) * 100)
            m = float(np.mean(per))
            res[(alias, cand)] = (m, per)
            lines.append(f"{alias},\"{cand}\",{m:.3f}," + ",".join(f"{x:.3f}" for x in per))
            if best is None or m > best_v + 0.1:            # ties within 0.1 points keep the earlier (paper default)
                best, best_v = cand, m
        frozen[alias] = best
    target = 8 * (62 + 4) / 2.0
    thr_bytes = {}
    for th, sc in thr_scs.items():
        b = [_load(experiments.run_path(PILOT_RUNS, sc, r, sd))["bytes_per_s_per_ingress"]
             for r in ("ours_v6", "wrr_speed") for sd in st.SEEDS_PILOT]
        thr_bytes[th] = float(np.mean(b))
        lines.append(f"threshold_telemetry,{th},bytes_per_s_per_ingress={thr_bytes[th]:.1f},target={target:.1f}")
    frozen["_threshold"] = min(thr_bytes, key=lambda th: abs(thr_bytes[th] - target))
    frozen["_frozen_at"] = time.strftime("%Y-%m-%d %H:%M")
    frozen["_decision_rule"] = ("per tunable baseline: the candidate with the highest mean deadline success over the 4 "
                                "pilot scenarios x 5 pilot seeds; within 0.1 points the earlier candidate (paper "
                                "default first); threshold telemetry: the threshold whose realized bytes are closest "
                                "to the medium budget (264 B/s per ingress)")
    for sc in scs:
        for r in ("wrr", "ours_v6", "oracle", "lsq"):
            v = [_load(experiments.run_path(PILOT_RUNS, sc, r, sd))["success"] * 100 for sd in st.SEEDS_PILOT]
            lines.append(f"timescale_check,{r},{np.mean(v):.2f},{sc.key}")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "pilot_results.csv"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(st.PARAMS_FILE, "w") as f:
        json.dump(frozen, f, indent=1)
    print("\n".join(lines))
    print("\nFROZEN:", json.dumps(frozen, indent=1))


def plan(only=None):
    from catsim import study as st
    exps = st.experiments()
    if only:
        exps = [e for e in exps if e[0] in only]
    return exps, st


def save_config():
    from dataclasses import asdict
    from catsim import study as st
    exps, _ = plan()
    cfg = {"seeds_final": list(st.SEEDS_FINAL), "seeds_pilot": list(st.SEEDS_PILOT),
           "frozen_params": st.load_frozen(), "experiments": []}
    for eid, desc, lst in exps:
        scen = {}
        for sc, alias in lst:
            scen.setdefault(sc.key, {"scenario": asdict(sc), "rules": []})["rules"].append(
                {"alias": alias, "run_as": st.resolved(alias)})
        cfg["experiments"].append({"id": eid, "description": desc, "scenarios": scen})
    with open(os.path.join(OUT, "config_snapshot.json"), "w") as f:
        json.dump(cfg, f, indent=1, default=str)


def run_all(workers, only=None):
    from catsim import experiments
    exps, st = plan(only)
    if not st.load_frozen():
        print("Run the pilot first (parameters are not frozen yet).")
        return
    save_config()
    t0 = time.time()
    total = sum(len(lst) * len(st.SEEDS_FINAL) for _, _, lst in exps)
    print(f"Study: {total} runs in {len(exps)} experiments, seeds 201-210, {workers} worker(s)", flush=True)
    for k, (eid, desc, lst) in enumerate(exps, 1):
        tasks = [(sc, st.resolved(alias), sd) for sc, alias in lst for sd in st.SEEDS_FINAL]
        print(f"\n[{k}/{len(exps)}] {eid}: {desc} ({len(tasks)} runs)", flush=True)
        experiments.execute(tasks, RUNS, workers)
        print(f"    elapsed {experiments.fmt_time(time.time() - t0)}", flush=True)


def status():
    from catsim import experiments
    exps, st = plan()
    tot_d = tot = 0
    for eid, desc, lst in exps:
        n = d = 0
        for sc, alias in lst:
            for sd in st.SEEDS_FINAL:
                n += 1
                d += os.path.exists(experiments.run_path(RUNS, sc, st.resolved(alias), sd))
        tot_d += d
        tot += n
        print(f"  {eid:20s} {d:5d} / {n:5d} runs done")
    print(f"  {'TOTAL':20s} {tot_d:5d} / {tot:5d}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--run", nargs="*")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--tables", action="store_true")
    ap.add_argument("--plots", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    if a.smoke:
        return smoke()
    if a.pilot:
        return pilot(a.workers, a.force)
    if a.run is not None:
        return run_all(a.workers, a.run or None)
    if a.status:
        return status()
    if a.tables:
        from catsim import study_analysis
        return study_analysis.main()
    if a.plots:
        from catsim import study_plots
        return study_plots.main()
    ap.print_help()


if __name__ == "__main__":
    main()
