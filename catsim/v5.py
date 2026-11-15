"""The v5 study (run_v5.py): ours v5 against ours v2 + measured speeds, the teammate's v4 (ported), and versions of
the strongest rivals that may also drop frames.

Four groups of tests, 61 in all:
  * the 36 tests of the main study (Beirut network), with the physics of round 3 unchanged;
  * 11 OVERLOAD tests on the Beirut network: more traffic than the sites can serve, for a while or all the time.
    Here the sites are deadline-aware (a frame whose deadline has passed is discarded instead of served), for every
    rule, as in v4's own stress test; one test keeps the old sites that serve every frame;
  * the 12 tests of the large network (6 sites, 12 ingresses), physics unchanged;
  * 2 overload tests on the large network.
Pilot: spare seeds 101-105 on 8 of these tests (never the held-out ones, never the large network). The large network
and 9 of the 11 Beirut overload tests are never used to design or tune v5.

PILOT DECISION RULE (written 31 Oct 2026, before any pilot run):
  * keep ours_v5 (calibrated) unless ours_v5_raw has a lower miss rate in MORE of the 8 pilot tests than it has a
    higher one; on a tie, keep the calibrated version. The other version is then removed from the study;
  * if the chosen version misses clearly more than ours v2 + speeds in a below-capacity pilot test, look into it
    before freezing, and disclose any change in the report;
  * then v5 is frozen: no change after the full study has started.
"""
from dataclasses import replace

from .config import MAIN, build_held_out, build_real_life, build_scenarios
from .large import LARGE_MAIN, build_large

# ---------------------------------------------------------------------------------------------- rules
V5_RULES = ["ours_v5", "ours_v2_speed", "v4", "wrr", "wrr_speed", "wrr_drop", "wrr_speed_drop", "lsq", "oracle"]
V5_EXTRA = ["expected_delay_drop", "v4_nodrop"]       # only in the overload tests and the two main scenarios
V5_ALL = V5_RULES[:-1] + V5_EXTRA + V5_RULES[-1:]
PRACTICAL_V5 = [r for r in V5_ALL if r != "oracle"]
DROPPERS = ["ours_v5", "ours_v5_raw", "v4", "wrr_drop", "wrr_speed_drop", "expected_delay_drop"]

# pass 1 also had "ours_v5_raw"; the decision rule kept the calibrated version (raw lower in 1 test, higher in 6)
PILOT_RULES_V5 = ["ours_v5", "ours_v2_speed", "v4", "wrr", "wrr_drop", "wrr_speed_drop"]
PILOT_SEEDS_V5 = (101, 102, 103, 104, 105)            # never used in the report
PILOT_TESTS_V5 = ["main", "load=95", "server_fail_recover", "shared_gpus", "wrong_weights", "report_interval=0.2",
                  "O_130", "O_burst"]

LABELS_V5 = {
    "ours_v5": "Ours v5 (v2 + speeds + drop option)",
    "ours_v5_raw": "Ours v5 without calibration (pilot only)",
    "v4": "v4 (teammate, ported)",
    "v4_nodrop": "v4 without dropping",
    "wrr_drop": "Round-robin + drop the excess",
    "wrr_speed_drop": "Round-robin + speeds + drop the excess",
    "expected_delay_drop": "Expected delay + drop if over deadline",
}
SHORT_V5 = {"ours_v5": "Ours v5", "ours_v5_raw": "v5 raw", "ours_v2_speed": "Ours v2 + speeds", "v4": "v4",
            "v4_nodrop": "v4 no drop", "wrr": "Round-robin", "wrr_speed": "RR + speeds", "wrr_drop": "RR + drop",
            "wrr_speed_drop": "RR + speeds + drop", "lsq": "LSQ-style", "expected_delay_drop": "Exp. delay + drop",
            "oracle": "Fresh-state greedy"}
