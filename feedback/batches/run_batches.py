"""Batches A and B of the evaluation of ours v6.1: the runner.

    python3 feedback/batches/run_batches.py check                      frozen files, plan sizes; runs nothing
    python3 feedback/batches/run_batches.py A [--workers N] [--seeds 301-305]
    python3 feedback/batches/run_batches.py B [--workers N] [--seeds 301-305]

What is run is exactly catsim.v61.plan(batch, seeds): the scenarios, the rules and the seeds were fixed at the freeze
(FREEZE_v6.1.md, 15 Nov 2026). Nothing is chosen here, and nothing in catsim/ is changed by this script.

  Batch A  every run is engine.run(scenario, rule, seed) as it is.
  Batch B  the same run, with the rule wrapped in a recorder that only writes down what the rule believed (the
           recorder never changes a decision: test_batches.py, and analyze_batches.py checks that the runs Batch A
           and Batch B share are equal).
           Measured besides success, as fixed at the freeze and defined as in feedback/phase1/run_phase1.py (measure):
             estimate / truth at each ingress   the rule's estimate of the total offered traffic at each update,
                                                divided by the frames really created in the W seconds before it,
                                                averaged over time (each estimate holds until the next one);
             drop share of each ingress         frames it dropped / frames it was offered, after the warm-up;
             admitted traffic / capacity        frames sent to a site per second / the configured capacity;
             telemetry bytes                    reports + drop counts, per second and per ingress (engine).

The run can be stopped and started again: finished runs are kept in _work/ and are not run twice.
Outputs, next to this file:
    batch_<X>.csv              one row per run
    batch_<X>_detail.jsonl.gz  per run: the per-second counts (frames, on time, rejected, discarded, late) and the
                               rule's own diagnostics (for the note on slow recovery and for Batch C)
    batch_<X>_manifest.json    what was run, on which code, with which library versions
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from multiprocessing import get_context

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "phase1"))

BIN = 5.0                                   # seconds: window for the per-ingress drop shares (as in Phase 1)
SIZES = {"A": 770, "B": 280}                # with five seeds (FREEZE_v6.1.md)


# ------------------------------------------------------------------------------------------- the frozen code
def frozen_files():
    """(path, expected SHA-256) for every file listed in FREEZE_v6.1.md."""
    with open(os.path.join(ROOT, "FREEZE_v6.1.md"), encoding="utf-8") as f:
        return re.findall(r"\| `([^`]+)` \| `([0-9a-f]{64})` \|", f.read())


def check_frozen():
    """Compare the frozen files with their fingerprints. Returns (checked, changed, crlf): files that differ, and
    files that match only after Windows line endings are turned back into Unix ones (the same code; git on Windows
    may check files out that way)."""
    changed, crlf = [], []
    files = frozen_files()
    for path, want in files:
        with open(os.path.join(ROOT, path), "rb") as f:
            raw = f.read()
        if hashlib.sha256(raw).hexdigest() == want:
            continue
        if hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == want:
            crlf.append(path)
        else:
            changed.append(path)
    return len(files), changed, crlf


def git(*args):
    try:
        return subprocess.run(["git", "-c", "core.filemode=false", *args], cwd=ROOT, capture_output=True, text=True,
                              timeout=30).stdout.strip() or None
    except Exception:
        return None


# ------------------------------------------------------------------------------------------- the plan
def parse_seeds(text):
    out = []
    for part in text.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return tuple(out)


def jobs_of(batch, seeds):
    from catsim import v61
    bad = [s for s in seeds if s not in v61.EVAL_SEEDS]
    if bad:
        raise SystemExit(f"seeds {bad} are not evaluation seeds of v6.1 ({v61.EVAL_SEEDS[0]}-{v61.EVAL_SEEDS[-1]})")
    jobs = [(batch, net, sc, rule, sd) for net, sc, rule, sd in v61.plan(batch, seeds)]
    keys = [key_of(j) for j in jobs]
    assert len(set(keys)) == len(keys), "two runs of the plan have the same name"
    return jobs


def key_of(job):
    batch, net, sc, rule, seed = job
    return f"{batch}|{net}|{sc.key}|{rule}|{seed}"


def physics_id(sc):
    return hashlib.sha1(repr(sc.physics()).encode()).hexdigest()[:12]


def is_pilot_scenario(net, sc):
    """v6.1's settings were chosen on this scenario (with other seeds): as in FREEZE_v6.1.md."""
    from catsim.v6 import PILOT_TESTS_V6
    return net == "beirut" and sc.key in PILOT_TESTS_V6


