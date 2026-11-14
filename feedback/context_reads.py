"""Phase 0: which fields of the simulator context does each rule actually read?

    python3 context_reads.py --frozen /path/to/v6-frozen --out context_reads.csv

Runs every rule of Study 1 and Study 2 on short scenarios (below capacity and in overload), twice:
  1. with the engine's own guard (guard=True): a non-oracle rule that reads the true state raises;
  2. with a recording context that logs every field a rule reads (the frozen code is not changed: the recorder is
     swapped in at run time).
"""
import argparse
import csv
import os
import sys
from dataclasses import replace
from types import SimpleNamespace

READS = set()


class Recorder(SimpleNamespace):
    def __getattribute__(self, name):
        if not name.startswith("__"):
            READS.add(name)
        return super().__getattribute__(name)


LIVE_TRUTH = ["nsys", "c_now", "speed_now", "late_true"]                 # guarded by the engine
TRUE_PARAMS = ["ingress_rate", "scv", "late", "late_exp", "late_for", "mean_t", "d_known", "mu"]
CONFIG = ["S", "c", "W", "D", "report_bytes", "counter_bytes", "budget_bps", "probe_bytes"]
MECHANICS = ["frame", "rngs", "grid_ager"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sys.path.insert(0, os.path.abspath(a.frozen))
    import catsim.engine as E
    from catsim import study as st
    from catsim.config import MAIN
    from catsim.v5 import build_overload
    from catsim.v6 import V6_ALL

    frozen = st.load_frozen()
    s2 = sorted({alias for _, _, lst in st.experiments(frozen) for _, alias in lst})
    short = dict(sim_time=40.0, warmup=10.0)
    o130 = [sc for sc in build_overload()[0] if sc.key == "O_130"][0]
    sets = [("study1", [replace(MAIN, **short), replace(o130, **short)], [(r, r) for r in V6_ALL]),
            ("study2", [replace(st.make(0.9, 0.05, "steady"), **short), replace(st.make(1.3, 0.05, "steady"), **short)],
             [(al, st.resolved(al, frozen)) for al in s2])]
    rows = []
    plain = E.SimpleNamespace
    for study, scs, rules in sets:
        for alias, rule in rules:
            guard = "pass"
            try:
                for sc in scs:
                    E.run(sc, rule, 5, guard=True)
            except RuntimeError as e:
                guard = f"RAISED: {e}"
            READS.clear()
            E.SimpleNamespace = Recorder
            try:
                for sc in scs:
                    E.run(sc, rule, 5)
            finally:
                E.SimpleNamespace = plain
            got = set(READS)
            known = set(LIVE_TRUTH + TRUE_PARAMS + CONFIG + MECHANICS)
            rows.append(dict(study=study, rule=alias, run_as=rule, guard=guard,
                             live_truth=" ".join(x for x in LIVE_TRUTH if x in got),
                             true_parameters=" ".join(x for x in TRUE_PARAMS if x in got),
                             configuration=" ".join(x for x in CONFIG if x in got),
                             mechanics=" ".join(x for x in MECHANICS if x in got),
                             other=" ".join(sorted(got - known))))
            print(study, alias, "|", guard, "|", rows[-1]["live_truth"], "|", rows[-1]["true_parameters"], "|",
                  rows[-1]["other"], flush=True)
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
