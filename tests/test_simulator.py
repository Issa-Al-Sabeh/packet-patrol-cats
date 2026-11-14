"""Unit and integration tests for the staleness-aware CATS study (python3 -m pytest tests -q).

They check the engine (determinism, conservation, deadline classes, queues, telemetry delay/age, byte accounting,
common traces, true-state isolation, per-ingress state), the admission wrapper, and each baseline on small cases whose
right answer is known by hand. The M/M/c check against Erlang C uses the existing catsim/checks.py.
"""
import math
import os
import sys
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from catsim import study as st                                         # noqa: E402
from catsim.baselines import (CatsLB, DahlinLI, Liyanage26, OracleAdm, PrequalHCL, dahlin_fill,   # noqa: E402
                              expand_table, resolve_rule)
from catsim.config import MAIN                                          # noqa: E402
from catsim.engine import run                                           # noqa: E402
from catsim.rules import WRR, Nearest, LSQ, Rule                        # noqa: E402

SMALL = replace(st.make(0.9, 0.05, "steady"), sim_time=40.0, warmup=10.0)
OVER = replace(st.make(1.3, 0.05, "steady"), sim_time=40.0, warmup=10.0)
ALL = st.MAIN_RULES + st.SUPP_RULES + ["oracle_adm", "wrr+adm", "lsq+adm", "prequal_hcl+adm", "liyanage26+adm"] + st.ABLATIONS


def _frames(sc, rule, seed=7, **kw):
    box = {}
    out = run(sc, rule, seed, hook=lambda d: box.update(d), **kw)
    return out, box


# ------------------------------------------------------------------------------------------------ engine
def test_regression_v6_reproduces_saved_study():
    """The engine extensions must not change any earlier run: ours v6, main Beirut scenario, seed 201 (summary_v6)."""
    o = run(MAIN, "ours_v6", 201)
    assert round(o["miss"] * 100, 4) == 2.8937


def test_deterministic_same_seed():
    a = run(SMALL, "ours_v6", 3)
    b = run(SMALL, "ours_v6", 3)
    for k in ("success", "late_completed", "expired", "rejected", "bytes_per_s", "p99_ms", "aoi_mean_s", "ts"):
        assert a[k] == b[k]


@pytest.mark.parametrize("rule", ALL)
def test_conservation_and_guard(rule):
    """Every rule runs with the true-state guard (non-oracle rules would raise); each frame ends exactly once."""
    for sc in (SMALL, OVER):
        o = run(sc, rule, 5, guard=True)
        c = o["counts"]
        assert c["success"] + c["late"] + c["expired"] + c["rejected"] == c["frames"]
        assert abs(o["success"] + o["late_completed"] + o["expired"] + o["rejected"] - 1.0) < 1e-12


def test_guard_catches_a_cheating_rule():
    from catsim.rules import RULE_CLASSES

    class Cheat(Rule):
        uses_reports = False

        def choose(self, now):
            return int(np.argmin(self.ctx.nsys)), float("nan")
    RULE_CLASSES["_cheat"] = Cheat
    with pytest.raises(RuntimeError):
        run(SMALL, "_cheat", 1, guard=True)
    run(SMALL, "_cheat", 1)                         # without the guard it would silently use the true state
    del RULE_CLASSES["_cheat"]


def test_deadline_classification():
    o, f = _frames(OVER, "wrr")
    D, warm = f["D"], f["warm"]
    n_s = n_l = n_e = n_r = 0
    for k, t0 in enumerate(f["created"]):
        if t0 < warm:
            continue
        if f["dropped"][k]:
            n_r += 1
        elif f["discarded"][k]:
            n_e += 1
            assert not math.isnan(f["arr_t"][k]) and math.isnan(f["start_t"][k])   # discarded before service
        elif f["finish"][k] - t0 > D:
            n_l += 1
        else:
            n_s += 1
    c = o["counts"]
    assert (n_s, n_l, n_e, n_r) == (c["success"], c["late"], c["expired"], c["rejected"])
    assert n_e > 0 and n_l > 0                                                   # overload: both kinds occur


def test_common_workload_traces():
    _, a = _frames(SMALL, "wrr")
    _, b = _frames(SMALL, "ours_v6")
    _, c = _frames(SMALL, "prequal_hcl")
    assert a["created"] == b["created"] == c["created"]
    assert a["size"] == b["size"] == c["size"]
    assert a["ing"] == b["ing"] == c["ing"]
    assert np.array_equal(a["d_true"], b["d_true"])


