"""Diagnostic only: ours v6.1 with the greedy allocation replaced by the BEST allocation on the same grid of 100
pieces (same cost curves, same limits, same drop option). Used to measure what the greedy planner costs in realised
deadline success. Not a proposed rule."""
import numpy as np

from catsim.rules import RULE_CLASSES
from catsim.rules_v61 import SplitV61


def best_on_grid(info, N=100):
    """(lam, drop) minimising sum_s C_s(x_s) + drop, x_s on the grid, x_s <= limit_s, sum x_s + drop = total.
    Dynamic programme over the sites (covers every split). None when no split fits the limits."""
    step, S = info["step"], len(info["levels"])
    x = np.arange(N + 1) * step
    C = []
    for s in range(S):
        lv, c = info["levels"][s], info["sel_c"][s]
        v = np.where(x <= lv[-1], np.interp(x, lv, c), c[-1] + info["slope"] * (x - lv[-1]))
        v[x > info["limit"][s] + 1e-9] = np.inf
        C.append(v)
    best = C[0].copy()
    pick = []                                              # pick[s-1][n] = pieces given to site s when sites 0..s hold n
    for s in range(1, S):
        new = np.full(N + 1, np.inf)
        arg = np.zeros(N + 1, dtype=int)
        for k in range(N + 1):
            if not np.isfinite(C[s][k]):
                break
            cand = best[:N + 1 - k] + C[s][k]
            better = cand < new[k:] - 1e-15
            new[k:][better] = cand[better]
            arg[k:][better] = k
        best = new
        pick.append(arg)
    if info["may_drop"]:
        tot = best[::-1] + np.arange(N + 1) * step          # index d = pieces dropped
        d = int(np.argmin(tot))
        if not np.isfinite(tot[d]):
            return None
    else:
        d = 0
        if not np.isfinite(best[N]):
            return None
    n = N - d
    ks = [0] * S
    for s in range(S - 1, 0, -1):
        ks[s] = int(pick[s - 1][n])
        n -= ks[s]
    ks[0] = n
    return np.array(ks, float) * step, d * step


class SplitV61GridOpt(SplitV61):
    def _after_greedy(self, info):
        got = best_on_grid(info)
        if got is None or abs(info["lam"].sum() + info["drop"] - info["total"]) > 1e-6 * info["total"] \
                or (info["lam"] > info["limit"] + 1e-6).any():
            return info["lam"], info["drop"]                # the 'every site is full' fallback: keep it
        return got


RULE_CLASSES["ours_v61_gridopt"] = SplitV61GridOpt
