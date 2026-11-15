"""Tests of ours v6.1: the aggregate drop counter and the corrected offered-traffic estimate
(python3 -m pytest tests -q). Background and numbers: feedback/estimator.md.
"""
import os
import sys
from dataclasses import replace

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from catsim import study as st                                         # noqa: E402
from catsim.baselines import resolve_rule, static_shares                # noqa: E402
from catsim.config import MAIN, Scenario                               # noqa: E402
from catsim.engine import run                                          # noqa: E402
from catsim.experiments import settings_code                           # noqa: E402
from catsim.rules import RULE_CLASSES                                  # noqa: E402

SMALL = replace(st.make(0.9, 0.05, "steady"), sim_time=40.0, warmup=10.0)
OVER = replace(st.make(1.3, 0.05, "steady"), sim_time=40.0, warmup=10.0)
# the counterexample of the feedback of 11 Nov 2026: two equal ingresses, 100 frames/s each (Beirut sites: 140/s)
CX = replace(MAIN, key="counterexample", ingresses=2, traffic="equal", load=200.0 / 140.0, site_discard=True,
             sim_time=80.0, warmup=20.0)


def _forced(name):
    """Ingress 0 drops every second frame, the other drops nothing; sent frames go by capacity round-robin.
    Only the offered-traffic estimate of the rule is exercised."""
    base = resolve_rule(name)

    class Forced(base):
        def __init__(self, ctx, i):
            super().__init__(ctx, i)
            self.cur = np.zeros(self.S)
            self.tog = False
            self.est = []

        def choose(self, now):
            if self.dirty and now >= self.last_rx + self.SETTLE:
                if hasattr(self, "_update_offered"):
                    self._update_offered()
                self.dirty = False
                self.est.append((now, float(self.rate_off.sum())))
            self.echo_out = 0
            if self.i == 0:
                self.tog = not self.tog
                if self.tog:
                    return -1, 1.0
            self.cur += self.c
            s = int(np.argmax(self.cur))
            self.cur[s] -= self.c.sum()
            return s, float("nan")
    RULE_CLASSES["_forced_" + name] = Forced
    box = {}
    run(CX, "_forced_" + name, 7, hook=lambda d: box.update(d))
    del RULE_CLASSES["_forced_" + name]
    return [float(np.mean([e for t, e in r.est if t >= box["warm"]])) for r in box["rules"]]


def test_counterexample_v6_is_wrong_and_v61_is_right():
    """One ingress admits half, the other all: the sites count 150, the truth is 200."""
    v6 = _forced("ours_v6")
    assert abs(v6[0] - 300.0) < 12 and abs(v6[1] - 150.0) < 6          # 300 and 150: wrong at both ingresses
    v61 = _forced("ours_v61")
    assert all(abs(x - 200.0) < 8 for x in v61), v61                   # within 4% of the truth at both


def test_v61_equals_v6_while_nothing_is_dropped():
    a, b = run(MAIN, "ours_v6", 201), run(MAIN, "ours_v61", 201)
    assert a["rejected"] == b["rejected"] == 0.0
    for k in ("miss", "late", "p99_ms", "share", "mean_ms"):
        assert a[k] == b[k], k
    assert round(b["miss"] * 100, 4) == 2.8937


def test_drop_threshold_of_v61():
    """v6.1 is in overload mode (may drop) from 90% of the measured capacity; v6 keeps 95% (its site limit)."""
    assert resolve_rule("ours_v61").DROP_FROM == 0.90
    assert resolve_rule("ours_v6").DROP_FROM is None and resolve_rule("ours_v6").U_LIMIT == 0.95
    sc = replace(MAIN, key="t92", load=0.93, site_discard=True, sim_time=80.0, warmup=20.0)
    old, new = run(sc, "ours_v61@DROP_FROM=0.95", 5), run(sc, "ours_v61", 5)
    assert new["rejected"] >= old["rejected"]                      # between the two thresholds only v6.1 may drop


def test_other_rules_and_run_names_are_untouched():
    """The counter is off for every other rule: no echo, the old byte count, the old run names."""
    o = run(OVER, "ours_v6", 5)
    assert o["echo_msgs"] == 0 and o["echo_bytes_per_s"] == 0.0
    assert settings_code(MAIN) == settings_code(replace(MAIN, echo_bytes=Scenario().echo_bytes))
    assert settings_code(MAIN) != settings_code(replace(MAIN, echo_bytes=4))


def test_counter_is_conserved_and_bytes_are_counted():
    """Every drop is counted once: the sums the sites report add up to the frames dropped (less the last moments)."""
    base = resolve_rule("ours_v61")
    seen = []

    class Rec(base):
        def on_report_e(self, now, s, q, g, A, X, E):
            if self.i == 0:
                seen.append((g, s, E))
            super().on_report_e(now, s, q, g, A, X, E)
    RULE_CLASSES["_rec_v61"] = Rec
    box = {}
    o = run(OVER, "_rec_v61", 5, hook=lambda d: box.update(d))
    del RULE_CLASSES["_rec_v61"]
    created, dropped = np.asarray(box["created"]), np.asarray(box["dropped"], dtype=bool)
    reported = sum(e for _, _, e in seen)
    last = max(g for g, _, _ in seen)
    W = OVER.report_interval
    assert dropped.sum() > 500
    assert reported <= dropped.sum()
    assert reported >= dropped[created < last - W].sum()               # only the newest drops are still on their way
    # bytes: every report is 62 + 4 + 2, and every count sent is 2
    S, R, T = len(OVER.servers), OVER.ingresses, box["T"]
    rounds = int(round(o["report_msgs"] / (S * R)))
    assert o["report_bytes_per_s"] == pytest.approx(rounds * S * R * (62 + 4 + 2) / T)
    assert o["echo_bytes_per_s"] == pytest.approx(o["echo_msgs"] * 2 / T)
    assert o["bytes_per_s"] == pytest.approx(o["report_bytes_per_s"] + o["echo_bytes_per_s"])
    assert o["echo_msgs"] <= R * (T / (0.25 * W)) + R                  # at most one count per ECHO_FRAC x W


