"""The final evaluation (Batches A to D on seeds 301 to 320), fixed with the freeze of v6.2, before any of its runs.

What is new compared with catsim/v61.py (which stays frozen and unchanged):
  * ours v6.2 (catsim/rules_v62.py, chosen on pilot seeds in feedback/batchC/) is added to Batches A and B.
  * The two rivals tuned on pilot seeds (feedback/batches/addendum.py) are in Batch A; the final one is added to
    Batch B too.
  * Batch D (below) is new.
  * Seeds 311 to 320 are ADDED AFTER THE FREEZE of v6.1 (decided on 21 Nov 2026, after the first results). They were
    never used for anything. Seeds 301 to 310 are the evaluation seeds of the v6.1 freeze.
Every run already made on seeds 301 to 305 is reused as it is (same code, same seed, same result).
"""
from dataclasses import replace

from . import v61

SEEDS = tuple(range(301, 321))
SEEDS_V61_FREEZE = tuple(range(301, 311))
SEEDS_ADDED = tuple(range(311, 321))

TUNED_1 = "wrr+adm61@U=0.9"                  # added after the freeze (addendum, rule A)
TUNED = "wrr+adm61@U=0.9,EWMA=1"             # added after the freeze (addendum, rule E): the hardest rival

BATCH_A_RULES = [r for r, _ in v61.BATCH_A_RULES] + [TUNED_1, TUNED, "ours_v62"]
BATCH_B_RULES = [r for r, _ in v61.BATCH_B_RULES] + [TUNED, "ours_v62"]
BATCH_D_RULES = ["ours_v62", "ours_v61", TUNED, "wrr+adm61", "wrr"]

# ---------------------------------------------------------------------------------------------------------------
# Batch D: does the picture hold outside what was designed for? Two checks, fixed here before any run:
#   1. FAST ON/OFF TRAFFIC (not Poisson at the scale of the reports): every 4 s, 2 s at 1.5 x the mean rate and
#      2 s at 0.5 x, the mean staying at the load. Counts over a report window are far more variable than Poisson.
#      It is also the hardest test of v6.2's change (a clear fall is taken at once).
#   2. A SECOND DEADLINE: 200 ms instead of 300 ms. On the new network the largest site's round trip (120 ms from
#      Ingress A) plus one 100 ms job no longer fits, so where the capacity is matters more.
#   Each at loads 95% and 115%, on the three networks: 12 scenarios.
# Values chosen from first principles, not tuned: on/off at 1.5/0.5 keeps every phase within the range of loads of
# Batch A (0.5 x 1.15 to 1.5 x 1.15); 200 ms is the shortest deadline already used in the v6 pilot set.
# ---------------------------------------------------------------------------------------------------------------
ONOFF_PERIOD, ONOFF_HIGH, ONOFF_LOW = 4.0, 1.5, 0.5
DEADLINE_2 = 200.0


def onoff(sc):
    T = sc.duration()
    pts, t = [], 0.0
    while t < T:
        half = ONOFF_PERIOD / 2.0
        pts += [(t, sc.load * ONOFF_HIGH), (t + half - 1e-3, sc.load * ONOFF_HIGH),
                (t + half, sc.load * ONOFF_LOW), (t + ONOFF_PERIOD - 1e-3, sc.load * ONOFF_LOW)]
        t += ONOFF_PERIOD
    return replace(sc, load_profile=tuple(pts))


def batch_d():
    """[(network, scenario)]"""
    out = []
    b, n = v61._beirut(), v61.new_network()
    for load in (0.95, 1.15):
        L = int(round(load * 100))
        base = {"beirut": replace(b["main"], load=load), "eight": v61._eight(load, "steady"),
                "new": replace(n["N_85"], load=load)}
        for net in ("beirut", "eight", "new"):
            sc = base[net]
            out.append((net, replace(onoff(sc), key=f"D_onoff_{L}", label=f"Load {L}%, fast on/off traffic",
                                     group="batchD")))
    for load in (0.95, 1.15):
        L = int(round(load * 100))
        base = {"beirut": replace(b["main"], load=load), "eight": v61._eight(load, "steady"),
                "new": replace(n["N_85"], load=load)}
        for net in ("beirut", "eight", "new"):
            out.append((net, replace(base[net], deadline_ms=DEADLINE_2, key=f"D_dl200_{L}",
                                     label=f"Load {L}%, deadline 200 ms", group="batchD")))
    return out


def plan(batch, seeds=SEEDS):
    """Every run of a batch: [(network, scenario, rule, seed)]."""
    scs, rules = {"A": (v61.batch_a, BATCH_A_RULES), "B": (v61.batch_b, BATCH_B_RULES),
                  "D": (batch_d, BATCH_D_RULES)}[batch]
    return [(net, sc, rule, sd) for net, sc in scs() for rule in rules for sd in seeds]
