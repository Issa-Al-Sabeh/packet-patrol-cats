"""Batch C diagnosis: what v6.1 believes, second by second, around the end of a burst or a failure.
Pilot seeds only (101-105). Diagnostics: the recorder never changes a decision."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from catsim.rules import RULE_CLASSES
from catsim.baselines import resolve_rule
from catsim.engine import run


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
                self.tr.append((round(float(now), 3), float(np.sum(self.rate_off)), float(self.p_drop),
                                [int(x) for x in self.meter.c]))
            return out
    name = "_trace_" + rule.replace("+", "_").replace("@", "_").replace("=", "_").replace(",", "_")
    RULE_CLASSES[name] = Rec
    return name


def trace(sc, rule, seed):
    box = {}
    out = run(sc, recorder(rule), seed, hook=lambda d: box.update(d))
    created = np.asarray(box["created"])
    r0 = box["rules"][0]
    rows = []
    for t, est, pd, c in r0.tr:
        true = ((created > t - 5.0) & (created <= t)).sum() / 5.0
        rows.append(dict(t=t, est=est, true=true, ratio=est / max(true, 1e-9), p_drop=pd, meter=c))
    return out, rows


if __name__ == "__main__":
    from catsim.v5 import build_overload
    sc = {s.key: s for s in build_overload()[0]}
    for key in sys.argv[1].split(","):
        out, rows = trace(sc[key], "ours_v61", int(sys.argv[2]))
        print(key, "success", round(out["success"] * 100, 1), "configured", sc[key].servers, "mu", sc[key].mu)
        for r in rows:
            if 40 <= r["t"] <= 150 and int(r["t"]) % 3 == 0:
                print(f"  t={r['t']:6.1f} est={r['est']:6.1f} true={r['true']:6.1f} ratio={r['ratio']:4.2f} drop={r['p_drop']:.2f} meter={r['meter']}")
