"""A second, LARGER network: 6 sites and 12 ingresses (run_large.py).

Purpose: check that the results of the main study hold at a bigger scale. Every rule is used EXACTLY as frozen in
round 3 (same code, same settings); nothing here was used to design or tune a rule, so the whole large study is
out-of-sample. Same physics as the main study (10 frames/s per server, Gamma job sizes, 300 ms deadline, reports
every 5 s with the 4-byte counter); only the network is bigger.
"""
from dataclasses import replace

from .config import Scenario

LARGE_SITE_NAMES = ("Hamra edge", "Achrafieh edge", "Jdeideh", "Baabda", "Jounieh", "Regional DC")

# 30 servers in total (300 frames/s). Round trip from Ingress A; the other 11 ingresses are up to 50% nearer or
# farther, so different ingresses are close to different sites.
LARGE_MAIN = Scenario(
    key="main", label="Large network: 6 sites, 12 ingresses", group="main",
    servers=(2, 2, 4, 4, 6, 12), base_delay_ms=(8.0, 10.0, 16.0, 20.0, 30.0, 60.0), delay_spread=0.5,
    ingresses=12, load=0.85, report_interval=5.0)

LARGE_SWEEPS = [   # (key, factor, value, label, change)
    ("report_interval=1", "report_interval", "1", "Reports every 1 s", dict(report_interval=1.0)),
    ("report_interval=10", "report_interval", "10", "Reports every 10 s", dict(report_interval=10.0)),
    ("load=70", "load", "70", "Load 70%", dict(load=0.70)),
    ("load=95", "load", "95", "Load 95%", dict(load=0.95)),
]

# Failures keep the total load during the event near 90-91% of what really works, like the main study.
LARGE_EVENTS = [
    ("L_server_fail", "Server failure: Jdeideh loses 2 of its 4 servers at 50 s, gets them back at 100 s",
     dict(cap_events=((50.0, 2, 2), (100.0, 2, 4)))),
    ("L_two_failures", "Two failures: Hamra edge loses 1 of 2 servers at 50 s, Baabda 1 of 4 at 70 s; both back "
     "at 120 s", dict(cap_events=((50.0, 0, 1), (70.0, 3, 3), (120.0, 0, 2), (120.0, 3, 4)))),
    ("L_dc_fail", "DC failure: the DC loses 2 of its 12 servers at 50 s, gets them back at 110 s",
     dict(cap_events=((50.0, 5, 10), (110.0, 5, 12)))),
    ("L_shared_gpus", "Shared GPUs: another app takes 2 of Baabda's 4 GPUs, 20 s on, 20 s off",
     dict(cap_events=((40.0, 3, 2), (60.0, 3, 4), (80.0, 3, 2), (100.0, 3, 4), (120.0, 3, 2), (140.0, 3, 4)))),
    ("L_wrong_weights", "Wrong weights: rules are told the DC has 12 servers, only 9 work",
     dict(servers=(2, 2, 4, 4, 6, 9), servers_known=(2, 2, 4, 4, 6, 12))),
    ("L_slow_gpus", "Slow GPUs: Jounieh's GPUs run at 70% speed from 40 s to 110 s",
     dict(speed_events=((40.0, 4, 0.7), (110.0, 4, 1.0)))),
    ("L_loss_30", "Lost reports: 30% of reports never arrive", dict(report_loss=0.30)),
]

LARGE_RULES = ["ours", "ours_v2", "ours_v2_check", "ours_v2_speed", "lsq", "timeout_sed", "prequal", "liyanage",
               "cap_random", "wrr", "wrr_speed", "oracle"]


def build_large():
    """(main, sweep points, event scenarios) of the large network."""
    sweeps = [replace(LARGE_MAIN, key=k, label=lab, group="sweep", factor=f, value=v, **chg)
              for k, f, v, lab, chg in LARGE_SWEEPS]
    events = [replace(LARGE_MAIN, key=k, label=lab, group="real", **chg) for k, lab, chg in LARGE_EVENTS]
    return LARGE_MAIN, sweeps, events


def plan_large(seeds):
    main, sweeps, events = build_large()
    out = []
    for name, scs in (("Large network: main scenario", [main]),
                      ("Large network: report interval and load", sweeps),
                      ("Large network: failures and real-life events", events)):
        out.append((name, [(sc, r, sd) for sc in scs for r in LARGE_RULES for sd in seeds]))
    return out