@pytest.mark.parametrize("rule", ["ours_v61", "ours_v61_oldrise", "wrr+adm61", "lsq+adm61", "prequal_hcl+adm61"])
def test_v61_rules_conserve_requests_under_the_guard(rule):
    for sc in (SMALL, OVER):
        o = run(sc, rule, 5, guard=True)
        c = o["counts"]
        assert c["success"] + c["late"] + c["expired"] + c["rejected"] == c["frames"]


def test_wrapper61_matches_the_wrapper_in_what_it_admits():
    """Same admission rule, corrected estimate: nothing dropped below capacity, about 1 - 0.95/1.3 at 130%."""
    below = run(SMALL, "wrr+adm61", 3)
    plain = run(SMALL, "wrr", 3)
    assert below["rejected"] == 0.0 and below["success"] == plain["success"]
    over = run(OVER, "wrr+adm61", 3)
    assert abs(over["rejected"] - (1 - 0.95 / 1.3)) < 0.04
    assert over["echo_msgs"] > 0


def test_ingresses_drop_alike_with_the_counter():
    """With v6's own-share estimate the ingresses drop very different shares; with the counter they do not."""
    spread = {}
    for rule in ("ours_v6", "ours_v61"):
        box = {}
        run(replace(OVER, sim_time=80.0, warmup=20.0), rule, 5, hook=lambda d: box.update(d))
        created, ing, dropped = (np.asarray(box[k]) for k in ("created", "ing", "dropped"))
        keep = created >= box["warm"]
        p = [dropped[keep & (ing == i)].mean() for i in range(OVER.ingresses)]
        spread[rule] = max(p) - min(p)
    assert spread["ours_v61"] < 0.05 < spread["ours_v6"], spread


def test_static_deadline_split():
    """The static split: shares add up to 1, follow capacity at a high design load, and move away from the small
    site at a low one (pooling); it reads nothing but configuration, and with the wrapper it conserves requests."""
    box = {}
    run(replace(MAIN, sim_time=30.0, warmup=10.0), "static_deadline", 3, guard=True, hook=lambda d: box.update(d))
    ctx, r = box["ctx_rules"], box["rules"][0]
    cap = np.array(MAIN.servers, float) / sum(MAIN.servers)
    hi = static_shares(r.c, ctx.mu, ctx.late[0], 0.95)
    lo = static_shares(r.c, ctx.mu, ctx.late[0], 0.70)
    assert abs(hi.sum() - 1) < 1e-9 and abs(lo.sum() - 1) < 1e-9
    assert np.abs(hi - cap).max() <= 0.011                             # within one 1% piece of the capacity shares
    assert lo[0] < cap[0] and lo[2] > cap[2]
    assert np.array_equal(r.w, hi)
    o = run(OVER, "static_deadline+adm61", 5, guard=True)
    c = o["counts"]
    assert c["success"] + c["late"] + c["expired"] + c["rejected"] == c["frames"]
    assert abs(o["rejected"] - (1 - 0.95 / 1.3)) < 0.04


def test_evaluation_set_of_the_freeze():
    """The evaluation set fixed at the v6.1 freeze: sizes, seeds, unique scenario names, and every rule name known.
    The new network executes with the guard on and conserves requests (30 s on seed 1; its results are not read)."""
    from catsim import v61
    assert v61.EVAL_SEEDS == tuple(range(301, 311)) and v61.FIRST_SEEDS == (301, 302, 303, 304, 305)
    for batch, n_sc, n_runs in (("A", 22, 770), ("B", 14, 280)):
        scs = {"A": v61.batch_a, "B": v61.batch_b}[batch]()
        keys = [sc.key for _, sc in scs]
        assert len(scs) == n_sc and len(set(keys)) == n_sc
        assert len(v61.plan(batch)) == n_runs
        for rule, _ in {"A": v61.BATCH_A_RULES, "B": v61.BATCH_B_RULES}[batch]:
            resolve_rule(rule)
    new = v61.new_network()
    assert {sc.servers for sc in new.values()} == {(2, 3, 5, 6, 8)}
    for key, rule in (("N_130", "ours_v61"), ("N_fail", "static_deadline+adm61"), ("N_surge", "ours_v61@allow_drop=False")):
        o = run(replace(new[key], sim_time=30.0, warmup=10.0), rule, 1, guard=True)
        c = o["counts"]
        assert c["success"] + c["late"] + c["expired"] + c["rejected"] == c["frames"]