def nice_label(net, sc):
    if net != "eight":
        return sc.label
    m = json.loads(sc.factor)
    extra = "" if m["R"] == 4 else f", {m['R']} ingresses"
    return f"Load {int(round(m['load'] * 100))}%, {m['pattern']}, reports every {m['W']:g} s{extra}"


# ------------------------------------------------------------------------------------------- recorders (Batch B)
def recording_wrapper(base):
    """The common admission wrapper (<rule>+adm or <rule>+adm61), writing down its estimate of the offered traffic
    each time it changes: (time, estimate of the total offered traffic, share it then drops). Nothing else changes."""
    from catsim.baselines import AdmissionWrapper61

    if issubclass(base, AdmissionWrapper61):          # one estimate per round of reports, made in choose()
        class Rec(base):
            def __init__(self, ctx, i):
                super().__init__(ctx, i)
                self.rec, self._t = [], 0.0

            def choose(self, now):
                self._t = now
                return super().choose(now)

            def _update(self):
                super()._update()
                if self.seen.all():
                    self.rec.append((self._t, float(self.rate_off.sum()), float(self.p_drop)))
    else:                                             # own drop share: the estimate moves with every report
        class Rec(base):
            def __init__(self, ctx, i):
                super().__init__(ctx, i)
                self.rec = []

            def on_report_x(self, now, s, q, g, A, X):
                new = g > self.last_g[s]
                super().on_report_x(now, s, q, g, A, X)
                if new and self.seen.all():
                    self.rec.append((now, float(self.rate_off.sum()), float(self.p_drop)))
    Rec.__name__ = "Rec[" + base.__name__ + "]"
    return Rec


def register_recorder(rule):
    """Register the recording version of a rule and return its name."""
    import candidates as cd                                    # feedback/phase1: the recorder of the split rules
    from catsim.baselines import AdmissionWrapper, resolve_rule
    from catsim.rules import RULE_CLASSES
    base = resolve_rule(rule)
    if issubclass(base, AdmissionWrapper):
        name = "_recw_" + rule.replace("@", "_at_").replace("=", "_").replace(",", "_").replace("+", "_plus_")
        if name not in RULE_CLASSES:
            RULE_CLASSES[name] = recording_wrapper(base)
        return name
    return cd.register(rule, "rec")


# ------------------------------------------------------------------------------------------- one run
def common_row(job, out):
    batch, net, sc, rule, seed = job
    c = out["counts"]
    R = sc.ingresses
    return dict(
        batch=batch, net=net, scenario=sc.key, label=nice_label(net, sc), pilot_scenario=int(is_pilot_scenario(net, sc)),
        rule=rule, seed=seed, physics=physics_id(sc), sites=len(sc.servers), ingresses=R, W=sc.report_interval,
        frames=c["frames"], n_success=c["success"], n_late=c["late"], n_expired=c["expired"], n_rejected=c["rejected"],
        success=out["success"] * 100, rejected=out["rejected"] * 100, expired=out["expired"] * 100,
        late=out["late_completed"] * 100, mean_ms=out["mean_ms"], p99_ms=out["p99_ms"],
        offered_load=out["offered_load"], util_mean=out["util_mean"],
        bytes_per_s_per_ingress=out["bytes_per_s_per_ingress"],
        report_bytes_per_s_per_ingress=out["report_bytes_per_s"] / R,
        echo_bytes_per_s_per_ingress=out["echo_bytes_per_s"] / R, runtime_s=out["runtime_s"])


def detail_of(job, out):
    return dict(key=key_of(job), ts=out["ts"], diag=out.get("diag"), util=out["util"], share=out["share"],
                avg_queue=out["avg_queue"], max_queue=out["max_queue"])


def plain(job):
    from catsim.engine import run
    batch, net, sc, rule, seed = job
    out = run(sc, rule, seed)
    return common_row(job, out), detail_of(job, out)