def test_fcfs_queue_and_capacity():
    """At most c frames in service per site at any time; service starts in arrival order (FCFS)."""
    sc = replace(SMALL, site_discard=False)
    _, f = _frames(sc, "wrr")
    for s in range(8):
        idx = [k for k in range(len(f["created"])) if f["site_of"][k] == s]
        idx.sort(key=lambda k: f["arr_t"][k])
        starts = [f["start_t"][k] for k in idx]
        assert all(starts[j] <= starts[j + 1] + 1e-12 for j in range(len(starts) - 1))
        ev = []
        for k in idx:
            ev.append((round(f["start_t"][k], 9), 1))                     # 1 ns resolution: rebuilding the end
            ev.append((round(f["finish"][k] - f["d_true"][f["ing"][k]][s] / 2, 9), -1))   # time adds float noise
        ev.sort(key=lambda e: (e[0], e[1]))
        busy, peak = 0, 0
        for _, dlt in ev:
            busy += dlt
            peak = max(peak, busy)
        assert peak <= sc.servers[s]


def test_mmc_against_erlang_c():
    from catsim.checks import mmc_mean
    sc = replace(MAIN, key="t_mmc", servers=(4,), base_delay_ms=(0.0,), ingresses=1, job_shape="exp", job_scv=1.0,
                 load=0.8, sim_time=3000.0)
    sims = [run(sc, "nearest", sd)["mean_ms"] / 1000 for sd in (1, 2, 3)]
    th = mmc_mean(4, 10.0, 0.8 * 40.0)
    assert abs(np.mean(sims) - th) / th < 0.03


def test_telemetry_delay_shifts_age_exactly():
    """With the same frames, adding 1 s of report delay raises the mean age of the telemetry used by about 1 s."""
    a = run(replace(SMALL, report_delay_s=0.0), "wrr_speed", 4)
    b = run(replace(SMALL, report_delay_s=1.0), "wrr_speed", 4)
    assert 0.9 < b["aoi_mean_s"] - a["aoi_mean_s"] < 1.1
    W = SMALL.report_interval
    assert b["aoi_p95_s"] <= W + 1.0 + 0.06 + 1e-6                     # interval + delay + longest one-way trip


def test_report_bytes_accounting():
    o = run(SMALL, "ours_v6", 2)                                        # reports with the 4-byte counter
    S, R, W, T = 8, 4, SMALL.report_interval, SMALL.sim_time
    rounds = sum(1 for k in range(1, 1000) if k * W < T - 1e-9)          # reports at W, 2W, ... < T
    assert o["report_bytes_per_s"] == pytest.approx(rounds * S * R * (62 + 4) / T)
    o2 = run(SMALL, "lsq", 2)                                           # no counter
    assert o2["report_bytes_per_s"] == pytest.approx(rounds * S * R * 62 / T)
    o3 = run(SMALL, "wrr", 2)                                           # no telemetry
    assert o3["bytes_per_s"] == 0


def test_probe_budget_matches_reports():
    o = run(SMALL, "prequal_hcl", 2)
    target = 8 * (62 + 4) / SMALL.report_interval
    assert o["report_bytes_per_s"] == 0
    assert abs(o["bytes_per_s_per_ingress"] - target) / target < 0.05


def test_threshold_reporting_sends_fewer_and_keeps_randomness():
    th = replace(SMALL, report_mode="threshold", report_threshold=1.0)
    a = run(SMALL, "ours_v6", 2)
    b = run(th, "ours_v6", 2)
    assert b["report_msgs"] < a["report_msgs"]
    assert 0 < b["report_rounds_sent"] < 1
    huge = replace(SMALL, report_mode="threshold", report_threshold=0.0)  # threshold 0 = send every round
    c = run(huge, "ours_v6", 2)
    assert c["report_msgs"] == a["report_msgs"] and c["success"] == a["success"]


def test_measurement_noise_changes_reports_only():
    a, fa = _frames(SMALL, "lsq", 6)
    b, fb = _frames(replace(SMALL, report_noise_sd=3.0), "lsq", 6)
    assert fa["created"] == fb["created"]
    assert b["est_err_mean"] > a["est_err_mean"]


def test_independent_ingress_state():
    _, f = _frames(SMALL, "lsq")
    rules = f["rules"]
    assert len({id(r) for r in rules}) == len(rules)
    assert len({id(r.q) for r in rules}) == len(rules)                  # no shared queue table
    sent = [sum(len(x) for x in r.log) for r in rules]
    assert len(set(sent)) > 1                                           # each counts only its own sends


def test_shifting_traffic_moves_between_ingresses():
    sc = replace(st.make(0.9, 0.05, "shifting"), sim_time=60.0, warmup=0.0)
    _, f = _frames(sc, "wrr")
    t = np.array(f["created"])
    ing = np.array(f["ing"])
    first = np.bincount(ing[t < 20], minlength=4)
    second = np.bincount(ing[(t >= 20) & (t < 40)], minlength=4)
    assert np.argmax(first) != np.argmax(second)


