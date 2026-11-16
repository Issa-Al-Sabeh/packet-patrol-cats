"""Which shares does the frozen static split (static_deadline, DESIGN_LOAD 0.95) use on each network of Batch A?

    python3 feedback/batches/check_static.py        -> tables/static_shares.csv

Written after Batch A: "static split + matched admission" gave the same runs as "round-robin + matched admission" on
the Beirut network and on the 8-site network. This script reads the shares from the rule itself (a 30-second run per
network; the run's results are not used) and counts how many 1% pieces fit under the site limits.
Nothing in catsim/ is changed.
"""
import csv
import os
import sys
from dataclasses import replace

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from catsim import v61                                                  # noqa: E402
from catsim.baselines import StaticDeadline                             # noqa: E402
from catsim.engine import run                                           # noqa: E402


def main():
    first = {}
    for net, sc in v61.batch_a():
        first.setdefault(net, sc)
    rows = []
    for net, sc in first.items():
        box = {}
        run(replace(sc, sim_time=30.0, warmup=10.0), "static_deadline", v61.FIRST_SEEDS[0],
            hook=lambda d: box.update(d))
        c = np.asarray(sc.servers, float)
        cap = c / c.sum()
        same = all(np.allclose(r.w, cap) for r in box["rules"])
        load, u, pieces = StaticDeadline.DESIGN_LOAD, StaticDeadline.U_MAX, StaticDeadline.PIECES
        step = load * c.sum() * sc.mu / pieces                          # frames/s in one piece
        fit = int(np.floor((u * c * sc.mu + 1e-9) / step).sum())        # pieces that fit under the site limits
        rows.append(dict(net=net, sites=len(c), ingresses=sc.ingresses, design_load=load, site_limit=u,
                         capacity_shares=" ".join(f"{x:.4f}" for x in cap),
                         static_shares=" ".join(f"{x:.4f}" for x in box["rules"][0].w),
                         every_ingress_uses_capacity_shares=int(same), pieces_needed=pieces, pieces_that_fit=fit))
        print(rows[-1])
    os.makedirs(os.path.join(HERE, "tables"), exist_ok=True)
    with open(os.path.join(HERE, "tables", "static_shares.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