def measured(job):
    """Batch B: the run with a recorder, and the measurements of feedback/phase1/run_phase1.py (measure)."""
    import numpy as np
    from catsim.engine import run
    batch, net, sc, rule, seed = job
    box = {}
    out = run(sc, register_recorder(rule), seed, hook=lambda d: box.update(d))
    created = np.asarray(box["created"])
    ing = np.asarray(box["ing"])
    dropped = np.asarray(box["dropped"], dtype=bool)
    warm, T = box["warm"], box["T"]
    R, W, mu = sc.ingresses, sc.report_interval, sc.mu
    keep = created >= warm
    span = T - warm
    cap = float(np.asarray(sc.servers, float).sum() * mu)
    # ---- drop share of each ingress: whole run, and per BIN seconds
    share = [float(dropped[keep & (ing == i)].mean()) if (keep & (ing == i)).any() else float("nan") for i in range(R)]
    edges = np.arange(warm, T + 1e-9, BIN)
    spread = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (created >= a) & (created < b)
        if dropped[m].mean() < 0.01:
            continue
        ps = [dropped[m & (ing == i)].mean() for i in range(R) if (m & (ing == i)).sum() >= 20]
        if len(ps) >= 2:
            spread.append(max(ps) - min(ps))
    # ---- what each ingress believed against the truth
    ratio, abs_err, pdrop, n_est = [], [], [], []
    for r in box["rules"]:
        rec = np.array([x[:3] for x in r.rec if x[0] >= warm], float)
        n_est.append(len(rec))
        if len(rec) == 0:
            ratio.append(float("nan"))
            abs_err.append(float("nan"))
            pdrop.append(float("nan"))
            continue
        t = rec[:, 0]
        true = (np.searchsorted(created, t, side="right") - np.searchsorted(created, t - W, side="right")) / W
        dt = np.diff(np.append(t, T))                         # each estimate holds until the next one
        q = rec[:, 1] / np.maximum(true, 1e-9)
        ratio.append(float(np.sum(q * dt) / dt.sum()))
        abs_err.append(float(np.sum(np.abs(q - 1.0) * dt) / dt.sum()))
        pdrop.append(float(np.sum(rec[:, 2] * dt) / dt.sum()))
    sent = (keep & ~dropped).sum() / span
    row = common_row(job, out)
    row["rule"] = rule                                        # the plan's name, not the recorder's
    row.update(
        admitted_over_capacity=float(sent / cap),
        share_min=float(np.nanmin(share)) * 100, share_max=float(np.nanmax(share)) * 100,
        share_by_ingress=json.dumps([round(x * 100, 3) for x in share]),
        spread_mean=float(np.mean(spread)) * 100 if spread else 0.0,
        spread_max=float(np.max(spread)) * 100 if spread else 0.0, bins_dropping=len(spread),
        est_min=float(np.nanmin(ratio)), est_max=float(np.nanmax(ratio)),
        est_by_ingress=json.dumps([round(x, 4) for x in ratio]),
        est_abs_err_by_ingress=json.dumps([round(x, 4) for x in abs_err]),     # added after the freeze (not in tables)
        plan_drop_by_ingress=json.dumps([round(x * 100, 3) for x in pdrop]),
        estimates_by_ingress=json.dumps(n_est))
    return row, detail_of(job, out)


def work(job):
    return (measured if job[0] == "B" else plain)(job)


# ------------------------------------------------------------------------------------------- running a batch
def _json_default(x):
    try:
        import numpy as np
        if isinstance(x, np.generic):
            return x.item()
        if isinstance(x, np.ndarray):
            return x.tolist()
    except ImportError:
        pass
    return str(x)


def load_journal(path):
    done = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:              # a line cut by a stop in the middle of a write
                    continue
                done[rec["key"]] = rec
    return done