DESCRIBE_V5 = {
    "ours_v5": "Ours v2 + measured speeds, with DROP as one more option in the plan, costing exactly one miss, "
               "available only in overload (offered traffic above 95% of the measured capacity; never below it, "
               "like v4). "
               "Each 1% of the traffic goes where it adds the fewest expected late frames (its own chance of being "
               "late + the harm to the others + the backlog it leaves); if every site costs more than one miss, it "
               "is dropped. Offered traffic = counted arrivals / (1 - drop share). Never plans a site that would be "
               "late even when empty. The send-or-drop comparison uses the risk scaled by late / predicted over the "
               "ingress's own answers. While it drops nothing it sends exactly like v2 + measured speeds.",
    "ours_v5_raw": "Ours v5 without the calibration (pilot only).",
    "ours_v2_speed": "The final rule of round 3: the risk-based split with measured speeds and the backlog cost. "
                     "Never drops; when every site is at 95% it shares the rest by capacity.",
    "v4": "The teammate's rule, ported from its report. Below capacity: least (reported queue + k x own sends since) "
          "per unit of speed, never drops. Overloaded (traffic incl. k x own drops > capacity): queue estimate "
          "now + its spread; score = miss chance + harm (chance every server is busy); drops when the best score "
          "> 1.05. Configured capacities (no meter).",
    "v4_nodrop": "v4 with dropping turned off.",
    "wrr": "Takes turns in proportion to the configured capacity. Never drops.",
    "wrr_speed": "Round-robin with the measured speeds of ours as weights. Never drops.",
    "wrr_drop": "Round-robin that drops just enough frames to keep what it sends at 95% of the configured capacity "
                "(offered traffic estimated exactly as in ours v5). Same as round-robin below 95%.",
    "wrr_speed_drop": "Round-robin + measured speeds that drops the traffic above 95% of the MEASURED capacity "
                      "instead of topping up. Same as round-robin + measured speeds while it drops nothing.",
    "lsq": "Last report plus own frames sent since, per server; the lowest. Never drops. (The best rule of the main "
           "study after round-robin and ours.)",
    "expected_delay_drop": "Expected delay on the belief of ours v1; drops a frame when even the lowest expected "
                           "response time is over the deadline (the strongest rival of v4 in v4's own report).",
    "oracle": "Sees the true queues, servers and speeds; lowest risk. Never drops. A reference for the tests "
              "below capacity; in overload the reference is the capacity bound instead.",
}

# ---------------------------------------------------------------------------------------------- tests
BURST = ((0.0, 0.85), (60.0, 0.85), (60.5, 1.40), (80.0, 1.40), (80.5, 0.85), (150.0, 0.85))
OVERLOAD = [   # (key, label, change); deadline-aware sites unless the change says otherwise
    ("O_100", "Load 100% (all the capacity)", dict(load=1.00)),
    ("O_110", "Load 110%", dict(load=1.10)),
    ("O_130", "Load 130%", dict(load=1.30)),
    ("O_150", "Load 150%", dict(load=1.50)),
    ("O_burst", "Burst: 85% load, 140% from 60 s to 80 s", dict(load_profile=BURST)),
    ("O_rush", "Rush hour: load 60% to 120% and back over 5 minutes",
     dict(sim_time=300.0, load=0.60,
          load_profile=((0.0, 0.60), (60.0, 0.60), (120.0, 1.20), (180.0, 1.20), (240.0, 0.60), (300.0, 0.60)))),
    ("O_surge", "Incident: Ingress A doubles its frames from 50 s to 100 s (load 119%)",
     dict(surge=(0, 2.0, 50.0, 100.0))),
    ("O_dc_half", "DC failure: the DC loses 4 of its 8 servers from 50 s to 110 s (119% of what works)",
     dict(cap_events=((50.0, 2, 4), (110.0, 2, 8)))),
    ("O_130_W1", "Load 130%, reports every 1 s", dict(load=1.30, report_interval=1.0)),
    ("O_130_W10", "Load 130%, reports every 10 s", dict(load=1.30, report_interval=10.0)),
    ("O_130_nodiscard", "Load 130%, sites serve every frame (no discard)", dict(load=1.30, site_discard=False)),
]
LARGE_OVERLOAD = [
    ("L_O_130", "Large network: load 130%", dict(load=1.30)),
    ("L_O_burst", "Large network: burst, 85% load, 140% from 60 s to 80 s", dict(load_profile=BURST)),
]

