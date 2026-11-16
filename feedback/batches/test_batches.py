"""Checks of the runner of Batches A and B (python3 -m pytest feedback/batches/test_batches.py -q).

Only pilot seed 101 and the Beirut network are used here: these are checks of the harness, not results.
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "phase1"))

import run_batches as rb                                                # noqa: E402
from catsim import v61                                                  # noqa: E402

PILOT_SEED = 101
SAME = ("frames", "n_success", "n_late", "n_expired", "n_rejected", "success", "rejected", "expired", "late",
        "mean_ms", "p99_ms", "bytes_per_s_per_ingress", "report_bytes_per_s_per_ingress",
        "echo_bytes_per_s_per_ingress")


def _o130():
    from catsim.v5 import build_overload
    return {sc.key: sc for sc in build_overload()[0]}["O_130"]


def test_frozen_files_are_unchanged():
    n, changed, _ = rb.check_frozen()
    assert n >= 30 and changed == []


def test_plan_sizes_and_names():
    for batch, size in rb.SIZES.items():
        jobs = rb.jobs_of(batch, v61.FIRST_SEEDS)
        assert len(jobs) == size
        assert len({rb.key_of(j) for j in jobs}) == size
        assert {j[4] for j in jobs} == set(range(301, 306))


def test_only_evaluation_seeds_are_accepted():
    import pytest
    with pytest.raises(SystemExit):
        rb.jobs_of("A", (201,))


def test_the_recorder_changes_no_result():
    """Batch B wraps each rule in a recorder. The run must be the same run."""
    sc = _o130()
    for rule in ("ours_v61", "ours_v6", "wrr+adm61", "wrr+adm"):
        a, _ = rb.plain(("A", "beirut", sc, rule, PILOT_SEED))
        b, _ = rb.measured(("B", "beirut", sc, rule, PILOT_SEED))
        for k in SAME:
            assert a[k] == b[k], (rule, k, a[k], b[k])
        assert b["rule"] == rule
        est = json.loads(b["est_by_ingress"])
        assert len(est) == sc.ingresses and all(0.5 < x < 2.0 for x in est), (rule, est)
        assert all(n > 10 for n in json.loads(b["estimates_by_ingress"]))


def test_measurements_equal_phase_1():
    """The same run, measured here and by feedback/phase1/run_phase1.py (saved in validate.csv), gives the same
    numbers."""
    import run_phase1 as p1
    rule = p1.V61_PHASE1
    sc = {s.key: s for _, s in p1.scenarios_pilot()}["dev_115"]
    with open(os.path.join(ROOT, "feedback", "phase1", "validate.csv")) as f:
        saved = [r for r in csv.DictReader(f) if r["scenario"] == "dev_115" and r["rule"] == rule
                 and int(r["seed"]) == PILOT_SEED][0]
    row, _ = rb.measured(("B", "dev", sc, rule, PILOT_SEED))
    for k in ("success", "rejected", "expired", "late", "admitted_over_capacity", "share_min", "share_max",
              "spread_mean", "spread_max", "est_min", "est_max"):
        assert abs(row[k] - float(saved[k])) <= 1e-9 * max(1.0, abs(float(saved[k]))), (k, row[k], saved[k])
    for k in ("share_by_ingress", "est_by_ingress", "plan_drop_by_ingress"):
        assert json.loads(row[k]) == json.loads(saved[k]), k
    assert row["bins_dropping"] == int(saved["bins_dropping"])