def test_bursty_average_load():
    sc = st.make(0.9, 0.05, "bursty")
    o = run(sc, "wrr", 3)
    assert abs(o["offered_load"] - 0.9) < 0.04


def test_network_delay_change_event():
    """Network delay change (path_event): while it lasts, every trip to that site takes `factor` times as long. The
    frames, jitter and WRR's choices do not depend on it, so arrival times differ by exactly the extra one-way delay."""
    ev = (7, 2.0, 20.0, 30.0)
    _, a = _frames(SMALL, "wrr")
    _, b = _frames(replace(SMALL, path_event=ev), "wrr")
    assert list(a["site_of"]) == list(b["site_of"])
    n_in = n_out = 0
    for k, t0 in enumerate(a["created"]):
        if a["site_of"][k] != 7:
            continue
        extra = b["arr_t"][k] - a["arr_t"][k]
        one_way = a["d_true"][a["ing"][k]][7] / 2.0
        if ev[2] <= t0 < ev[3]:
            assert abs(extra - one_way * (ev[1] - 1.0)) < 1e-9
            n_in += 1
        else:
            assert abs(extra) < 1e-9
            n_out += 1
    assert n_in > 50 and n_out > 50


def test_admission_wrapper_does_not_change_routing_below_capacity():
    sc = replace(st.make(0.6, 0.05, "steady"), sim_time=40.0, warmup=10.0)
    for r in ("wrr", "lsq", "wpow2_stale", "dahlin_li", "cats_lb"):
        _, a = _frames(sc, r)
        _, b = _frames(sc, r + "+adm")
        assert not any(b["dropped"])
        assert a["site_of"] == b["site_of"], r


def test_admission_wrapper_drops_in_overload():
    o = run(OVER, "wrr+adm", 2)
    assert 0.15 < o["rejected"] < 0.35                                  # about 1 - 0.95 / 1.3 = 27%


# ------------------------------------------------------------------------------------------------ baselines
def _ctx(S=3, c=(1, 1, 1), d=(0.01, 0.02, 0.03), mu=10.0, W=2.0, D=0.3, rate=10.0):
    c = np.array(c)
    return SimpleNamespace(S=S, c=c, mu=mu, scv=0.25, D=D, W=W, d_known=np.array([d]), rngs=[np.random.default_rng(0)],
                           ingress_rate=[rate], budget_bps=0.0, probe_bytes=124, frame=0, report_bytes=62,
                           counter_bytes=4)


def test_nearest_and_wrr_sequence():
    ctx = _ctx(S=3, c=(5, 1, 1), d=(0.03, 0.01, 0.02))
    assert Nearest(ctx, 0).choose(0)[0] == 1
    w = WRR(ctx, 0)
    assert [w.choose(0)[0] for _ in range(7)] == [0, 0, 1, 0, 2, 0, 0]  # nginx smooth WRR, weights {5, 1, 1}


def test_lsq_local_view():
    ctx = _ctx(S=3, c=(1, 2, 1))
    r = LSQ(ctx, 0)
    for s, q in enumerate((2, 2, 1)):
        r.on_report(1.0, s, q, 1.0, 0)
    assert r.choose(1.0)[0] == 1                                        # 2 frames on 2 servers = 1 per server
    r.on_send(1.0, 1)
    r.on_send(1.0, 1)                                                    # now 4 / 2 = 2 per server
    assert r.choose(1.0)[0] == 2


def test_lsq_sample_independent_sampling_within_budget():
    """LSQ-Sample: no shared reports; its own random samples (probes) spend the same byte budget; each ingress samples
    on its own, so two ingresses do not hold the same measurement times (shared reports would make them equal)."""
    o, f = _frames(SMALL, "lsq_sample")
    assert o["report_bytes_per_s"] == 0.0
    budget = f["ctx"].budget_bps
    assert abs(o["bytes_per_s_per_ingress"] - budget) / budget < 0.05
    r0, r1 = f["rules"][0], f["rules"][1]
    assert np.mean(np.isclose(r0.g, r1.g)) < 0.5
    _, f2 = _frames(SMALL, "lsq")
    assert np.mean(np.isclose(f2["rules"][0].g, f2["rules"][1].g)) > 0.5         # shared reports: same times
    # the sample replaces the local entry and covers the own frames that reached the site before it was taken
    ctx = _ctx(S=3, c=(1, 2, 1))
    ctx.budget_bps, ctx.probe_bytes = 264.0, 124
    r = resolve_rule("lsq_sample")(ctx, 0)
    r.on_send(1.0, 1)                                       # arrives at 1.0 + 0.02 / 2
    r.on_probe(1.2, 1, 3, 1.05)                            # sampled after it arrived: 3 frames, all counted already
    assert r.q[1] == 3 and len(r.log[1]) == 0
    r.on_send(1.3, 1)
    r.on_probe(1.4, 1, 0, 1.0)                             # an older sample is ignored
    assert r.q[1] == 3 and len(r.log[1]) == 1