GROUP_TITLES = {"main": "Beirut: main scenario", "sweep": "Beirut: sweeps", "stress": "Beirut: stress tests",
                "real": "Beirut: real-life scenarios", "heldout": "Beirut: held-out scenarios",
                "overload": "Beirut: overload tests", "L_main": "Large network: main scenario",
                "L_sweep": "Large network: report interval and load", "L_real": "Large network: failures and events",
                "L_overload": "Large network: overload tests"}
FAMILY = {"main": "beirut", "sweep": "beirut", "stress": "beirut", "real": "beirut", "heldout": "beirut",
          "overload": "overload", "L_main": "large", "L_sweep": "large", "L_real": "large", "L_overload": "overload"}
FAMILY_TITLES = {"beirut": "Beirut, 36 tests of the main study", "large": "Large network, 12 tests",
                 "overload": "Overload, 13 tests (11 Beirut + 2 large)"}


def is_large(sc):
    return len(sc.servers) == len(LARGE_MAIN.servers)


def test_id(sc):
    """Unique id of a test across both networks (the scenario keys of the two networks overlap)."""
    return ("L:" + sc.key) if is_large(sc) else sc.key


def build_overload():
    beirut = [replace(MAIN, key=k, label=lab, group="overload", **dict(dict(site_discard=True), **chg))
              for k, lab, chg in OVERLOAD]
    large = [replace(LARGE_MAIN, key=k, label=lab, group="L_overload", **dict(dict(site_discard=True), **chg))
             for k, lab, chg in LARGE_OVERLOAD]
    return beirut, large


def beirut_tests():
    """The 36 tests of the main study, in report order (each scenario once)."""
    main, sweeps, stress = build_scenarios()
    out, seen = [main], {main.key}
    for _, (_, _, pts) in sweeps.items():
        for sc in pts:
            if sc.key not in seen:
                seen.add(sc.key)
                out.append(sc)
    return out + stress + build_real_life(main) + build_held_out(main)


def large_tests():
    main, sweeps, events = build_large()
    return ([replace(main, group="L_main")] + [replace(sc, group="L_sweep") for sc in sweeps] +
            [replace(sc, group="L_real") for sc in events])


def all_tests():
    o_b, o_l = build_overload()
    return beirut_tests() + o_b + large_tests() + o_l


def plan_v5(seeds, quick=False):
    """The study as ordered steps: (step name, [(scenario, rule, seed), ...])."""
    beirut = beirut_tests()
    o_b, o_l = build_overload()
    large = large_tests()

    def tasks(scs, rules):
        return [(sc, r, sd) for sc in scs for r in rules for sd in seeds]

    steps = [("Beirut main scenario: all rules", tasks(beirut[:1], V5_ALL))]
    if quick:
        steps.append(("Overload: load 130% (quick)", tasks([o_b[2]], V5_ALL)))
        return steps
    steps += [
        ("Beirut: the other 35 tests of the main study", tasks(beirut[1:], V5_RULES)),
        ("Beirut: 11 overload tests", tasks(o_b, V5_ALL)),
        ("Large network: main scenario", tasks(large[:1], V5_ALL)),
        ("Large network: the other 11 tests", tasks(large[1:], V5_RULES)),
        ("Large network: 2 overload tests", tasks(o_l, V5_ALL)),
    ]
    return steps


def plan_pilot_v5():
    pool = {sc.key: sc for sc in beirut_tests() + build_overload()[0]}
    scs = [pool[k] for k in PILOT_TESTS_V5]
    return [("Pilot of v5: spare seeds 101-105 (not used in the report)",
             [(sc, r, sd) for sc in scs for r in PILOT_RULES_V5 for sd in PILOT_SEEDS_V5])]
