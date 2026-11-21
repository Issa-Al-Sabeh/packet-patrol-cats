"""The final evaluation: Batches A, B and D on seeds 301 to 320 (catsim/final.py, FREEZE_v6.2.md).

    python3 feedback/final/run_final.py check
    python3 feedback/final/run_final.py A|B|D [--workers 2] [--max-seconds 560]

Resumable: finished runs are kept in feedback/final/_work/ and never run twice. Runs already made on seeds 301 to 305
(feedback/batches/_work/: Batches A and B, and the added rivals) are reused as they are: same code, same seed.
Run the same command again until it says the batch is complete; it then writes batch_<X>.csv and the detail file.
Batch B runs carry the estimate measurements (feedback/batches/run_batches.py, measured); A and D are plain runs.
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import sys
import time
from multiprocessing import get_context

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "batches"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "phase1"))

import run_batches as rb  # noqa: E402

OLD = os.path.join(os.path.dirname(HERE), "batches", "_work")


def check_frozen():
    """Every file of the v6.1 freeze and of the v6.2 freeze must match its fingerprint."""
    changed, n = [], 0
    for note in ("FREEZE_v6.1.md", "FREEZE_v6.2.md"):
        with open(os.path.join(ROOT, note), encoding="utf-8") as f:
            for path, want in re.findall(r"\| `([^`]+)` \| `([0-9a-f]{64})` \|", f.read()):
                n += 1
                with open(os.path.join(ROOT, path), "rb") as g:
                    raw = g.read()
                if want not in (hashlib.sha256(raw).hexdigest(), hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()):
                    changed.append(path)
    return n, changed


def work(job):
    import catsim.rules_v62  # noqa: F401  (registers ours_v62 in this worker)
    return rb.work(job)


def jobs_of(batch):
    from catsim import final
    return [(batch, net, sc, rule, sd) for net, sc, rule, sd in final.plan(batch)]


def reuse(batch, done, keys):
    """Runs of the first pass (seeds 301-305), same rule, scenario and seed: copy them into this journal."""
    src = {"A": ["batch_A.jsonl", "addendum_eval.jsonl"], "B": ["batch_B.jsonl"], "D": []}[batch]
    got = 0
    for name in src:
        for rec in rb.load_journal(os.path.join(OLD, name)).values():
            k = rec["key"].split("|", 1)[1]
            key = f"{batch}|{k}"
            if key in keys and key not in done:
                rec = dict(rec, key=key, reused_from=name)
                rec["row"] = dict(rec["row"], batch=batch)
                rec["detail"] = dict(rec["detail"], key=key)
                done[key] = rec
                got += 1
    return got


def run(batch, workers, max_seconds):
    import catsim.rules_v62  # noqa: F401
    n, changed = check_frozen()
    if changed:
        raise SystemExit("frozen files differ from FREEZE_v6.1.md / FREEZE_v6.2.md, nothing is run: " + ", ".join(changed))
    jobs = jobs_of(batch)
    keys = {rb.key_of(j) for j in jobs}
    assert len(keys) == len(jobs)
    os.makedirs(os.path.join(HERE, "_work"), exist_ok=True)
    journal = os.path.join(HERE, "_work", f"batch_{batch}.jsonl")
    done = rb.load_journal(journal)
    new = reuse(batch, done, keys)
    if new:
        with open(journal, "a", encoding="utf-8") as jf:
            for key, rec in done.items():
                if rec.get("reused_from"):
                    jf.write(json.dumps(rec, default=rb._json_default) + "\n")
    todo = [j for j in jobs if rb.key_of(j) not in done]
    print(f"Batch {batch}: {len(jobs)} runs, {len(jobs) - len(todo)} done ({new} reused now), {len(todo)} to run",
          flush=True)
    t0 = time.time()
    if todo:
        pool = get_context("spawn").Pool(workers)
        try:
            with open(journal, "a", encoding="utf-8") as jf:
                for k, (row, detail) in enumerate(pool.imap_unordered(work, todo, chunksize=1), 1):
                    rec = {"key": detail["key"], "row": row, "detail": detail}
                    jf.write(json.dumps(rec, default=rb._json_default) + "\n")
                    jf.flush()
                    done[rec["key"]] = rec
                    if k % 100 == 0:
                        print(f"  {k}/{len(todo)}  {time.time() - t0:.0f} s", flush=True)
                    if time.time() - t0 > max_seconds:
                        print(f"  stopping after {k} runs ({time.time() - t0:.0f} s); run again to continue", flush=True)
                        break
        finally:
            pool.terminate()
    missing = [rb.key_of(j) for j in jobs if rb.key_of(j) not in done]
    if missing:
        print(f"{len(missing)} runs still missing", flush=True)
        return False
    rows = [done[rb.key_of(j)]["row"] for j in jobs]
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(os.path.join(HERE, f"batch_{batch}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    with gzip.open(os.path.join(HERE, f"batch_{batch}_detail.jsonl.gz"), "wt", encoding="utf-8") as f:
        for j in jobs:
            f.write(json.dumps(done[rb.key_of(j)]["detail"], default=rb._json_default) + "\n")
    import numpy
    import platform
    import scipy
    man = dict(batch=batch, runs=len(rows), reused=sum(1 for j in jobs if done[rb.key_of(j)].get("reused_from")),
               seeds=sorted({r["seed"] for r in rows}), rules=sorted({r["rule"] for r in rows}),
               frozen_files_checked=n, frozen_files_changed=changed, git_head=rb.git("rev-parse", "HEAD"),
               python=platform.python_version(), numpy=numpy.__version__, scipy=scipy.__version__,
               finished=time.strftime("%Y-%m-%d %H:%M:%S"))
    with open(os.path.join(HERE, f"batch_{batch}_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1)
    print(f"Batch {batch} complete: {len(rows)} runs -> feedback/final/batch_{batch}.csv", flush=True)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["check", "A", "B", "D"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--max-seconds", type=float, default=1e9)
    a = ap.parse_args()
    if a.what == "check":
        n, changed = check_frozen()
        print(f"frozen files: {n} checked, {len(changed)} changed {changed if changed else ''}")
        for b in "ABD":
            print(b, len(jobs_of(b)), "runs")
        sys.exit(1 if changed else 0)
    run(a.what, a.workers, a.max_seconds)


if __name__ == "__main__":
    main()