def test_dahlin_water_filling():
    assert np.allclose(dahlin_fill([0, 2, 4], [1, 1, 1], 3), [5 / 6, 1 / 6, 0])
    L = np.array([0, 2, 4.0])
    assert np.allclose(dahlin_fill(L, [1, 1, 1], 100), ((L.sum() + 100) / 3 - L) / 100)    # Eq. 2
    assert np.allclose(dahlin_fill([4, 4], [1, 2], 3), [0, 1])          # per-GPU load decides


def test_dahlin_randomizes_by_fill():
    ctx = _ctx()
    r = DahlinLI(ctx, 0)
    for s, q in enumerate((0, 2, 4)):
        r.on_report(2.0, s, q, 2.0, 1)                                   # 3 arrivals per 2 s window in total
    picks = np.bincount([r.choose(2.0)[0] for _ in range(4000)], minlength=3) / 4000
    assert picks[2] == 0 and picks[0] > picks[1] > 0


def test_cats_table_and_threshold():
    assert list(np.bincount(expand_table([0.2, 0.3, 0.3, 0.2], 10))) == [2, 3, 3, 2]       # draft Fig. 3
    ctx = _ctx(S=3, c=(1, 1, 1), d=(0.01, 0.01, 0.01))
    r = CatsLB(ctx, 0)
    for s in range(3):
        r.on_report(1.0, s, 0, 1.0, 0)
    r.choose(1.0)
    n0 = r.n_regen
    r.on_report(3.0, 0, 0.1, 3.0, 0)                                     # change below THETA: no new table
    r.choose(3.0)
    assert r.n_regen == n0
    r.on_report(5.0, 0, 3, 5.0, 0)                                       # big change: regenerate, site 0 loses share
    r.choose(5.0)
    assert r.n_regen == n0 + 1 and r.w[0] < r.w[1]


def test_prequal_hcl_selection():
    ctx = _ctx(S=4, c=(1, 1, 1, 1), d=(0.0, 0.0, 0.0, 0.0))
    p = PrequalHCL(ctx, 0)
    p.rate = 0.0
    p.tokens = 0.0
    for v in (0.0, 0.0, 1.0, 5.0):
        p.rif_hist.append(v)                                             # 84% quantile ~ 2.9
    p.pool = [[0, 0.0, 0.30, 0.0, 0, 99], [1, 1.0, 0.10, 0.0, 0, 99], [2, 5.0, 0.01, 0.0, 0, 99]]
    assert p.choose(0.1)[0] == 1                                         # cold with the lowest latency (2 is hot)
    p.pool = [[2, 5.0, 0.01, 0.0, 0, 99], [3, 4.0, 0.50, 0.0, 0, 99]]
    p.rif_hist.extend([0.0] * 20)
    assert p.choose(0.1)[0] == 3                                         # all hot: lowest RIF


def test_liyanage_formulas_and_hysteresis():
    ctx = _ctx(S=2, c=(1, 1), d=(0.0, 0.0), D=0.5, rate=1.0)
    r = Liyanage26(ctx, 0)
    r.PROBE = False
    r.cur = [0]
    for k in range(20):
        r.on_reply(0.0, 0, 0.40 + 0.01 * (k % 10), 0)                    # current: Cantelli bound > 0.15
        r.on_reply(0.0, 1, 0.10 + 0.001 * k, 0)                          # challenger: clearly better
    picks = [r.choose(1.0)[0] for _ in range(5)]
    assert picks == [0, 0, 0, 0, 1]                                      # switches only after N = 5 passes
    z = 2.0
    assert 1.0 / (1.0 + z * z) == pytest.approx(0.2)                    # Cantelli bound at z = 2


def test_oracle_adm_drops_only_hopeless():
    o = run(SMALL, "oracle_adm", 3)
    o2 = run(OVER, "oracle_adm", 3)
    assert o2["rejected"] > o["rejected"]


def test_resolve_rule_parameters():
    cls = resolve_rule("prequal_hcl@MAX_AGE=4.0,Q_RIF=0.75")
    assert cls.MAX_AGE == 4.0 and cls.Q_RIF == 0.75 and issubclass(cls, PrequalHCL)
    with pytest.raises(KeyError):
        resolve_rule("prequal_hcl@NOT_A_PARAM=1")
    adm = resolve_rule("liyanage26+adm")
    assert adm.uses_reports and adm.uses_counter and adm.needs_replies
