"""Phase 1 prototypes of the offered-traffic estimator. NOT part of catsim: nothing here is used by any saved result.

The frozen v6 estimate of the traffic offered at site s (rules_v6.py line 73) is
    r_s = (A_s / W) / (1 - p),        p = this ingress's OWN drop share in the report window.
Every candidate keeps that formula and the frozen smoothing, and changes only where p comes from:

    own    the frozen rule: p = own dropped / own offered                      (assumes every ingress drops alike)
    bound  p = own dropped / (all arrivals + own dropped)                      (a lower bound: the others drop nothing)
    echo   p = all dropped / (all arrivals + all dropped), from an aggregate drop counter in the site reports
           (added information: each ingress tells a site how many frames it dropped, at most every ECHO_FRAC x W
           seconds, on a frame it sends anyway; the site adds the counts up and reports the sum)

Switch b1_like: the "clear rise" test (B1) compares the arrivals count with the estimate of the ARRIVALS (the offered
estimate x (1 - p)) instead of with the offered estimate itself (audit finding 3).

The echo counter is EMULATED here: the ingresses of one run write to a shared EchoBus that stands for the sites'
counters, and read it only when the matching report arrives (so it is lost or late exactly when that report is).
If the team picks this option, the counter moves into the engine and the reports for real.
"""
import math
from collections import deque

import numpy as np

from catsim.rules import RULE_CLASSES, SplitSpeed
from catsim.rules_v5 import OwnDrops
from catsim.rules_v6 import SplitV6

ECHO_BYTES = 2            # one echoed count (ingress -> site), and one aggregate count per report (site -> ingress)


class EchoBus:
    """Stands for the sites' aggregate drop counters (see the module docstring)."""

    def __init__(self, S):
        self.log = [deque() for _ in range(S)]       # (estimated arrival time at the site, frames dropped)
        self.msgs = 0

    def add(self, s, t_arr, n):
        self.log[s].append((t_arr, n))
        self.msgs += 1

    def count(self, s, t0, t1):
        return sum(n for t, n in self.log[s] if t0 < t <= t1)

    def prune(self, s, older_than):
        lg = self.log[s]
        while lg and lg[0][0] < older_than:
            lg.popleft()


class EstV6(SplitV6):
    share_mode = "own"        # own | bound | echo
    at_plan = False           # own only: apply the report at plan time instead of on arrival (harness check)
    b1_like = False
    ECHO_FRAC = 0.25

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        S = self.S
        self.A_last = np.zeros(S)
        self.D_last = np.zeros(S)
        self.g_last = np.full(S, -1e9)
        self.fresh = np.zeros(S, dtype=bool)
        self.seen_off = np.zeros(S, dtype=bool)
        self.pending = 0
        self.last_echo = -1e9
        self.echo_msgs = 0
        self.p_hat = 0.0
        if self.share_mode == "echo":
            if getattr(ctx, "_echo_bus", None) is None:
                ctx._echo_bus = EchoBus(S)
            self.bus = ctx._echo_bus

    # ---- the estimate (frozen smoothing: first report, clear rise at once, else EWMA)
    def _absorb(self, s, A, p):
        W = self.W
        r = A / W / (1.0 - p)
        if not self.seen_off[s]:
            self.rate_off[s] = r
            self.seen_off[s] = True
            return
        if self.b1_like:
            e = self.rate_off[s] * W * (1.0 - p)
            rise = A > e + self.RISE_Z * math.sqrt(max(e, 1.0))
        else:
            rise = A > self.rate_off[s] * W + self.RISE_Z * math.sqrt(max(self.rate_off[s] * W, 1.0))
        if self.use_burst and rise:
            self.rate_off[s] = r
        else:
            self.rate_off[s] = self.EWMA * r + (1 - self.EWMA) * self.rate_off[s]

    def _per_report(self):
        return self.share_mode == "own" and not self.at_plan

    def on_report_x(self, now, s, q, g, A, X):
        if g <= self.g[s]:
            return
        if self._per_report():
            self._absorb(s, A, self.own_log.share(g - self.W, g))
        else:
            self.A_last[s], self.g_last[s], self.fresh[s] = A, g, True
            if self.share_mode == "echo":
                self.D_last[s] = self.bus.count(s, g - self.W, g)
                self.bus.prune(s, now - 3.0 * self.W - 10.0)
        self.own_log.prune(now - 2.0 * self.W - 5.0 - self.BURST_WIN)
        SplitSpeed.on_report_x(self, now, s, q, g, A, X)

    def _update_offered(self):
        """Plan time (every report of the round has arrived): one share p for the round, then the frozen smoothing."""
        if self._per_report() or not self.fresh.any():
            return
        g = float(np.max(self.g_last))
        A_tot = float(self.A_last.sum())
        if self.share_mode == "own":
            p = self.own_log.share(g - self.W, g)
        elif self.share_mode == "bound":
            d = sum(1 for t, x in self.own_log.log if g - self.W < t <= g and x)
            p = d / (A_tot + d) if A_tot + d > 0 else 0.0
        else:
            D = float(self.D_last.sum())
            p = D / (A_tot + D) if A_tot + D > 0 else 0.0
        p = min(p, OwnDrops.MAX)
        self.p_hat = p
        for s in np.flatnonzero(self.fresh):
            self._absorb(int(s), self.A_last[s], p)
        self.fresh[:] = False

    def _plan(self, now):
        self._update_offered()
        super()._plan(now)

    # ---- echo: tell a site how many frames this ingress dropped, on a frame it sends anyway
    def on_send(self, now, s):
        super().on_send(now, s)
        if self.share_mode == "echo" and self.pending and now - self.last_echo >= self.ECHO_FRAC * self.W:
            self.bus.add(s, now + self.d[s] / 2, self.pending)
            self.pending, self.last_echo = 0, now
            self.echo_msgs += 1

    def on_drop(self, now):
        super().on_drop(now)
        self.pending += 1


