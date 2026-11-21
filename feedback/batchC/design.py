"""Batch C: choosing v6.2 on pilot seeds.

    python3 feedback/batchC/design.py          pilot seeds 101-105, 22 Batch A scenarios -> pilot.csv, choice.json

What is tried (catsim/rules_v62.py): v6.1 with ONE change, in how the offered-traffic estimate comes down.
    v6.1 (no change)          ours_v61
    clear fall at once        v62c_fall   (FALL_Z = 3, the mirror of v6.1's rise test)
    lighter smoothing         v62c_w06    (OFF_W = 0.6)
    no smoothing              v62c_w10    (OFF_W = 1.0)

RULES OF THE CHOICE, WRITTEN AND COMMITTED BEFORE ANY OF THESE RUNS:
  A. Pilot seeds 101 to 105 only; the 22 scenarios of Batch A (catsim.v61.batch_a); deadline success as in the
     freeze (frames answered in time / frames generated after the warm-up).
  B. The best candidate = the highest mean success over the 22 scenarios (mean of the scenario means).
  C. It replaces v6.1 only if its gain over v6.1, paired by seed and pooled over the 22 scenarios (mean over the
     scenarios inside each seed, then Student's t on 4 degrees of freedom), has a 95% interval entirely above 0.
     Otherwise v6.2 = v6.1 unchanged, and Batch C reports that no change of this kind helped.
  D. Ties go to the order above (v6.1 first).
  E. The choice is frozen as ours_v62 (tag v6.2-frozen) before any run of it on evaluation seeds, and it is reported
     next to v6.1 as a new version. v6.1 stays frozen. Nothing is removed.
  The second cause found in the diagnosis (the capacity meter is slow to see servers come back) is NOT addressed:
  one fix only, as planned. It is reported as a known limit.
"""
import json
import math
import os
import sys
import time
from multiprocessing import get_context

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "batches"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "phase1"))

PILOT = (101, 102, 103, 104, 105)
CANDIDATES = ["ours_v61", "v62c_fall", "v62c_w06", "v62c_w10"]


def work(job):
    import catsim.rules_v62  # noqa: F401  (registers the candidates in this worker)
    import run_batches as rb
    return rb.plain(job)


def choose(df):
    import numpy as np
    from scipy import stats
    m = df.groupby(["net", "scenario", "rule"]).success.mean().groupby("rule").mean()
    means = {r: float(m[r]) for r in CANDIDATES}
    best = max(CANDIDATES, key=lambda r: (means[r], -CANDIDATES.index(r)))
    p = df.pivot_table(index=["net", "scenario", "seed"], columns="rule", values="success")
    gains = {}
    for r in CANDIDATES[1:]:
        d = (p[r] - p["ours_v61"]).groupby("seed").mean().to_numpy()
        h = float(stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / math.sqrt(len(d)))
        gains[r] = dict(mean=float(d.mean()), half=h, by_seed=[round(float(x), 3) for x in d])
    chosen = best if best != "ours_v61" and gains[best]["mean"] - gains[best]["half"] > 0 else "ours_v61"
    return dict(means=means, gains=gains, best=best, chosen=chosen, seeds=list(PILOT),
                rule="feedback/batchC/design.py docstring, rules A-E")


def main():
    import pandas as pd
    import run_batches as rb
    from catsim import v61
    n, changed, _ = rb.check_frozen()
    if changed:
        raise SystemExit("frozen files changed: " + ", ".join(changed))
    jobs = [("P", net, sc, r, sd) for net, sc in v61.batch_a() for r in CANDIDATES for sd in PILOT]
    os.makedirs(os.path.join(HERE, "_work"), exist_ok=True)
    journal = os.path.join(HERE, "_work", "pilot.jsonl")
    done = rb.load_journal(journal)
    todo = [j for j in jobs if rb.key_of(j) not in done]
    print(f"{len(jobs)} pilot runs, {len(todo)} to run", flush=True)
    t0 = time.time()
    if todo:
        with open(journal, "a", encoding="utf-8") as jf, get_context("spawn").Pool(2) as pool:
            for k, (row, detail) in enumerate(pool.imap_unordered(work, todo, chunksize=1), 1):
                jf.write(json.dumps({"key": detail["key"], "row": row, "detail": detail}, default=rb._json_default) + "\n")
                jf.flush()
                done[detail["key"]] = {"row": row}
                if k % 50 == 0 or k == len(todo):
                    print(f"  {k}/{len(todo)} {time.time() - t0:.0f} s", flush=True)
    rows = [done[rb.key_of(j)]["row"] for j in jobs]
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(HERE, "pilot.csv"), index=False)
    c = choose(df)
    c["chosen_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(HERE, "choice.json"), "w", encoding="utf-8") as f:
        json.dump(c, f, indent=1)
    print(json.dumps(c, indent=1))


if __name__ == "__main__":
    main()