def run_batch(batch, seeds, workers, limit=0):
    n_files, changed, crlf = check_frozen()
    if changed:
        raise SystemExit("frozen files differ from FREEZE_v6.1.md, nothing is run: " + ", ".join(changed))
    jobs = jobs_of(batch, seeds)
    if len(seeds) == 5 and len(jobs) != SIZES[batch]:
        raise SystemExit(f"Batch {batch} should have {SIZES[batch]} runs, the plan gives {len(jobs)}")
    work_dir = os.path.join(HERE, "_work")
    os.makedirs(work_dir, exist_ok=True)
    journal = os.path.join(work_dir, f"batch_{batch}.jsonl")
    done = load_journal(journal)
    todo = [j for j in jobs if key_of(j) not in done]
    if limit:
        todo = todo[:limit]
    print(f"Batch {batch}: {len(jobs)} runs in the plan, {len(jobs) - len([j for j in jobs if key_of(j) not in done])}"
          f" already done, {len(todo)} to run now, {workers} workers", flush=True)
    t0 = time.time()
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    if todo:
        with open(journal, "a", encoding="utf-8") as jf, get_context("spawn").Pool(workers) as pool:
            for k, (row, detail) in enumerate(pool.imap_unordered(work, todo, chunksize=1), 1):
                rec = {"key": detail["key"], "row": row, "detail": detail}
                jf.write(json.dumps(rec, default=_json_default) + "\n")
                jf.flush()
                done[rec["key"]] = rec
                if k % 25 == 0 or k == len(todo):
                    print(f"  {k}/{len(todo)}  {time.time() - t0:.0f} s", flush=True)
    missing = [key_of(j) for j in jobs if key_of(j) not in done]
    if missing:
        print(f"{len(missing)} runs of the plan are still missing; run the same command again", flush=True)
        return
    rows = [done[key_of(j)]["row"] for j in jobs]             # the order of the plan
    out_csv = os.path.join(HERE, f"batch_{batch}.csv")
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with gzip.open(os.path.join(HERE, f"batch_{batch}_detail.jsonl.gz"), "wt", encoding="utf-8") as f:
        for j in jobs:
            f.write(json.dumps(done[key_of(j)]["detail"], default=_json_default) + "\n")
    import numpy
    import scipy
    manifest = dict(
        batch=batch, runs=len(rows), seeds=list(seeds), scenarios=len({(r["net"], r["scenario"]) for r in rows}),
        rules=sorted({r["rule"] for r in rows}), plan="catsim.v61.plan", frozen_note="FREEZE_v6.1.md",
        frozen_files_checked=n_files, frozen_files_changed=changed, frozen_files_crlf_only=crlf,
        git_head=git("rev-parse", "HEAD"), git_tag_v61_frozen=git("rev-parse", "v6.1-frozen^{commit}"),
        python=platform.python_version(), numpy=numpy.__version__, scipy=scipy.__version__,
        platform=platform.platform(), finished=time.strftime("%Y-%m-%d %H:%M:%S"),
        last_session_started=started, last_session_runs=len(todo), last_session_wall_s=round(time.time() - t0, 1),
        runtime_sum_s=round(sum(r["runtime_s"] for r in rows), 1))
    with open(os.path.join(HERE, f"batch_{batch}_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    print(f"{len(rows)} runs -> {os.path.relpath(out_csv, ROOT)}  ({time.time() - t0:.0f} s this session)", flush=True)


def check():
    n, changed, crlf = check_frozen()
    print(f"frozen files: {n} checked, {len(changed)} changed" + (f" ({', '.join(changed)})" if changed else "")
          + (f"; {len(crlf)} with Windows line endings only" if crlf else ""))
    print(f"git HEAD {git('rev-parse', 'HEAD')}, tag v6.1-frozen {git('rev-parse', 'v6.1-frozen^{commit}')}")
    from catsim import v61
    for b in ("A", "B"):
        jobs = jobs_of(b, v61.FIRST_SEEDS)
        nets = {}
        for _, net, sc, _, _ in jobs:
            nets.setdefault(net, set()).add(sc.key)
        print(f"Batch {b}: {len(jobs)} runs (expected {SIZES[b]}); scenarios " +
              ", ".join(f"{k} {len(v)}" for k, v in nets.items()) + f"; rules {len({j[3] for j in jobs})}")
    return not changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["check", "A", "B"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--seeds", default="301-305", help="evaluation seeds, e.g. 301-305 or 301-310")
    ap.add_argument("--limit", type=int, default=0, help="run at most this many of the missing runs now")
    a = ap.parse_args()
    if a.what == "check":
        sys.exit(0 if check() else 1)
    run_batch(a.what, parse_seeds(a.seeds), a.workers, a.limit)


if __name__ == "__main__":
    main()
