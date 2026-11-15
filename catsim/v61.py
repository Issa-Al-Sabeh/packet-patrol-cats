"""The evaluation set of ours v6.1, fixed at the freeze (FREEZE_v6.1.md, 15 Nov 2026).

Nothing in this file was run before the freeze on the seeds below, and the new network was never run at all (one
30-second run on seed 1 checks that it executes; its results are not read). The scenarios, the rules, the seeds and
the comparisons are fixed here so that they cannot follow the results.

    Batch A  where does the gain come from?           v6.1 against matched-admission rivals and its own parts
    Batch B  does the estimate hold when ingresses    unequal shares, a burst at one ingress, reports at different
             differ?                                  moments, lost reports

Networks:
    beirut   3 sites, 4 ingresses. The design network: every choice of v6.1 was made on it with seeds 101-105.
    eight    8 sites, 4 ingresses (Study 2). Used since the v6 freeze only to measure the frozen v6 and to diagnose
             the LSQ baseline (seeds 201-205). No version of v6.1 has run on it.
    new      5 sites, 6 ingresses. Defined here, never run.
"""
from dataclasses import replace

from .config import Scenario

EVAL_SEEDS = tuple(range(301, 311))          # reserved since the v6 freeze; unused until now
FIRST_SEEDS = EVAL_SEEDS[:5]                 # first pass (Batches A and B); 306-310 complete it to ten

# ---------------------------------------------------------------------------------------------------------------
# The new network. Same application as everywhere else (10 frames/s per GPU, Gamma job sizes, 300 ms deadline).
# What is new: 5 sites, 6 ingresses, reports every 3 s, and a large site that is far away. The remote DC holds a
# third of the capacity and its round trip from Ingress A is 40% of the deadline (Beirut's farthest: 20%), so
# sending by capacity alone is no longer free there. Other ingresses are up to 30% nearer or farther.
# ---------------------------------------------------------------------------------------------------------------
NEW_SITE_NAMES = ("Edge 1", "Edge 2", "Metro", "Regional DC", "Remote DC")
NEW_MAIN = Scenario(
    key="N_85", label="New network: load 85%", group="new",
    servers=(2, 3, 5, 6, 8), base_delay_ms=(6.0, 14.0, 28.0, 45.0, 120.0), delay_spread=0.3,
    ingresses=6, load=0.85, report_interval=3.0)
_BURST = ((0.0, 0.85), (60.0, 0.85), (60.5, 1.40), (80.0, 1.40), (80.5, 0.85), (150.0, 0.85))   # as in catsim/v5.py


def new_network():
    """The scenarios of the new network, by key. As in the Beirut tests, sites discard frames that are already past
    their deadline in the overload tests only."""
    over = replace(NEW_MAIN, site_discard=True)
    scs = [
        NEW_MAIN,
        replace(NEW_MAIN, key="N_95", label="New network: load 95%", load=0.95),
        replace(over, key="N_115", label="New network: load 115%", load=1.15),
        replace(over, key="N_130", label="New network: load 130%", load=1.30),
        replace(over, key="N_burst", label="New network: burst, 85% load, 140% from 60 s to 80 s", load_profile=_BURST),
        replace(NEW_MAIN, key="N_fail", label="New network: the Regional DC loses 2 of its 6 servers at 50 s, gets "
                "them back at 100 s", cap_events=((50.0, 3, 4), (100.0, 3, 6))),
        replace(over, key="N_130_stagger", label="New network: load 130%, sites report at different moments",
                load=1.30, stagger_reports=True),
        replace(over, key="N_surge", label="New network: load 95%, the largest ingress doubles its frames from 50 s "
                "to 100 s", load=0.95, surge=(0, 2.0, 50.0, 100.0)),
    ]
    return {sc.key: sc for sc in scs}


def _beirut():
    from .v5 import beirut_tests, build_overload
    return {sc.key: sc for sc in beirut_tests() + build_overload()[0]}


def _eight(load, pattern, **kw):
    from . import study as st
    return st.make(load, 0.05, pattern, **kw)


# ---------------------------------------------------------------------------------------------------------------
# Batch A
# ---------------------------------------------------------------------------------------------------------------
BATCH_A_RULES = [
    ("ours_v61", "Ours v6.1"),
    ("wrr+adm61", "Round-robin + matched admission"),
    ("static_deadline+adm61", "Static split + matched admission"),
    ("ours_v61@KAPPA=0", "v6.1 without the backlog penalty"),
    ("ours_v61@allow_drop=False", "v6.1 without dropping"),
    ("ours_v6", "Ours v6 (frozen)"),
    ("wrr", "Round-robin"),
]
BATCH_A_BEIRUT = ["main", "load=95", "O_110", "O_130", "O_150", "O_burst", "O_surge", "server_fail_recover",
                  "O_dc_half", "wrong_weights"]
BATCH_A_NEW = ["N_85", "N_95", "N_115", "N_130", "N_burst", "N_fail"]


def batch_a():
    """[(network, scenario)]"""
    b, n = _beirut(), new_network()
    eight = [_eight(ld, pat) for pat in ("steady", "bursty") for ld in (0.9, 1.1, 1.3)]
    return ([("beirut", b[k]) for k in BATCH_A_BEIRUT] + [("eight", sc) for sc in eight] +
            [("new", n[k]) for k in BATCH_A_NEW])


# ---------------------------------------------------------------------------------------------------------------
# Batch B. Every scenario is in overload for at least part of the run: the estimate only matters while frames
# are dropped.
# ---------------------------------------------------------------------------------------------------------------
BATCH_B_RULES = [
    ("ours_v61", "Ours v6.1 (drop counter)"),
    ("ours_v6", "Ours v6 (own drop share)"),
    ("wrr+adm61", "Round-robin + admission, drop counter"),
    ("wrr+adm", "Round-robin + admission, own drop share"),
]
BATCH_B_NEW = ["N_130", "N_130_stagger", "N_surge"]


def batch_b():
    """[(network, scenario)]"""
    b, n = _beirut(), new_network()
    o130 = b["O_130"]
    beirut = [
        o130,                                                             # shares 40/30/20/10%
        replace(o130, key="B_130_equal", label="Load 130%, equal shares", traffic="equal"),
        replace(o130, key="B_130_stagger", label="Load 130%, sites report at different moments", stagger_reports=True),
        replace(o130, key="B_130_loss", label="Load 130%, 30% of reports lost", report_loss=0.3),
        b["O_130_W1"],
        b["O_surge"],                                                     # one ingress doubles for 50 s
    ]
    eight = [_eight(1.3, "steady"), _eight(1.3, "shifting"), _eight(1.1, "bursty"), _eight(1.3, "steady", W=0.5),
             _eight(1.3, "steady", R=16)]
    return [("beirut", sc) for sc in beirut] + [("eight", sc) for sc in eight] + [("new", n[k]) for k in BATCH_B_NEW]


def plan(batch, seeds=FIRST_SEEDS):
    """Every run of a batch: [(network, scenario, rule, seed)]."""
    scs, rules = {"A": (batch_a, BATCH_A_RULES), "B": (batch_b, BATCH_B_RULES)}[batch]
    return [(net, sc, rule, sd) for net, sc in scs() for rule, _ in rules for sd in seeds]

