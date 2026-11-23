"""Diagnostics only: record what each ingress believes and plans, second by second. Never changes a decision.

    python3 feedback/revision/trace.py A|B <scenario> <rule> <seed>

Writes feedback/revision/traces/trace_<batch>_<scenario>_<rule>_<seed>.json and checks that the run's deadline
success equals the stored one exactly:
  - seed 301 and Batch B: feedback/final/batch_B.csv
  - seed 101 (pilot): feedback/batchC/pilot.csv, where the frozen ours_v62 is the candidate v62c_fall
The recorder wraps the frozen rule and only reads its state after each decision (catsim/engine.py, hook).
"""
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TRACES = os.path.join(HERE, "traces")
sys.path.insert(0, ROOT)
from catsim.rules import RULE_CLASSES      # noqa: E402
from catsim.baselines import resolve_rule  # noqa: E402
from catsim.engine import run              # noqa: E402
from catsim import v61                     # noqa: E402
import catsim.rules_v62                    # noqa: E402,F401  (registers ours_v62)

PILOT_NAME = {"ours_v62": "v62c_fall"}     # the candidate chosen in feedback/batchC/ and frozen as ours_v62


def recorder(rule):
    base = resolve_rule(rule)

    class Rec(base):
        def __init__(self, ctx, i):
            super().__init__(ctx, i)
            self.tr, self._next = [], 0.0

        def choose(self, now):
            out = super().choose(now)
            if now >= self._next:
                self._next = np.floor(now) + 1.0
                p = getattr(self, 'p', None)
                self.tr.append(dict(t=float(now), est=float(np.sum(self.rate_off)), pd=float(self.p_drop),
                                    kcal=float(getattr(self, 'kcal', np.nan)),
                                    cal=bool(getattr(self, 'calibrated', False)),
                                    meter=[int(x) for x in self.meter.c],
                                    p=None if p is None else [float(x) for x in p]))
            return out

    name = "_rec_" + rule.replace("+", "_").replace("@", "_").replace("=", "_").replace(",", "_")
    RULE_CLASSES[name] = Rec
    return name


def stored_success(batch, key, rule, seed):
    """Deadline success (%) of the same run in the stored results, or None."""
    if batch == "B" and seed in range(301, 321):
        path, want = os.path.join(ROOT, "feedback", "final", "batch_B.csv"), (key, rule, str(seed))
    elif seed in range(101, 106):
        path, want = os.path.join(ROOT, "feedback", "batchC", "pilot.csv"), (key, PILOT_NAME.get(rule, rule), str(seed))
    else:
        return None
    for r in csv.DictReader(open(path)):
        if (r["scenario"], r["rule"], r["seed"]) == want:
            return float(r["success"])
    return None


def go(batch, key, rule, seed):
    scs = dict((sc.key, sc) for net, sc in (v61.batch_a() if batch == 'A' else v61.batch_b()))
    sc = scs[key]
    box = {}
    out = run(sc, recorder(rule), seed, hook=lambda d: box.update(d))
    return sc, out, box


if __name__ == '__main__':
    batch, key, rule, seed = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    sc, out, box = go(batch, key, rule, seed)
    created = np.asarray(box['created']); site = np.asarray(box['site_of']); dropped = np.asarray(box['dropped'])
    S = len(sc.servers); T = box['T']
    res = dict(batch=batch, key=key, rule=rule, seed=seed, success=out['success'], servers=list(sc.servers),
               mu=getattr(sc, 'mu', None))
    # frames sent to each site per second (not dropped), and frames offered per second
    secs = np.arange(int(box['warm']), int(T))
    real = np.zeros((len(secs), S)); offered = np.zeros(len(secs))
    for k, t in enumerate(secs):
        m = (created >= t) & (created < t + 1)
        offered[k] = m.sum()
        for s in range(S):
            real[k, s] = (m & (site == s) & ~dropped).sum()
    res['secs'] = secs.tolist(); res['real'] = real.tolist(); res['offered'] = offered.tolist()
    res['rules'] = [r.tr for r in box['rules']]
    os.makedirs(TRACES, exist_ok=True)
    fn = f'trace_{batch}_{key}_{rule.replace("@", "_").replace(",", "_")}_{seed}.json'
    json.dump(res, open(os.path.join(TRACES, fn), 'w'))
    got = out['success'] * 100
    ref = stored_success(batch, key, rule, seed)
    same = "no stored run to compare" if ref is None else \
        f"stored {ref:.4f}: {'identical' if abs(ref - got) < 1e-9 else 'DIFFERENT'}"
    print(f"{key} {rule} seed {seed}: success {got:.4f}% ({same}) -> traces/{fn}")
