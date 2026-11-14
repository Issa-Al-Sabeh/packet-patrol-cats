"""Phase 1 tests of the offered-traffic estimator (python3 -m pytest feedback/phase1 -q).

1. The professor's counterexample (feedback of 11 Nov 2026): two ingresses offer 100 frames/s each, one admits half,
   the other admits all, so the sites count 150. The frozen estimator answers 300 and 150; the truth is 200.
2. The same counterexample as a simulation, for the frozen rule and for each candidate.
3. The harness itself: the candidate class with the frozen settings reproduces ours v6 exactly.
"""
import os
import sys
from dataclasses import replace

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import candidates as cd                                   # noqa: E402
from catsim.config import MAIN                            # noqa: E402
from catsim.engine import run                             # noqa: E402
from catsim.rules_v5 import OwnDrops, _offered            # noqa: E402
from catsim.v5 import build_overload                      # noqa: E402

# 2 equal ingresses, 100 frames/s each on the Beirut sites (14 GPUs x 10 frames/s = 140 frames/s)
CX = replace(MAIN, key="counterexample", ingresses=2, traffic="equal", load=200.0 / 140.0, site_discard=True,
             sim_time=80.0, warmup=20.0)
TRUTH = 200.0


def test_counterexample_arithmetic_frozen_function():
    """The frozen function itself, no simulation: 150 counted, own drop shares 0.5 and 0."""
    got = []
    for dropping in (True, False):
        own = OwnDrops()
        for k in range(100):                                  # 100 own frames in the 1-second window
            own.add((k + 0.5) / 100.0, dropping and k % 2 == 0)
        rate, seen = np.zeros(1), np.zeros(1, dtype=bool)
        _offered(own, rate, seen, 0, 150, 1.0, 1.0, 0.3)
        got.append(float(rate[0]))
    assert got == [300.0, 150.0]                              # the truth is 200: the estimate is wrong at both


def _estimates(rule):
    box = {}
    run(CX, cd.register(rule, "forced"), 7, hook=lambda d: box.update(d))
    return [float(np.mean([e for t, e in r.est if t >= box["warm"]])) for r in box["rules"]]


@pytest.mark.parametrize("rule,expect", [
    ("ours_v6", (300.0, 150.0)),          # frozen: wrong at both ingresses (documented, not fixed here)
    ("est_bound", (200.0, 150.0)),        # lower bound: right where the drops are, low where there are none
    ("est_echo", (200.0, 200.0)),         # aggregate drop counter: right at both
])
def test_counterexample_simulated(rule, expect):
    got = _estimates(rule)
    for g, e in zip(got, expect):
        assert abs(g - e) <= 0.04 * e, (rule, got)


def test_only_the_echo_estimate_is_right_at_both_ingresses():
    for rule, ok in (("ours_v6", False), ("est_bound", False), ("est_echo", True)):
        got = _estimates(rule)
        assert all(abs(g - TRUTH) <= 0.04 * TRUTH for g in got) == ok, (rule, got)


@pytest.mark.parametrize("rule", ["est_own", "est_own_plan"])
def test_harness_reproduces_frozen_v6(rule):
    o130 = [sc for sc in build_overload()[0] if sc.key == "O_130"][0]
    for sc, seed in ((MAIN, 201), (o130, 101)):
        a, b = run(sc, "ours_v6", seed), run(sc, rule, seed)
        for k in ("miss", "late", "dropped", "discarded", "p99_ms", "share"):
            assert a[k] == b[k], (rule, sc.key, k)
    assert round(run(MAIN, "est_own", 201)["miss"] * 100, 4) == 2.8937
