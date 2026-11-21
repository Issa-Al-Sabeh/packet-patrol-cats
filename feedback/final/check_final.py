import sys, random, os
import pandas as pd, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, ROOT + "/feedback/batches"); sys.path.insert(0, ROOT + "/feedback/phase1"); sys.path.insert(0, ROOT + "/feedback/final")
import catsim.rules_v62
import run_batches as rb, run_final as rf
from catsim import final
ok = True
for b in "ABD":
    d = pd.read_csv(f"{ROOT}/feedback/final/batch_{b}.csv", float_precision="round_trip")
    n_sc = d.groupby(["net", "scenario"]).ngroups
    want = n_sc * d.rule.nunique() * 20
    full = len(d) == want == len(final.plan(b))
    per = d.groupby(["net", "scenario", "rule"]).seed.nunique().min() == 20
    frames = d.groupby(["net", "scenario", "seed"]).frames.nunique().max() == 1
    ends = bool((d.n_success + d.n_late + d.n_expired + d.n_rejected == d.frames).all())
    print(b, len(d), "runs; complete", full and per, "| same frames per scenario+seed", frames, "| every frame ends once", ends)
    ok &= full and per and frames and ends
# first-pass rows unchanged (reused) and equal to the earlier CSVs
for b, old in (("A", ["batch_A.csv", "batch_A_added.csv"]), ("B", ["batch_B.csv"])):
    d = pd.read_csv(f"{ROOT}/feedback/final/batch_{b}.csv", float_precision="round_trip").set_index(["net", "scenario", "rule", "seed"])
    o = pd.concat([pd.read_csv(f"{ROOT}/feedback/batches/{f}", float_precision="round_trip") for f in old]).set_index(["net", "scenario", "rule", "seed"])
    j = o[["success", "rejected", "frames"]].join(d[["success", "rejected", "frames"]], rsuffix="_n", how="inner")
    eq = bool((j.success == j.success_n).all() and (j.frames == j.frames_n).all())
    print(b, "first-pass rows reused unchanged:", len(j), eq); ok &= eq
# random re-run sample of NEW runs, and of reused runs
random.seed(2026_11_21)
bad = 0; n = 0
for b, k in (("A", 8), ("B", 4), ("D", 6)):
    d = pd.read_csv(f"{ROOT}/feedback/final/batch_{b}.csv", float_precision="round_trip").set_index(["net", "scenario", "rule", "seed"])
    jobs = rf.jobs_of(b)
    for job in random.sample(jobs, k):
        row, _ = rb.work(job); n += 1
        s = d.loc[(job[1], job[2].key, job[3], job[4])]
        diff = [c for c in ("frames", "n_success", "n_rejected", "n_late", "n_expired", "success") if not (row[c] == s[c])]
        if diff: bad += 1; print("DIFFERENT", b, job[1], job[2].key, job[3], job[4], diff)
print("re-run sample:", n, "runs,", bad, "different"); ok &= bad == 0
print("ALL CHECKS PASS" if ok else "SOME CHECK FAILED")
