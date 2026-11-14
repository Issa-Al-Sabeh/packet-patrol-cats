"""The v6 study (run_v6.py): ours v6 = ours v5 + (A) balance unless the plan clearly wins, (B) react to bursts between
reports, (C) the corrected risk for the shares too. See rules_v6.py.

Tests: the same 61 tests as the v5 study (36 Beirut, 11 Beirut overload, 12 large network, 2 large overload), physics
unchanged.

SEEDS. Everything in the final study runs on FRESH seeds 201-210, every rule included (v5 and the rivals are re-run),
because v6 was designed after looking at v5's results on seeds 1-10. Pilot: spare seeds 101-105 only. Seed 999 was
used to test the code (as in the v5 study); on it, the plan's predicted gain over the balanced split was 0.5-5% in
the Beirut tests and 8-10% in the large network, so the candidate thresholds for change A are 2, 5, 10 and 25%
(the first idea, 10/25/50%, would have meant "always balance").

PILOT DECISION RULE (written 1 Nov 2026, before any pilot run):
  1. GAIN (change A) is chosen among 0.02, 0.05, 0.10 and 0.25. For each pilot test, the regret of a candidate is
     its miss rate minus the lowest of the four candidates. Keep the candidate with the lowest average regret over
     the pilot tests; within 0.01 points, keep the larger one (it trusts the model less).
  2. If the chosen v6 misses clearly more than ours v5 or round-robin + measured speeds in a pilot test (paired 95%
     CI over the 5 spare seeds), look into it before freezing, and disclose any change.
  3. Then v6 is frozen (GAIN written into rules_v6.SplitV6): no change after the full study has started.
PILOT OUTCOME (1 Nov 2026, spare seeds 101-105): average regret G=2% 0.546, G=5% 0.205, G=10% 0.225, G=25% 0.082
  -> GAIN = 0.25 (rule 1). Rule 2: never clearly worse than ours v5 or round-robin + measured speeds. v6 frozen.
  The 97 pilot runs saved before an interruption were made with the same code and were kept.
Pilot tests: the 8 pilot tests of the v5 study plus three Beirut sweep points where round-robin beat v5 (reports
every 30 s, 2 ingresses, 200 ms deadline). Never the held-out scenarios, never the large network.
"""
from .v5 import beirut_tests, build_overload, large_tests

V6_RULES = ["ours_v6", "ours_v5", "ours_v2_speed", "v4", "wrr", "wrr_speed", "wrr_drop", "wrr_speed_drop", "lsq",
            "oracle"]
V6_ABLATIONS = ["ours_v6_nobal", "ours_v6_noburst", "ours_v6_nocal"]
V6_EXTRA = ["expected_delay_drop", "v4_nodrop"]          # only in the overload tests and the two main scenarios
V6_ALL = V6_RULES[:-1] + V6_ABLATIONS + V6_EXTRA + V6_RULES[-1:]

PILOT_GAINS = ["ours_v6_g02", "ours_v6_g05", "ours_v6_g10", "ours_v6_g25"]
PILOT_RULES_V6 = PILOT_GAINS + ["ours_v5", "wrr_speed", "wrr", "v4", "wrr_speed_drop"]
PILOT_SEEDS_V6 = (101, 102, 103, 104, 105)
PILOT_TESTS_V6 = ["main", "load=95", "server_fail_recover", "shared_gpus", "wrong_weights", "report_interval=0.2",
                  "O_130", "O_burst", "report_interval=30", "ingresses=2", "deadline=200"]
FINAL_SEEDS = tuple(range(201, 211))

SHORT_V6 = {"ours_v6": "Ours v6", "ours_v6_nobal": "v6 without A (balance)", "ours_v6_noburst": "v6 without B (bursts)",
            "ours_v6_nocal": "v6 without C (corrected risk)", "ours_v5": "Ours v5", "ours_v2_speed": "Ours v2 + speeds",
            "v4": "v4 (ported)", "v4_nodrop": "v4 no drop", "wrr": "Round-robin", "wrr_speed": "RR + speeds",
            "wrr_drop": "RR + drop", "wrr_speed_drop": "RR + speeds + drop", "lsq": "LSQ-style",
            "expected_delay_drop": "Exp. delay + drop", "oracle": "Oracle",
            "ours_v6_g02": "v6 G=2%", "ours_v6_g05": "v6 G=5%", "ours_v6_g10": "v6 G=10%", "ours_v6_g25": "v6 G=25%"}


def plan_v6(seeds=FINAL_SEEDS):
    beirut = beirut_tests()
    o_b, o_l = build_overload()
    large = large_tests()

    def tasks(scs, rules):
        return [(sc, r, sd) for sc in scs for r in rules for sd in seeds]

    main_rules = V6_RULES + V6_ABLATIONS
    return [
        ("Beirut main scenario", tasks(beirut[:1], V6_ALL)),
        ("Beirut: the other 35 tests", tasks(beirut[1:], main_rules)),
        ("Beirut: 11 overload tests", tasks(o_b, V6_ALL)),
        ("Large network: main scenario", tasks(large[:1], V6_ALL)),
        ("Large network: the other 11 tests", tasks(large[1:], main_rules)),
        ("Large network: 2 overload tests", tasks(o_l, V6_ALL)),
    ]


def plan_pilot_v6():
    pool = {sc.key: sc for sc in beirut_tests() + build_overload()[0]}
    scs = [pool[k] for k in PILOT_TESTS_V6]
    return [("Pilot of v6: spare seeds 101-105", [(sc, r, sd) for sc in scs for r in PILOT_RULES_V6
                                                   for sd in PILOT_SEEDS_V6])]