def _variant(name, **attrs):
    cls = type(name, (EstV6,), attrs)
    RULE_CLASSES[name] = cls
    return cls


CANDIDATES = {
    "est_own": dict(share_mode="own"),                                   # must equal ours_v6 exactly
    "est_own_plan": dict(share_mode="own", at_plan=True),               # must equal ours_v6 (synchronised reports)
    "est_own_b1": dict(share_mode="own", b1_like=True),
    "est_bound": dict(share_mode="bound"),
    "est_bound_b1": dict(share_mode="bound", b1_like=True),
    "est_echo": dict(share_mode="echo"),
    "est_echo_b1": dict(share_mode="echo", b1_like=True),
}
for _n, _a in CANDIDATES.items():
    _variant(_n, **_a)


# ---------------------------------------------------------------------------------- measurement helpers
def recording(base):
    """The same rule, logging at every plan what it believed (never changes a decision)."""
    class Rec(base):
        def __init__(self, ctx, i):
            super().__init__(ctx, i)
            self.rec = []

        def _plan(self, now):
            super()._plan(now)
            if self.plan_t == now:
                self.rec.append((now, float(self.rate_off.sum()) * self.scale, float(self.p_drop), float(self.scale),
                                 float(self.kcal), int(self.n_cal)) + tuple(float(x) for x in self.p)
                                + tuple(int(x) for x in self.meter.c))
    Rec.__name__ = "Rec[" + base.__name__ + "]"
    return Rec


def forced(base):
    """The professor's counterexample as a run: ingress 0 drops every second frame, the others drop nothing, and
    every frame that is sent goes by capacity round-robin. Only the offered-traffic estimate is exercised."""
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
            if self.i == 0:
                self.tog = not self.tog
                if self.tog:
                    return -1, 1.0
            self.cur += self.c
            s = int(np.argmax(self.cur))
            self.cur[s] -= self.c.sum()
            return s, float("nan")
    Forced.__name__ = "Forced[" + base.__name__ + "]"
    return Forced


def register(name, kind):
    """Register '_rec_<name>' or '_forced_<name>' (name = ours_v6 or a candidate) and return the new rule name."""
    from catsim.baselines import resolve_rule
    new = f"_{kind}_{name}".replace("@", "_at_").replace("=", "_").replace(",", "_")
    if new not in RULE_CLASSES:
        RULE_CLASSES[new] = {"rec": recording, "forced": forced}[kind](resolve_rule(name))
    return new
