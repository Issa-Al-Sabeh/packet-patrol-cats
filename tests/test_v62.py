"""v6.2 candidates: at v6.1's settings the new class is exactly v6.1 (pilot seed 101 only)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import catsim.rules_v62  # noqa: E402,F401  (registers the candidates)
from catsim.engine import run  # noqa: E402
from catsim.v5 import build_overload  # noqa: E402

KEYS = ("success", "rejected", "expired", "late_completed", "mean_ms", "p99_ms")


def _sc(key):
    return {s.key: s for s in build_overload()[0]}[key]


def test_same_settings_equal_v61():
    for key in ("O_burst", "O_130", "O_dc_half"):
        a, b = run(_sc(key), "ours_v61", 101), run(_sc(key), "v62c_same", 101)
        for k in KEYS:
            assert a[k] == b[k], (key, k, a[k], b[k])


def test_candidates_change_the_burst_run():
    a = run(_sc("O_burst"), "ours_v61", 101)
    for name in ("v62c_fall", "v62c_w06", "v62c_w10"):
        assert run(_sc("O_burst"), name, 101)["success"] != a["success"], name
