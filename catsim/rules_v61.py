"""OURS V6.1 = ours v6 with the offered-traffic estimate corrected (feedback of 11 Nov 2026, Phase 1; the reasons and the
numbers are in feedback/estimator.md). Everything else is exactly v6.

What was wrong in v6. Its estimate of the traffic offered at site s is
    r_s = (A_s / W) / (1 - p),      p = this ingress's OWN drop share in the report window,
which is right only if every ingress drops the same share. They do not (feedback/estimator.md, section 3).

What v6.1 does instead (option C of that note, "add information"):
  1. THE AGGREGATE DROP COUNTER. Each ingress counts the frames it drops. At most every ECHO_FRAC x W seconds it puts
     that count on a frame it is sending anyway (echo_bytes) and starts again from zero. Each site adds up the counts
     that reach it in a report window and reports the sum E_s with its report (echo_bytes more per report). So
         p = sum_s E_s / (sum_s A_s + sum_s E_s)
     is the share of ALL the offered frames that ALL the ingresses dropped, the same number at every ingress that
     received the same reports. The estimate keeps v6's formula, r_s = (A_s / W) / (1 - p), and v6's smoothing (first
     report as is; a clear rise at once; otherwise an EWMA).
     p is one number per round of reports, so it is computed when the plan is made (every report of the round has then
     arrived), not report by report.
  2. THE CLEAR-RISE TEST COMPARES LIKE WITH LIKE (audit finding 3). v6 compared the count of frames that reached the
     site, A_s, with its estimate of the OFFERED frames. v6.1 compares A_s with the arrivals that estimate implies,
     estimate x W x (1 - p).
  3. OVERLOAD MODE STARTS AT 90% OF THE MEASURED CAPACITY (v6: 95%). Phase 2 (feedback/cost.md): with the corrected
     estimate every ingress sits at the same side of the threshold, and at 95% load they switched dropping on and off
     together. The threshold is v6's own overload switch, so it moves two things: between 90% and 95% a frame may be
     dropped (only when every site would cost more than one miss for it), and the plan is used as it is, without the
     balance rule A. No site is planned above 95% of its capacity, as before. Chosen on pilot seeds 101-105 among
     85%, 90% and 95% (90%: better in two of 16 pilot scenarios, worse in none; 85% starts dropping at the normal
     load).
While nothing is dropped anywhere, p = 0; while the offered traffic is also below 90% of the measured capacity, v6.1
decides exactly like v6 (tested).

Named, not changed (Phase 2): the term kappa x (frames left above the safe queue level) of the cost is an
EXTERNALITY-INSPIRED BACKLOG PENALTY. kappa = rho / (1 - rho) counts the later frames one leftover frame delays and
charges each as late, which is an upper bound and not a derived conversion; rho is capped at 0.95 (kappa <= 19), and
the cap is part of the algorithm. A constant penalty gives the same results on the pilot seeds (feedback/cost.md).

Limits (stated, not hidden):
  * the counts travel on frames, so an ingress that sends nothing reports nothing (its share is capped at 90%, so it
    always sends something); a count is lost with the report that carries it;
  * a count reaches the reports up to ECHO_FRAC x W + one way of path delay after the drops it counts;
  * the drops are added up over all sites and ingresses: the sites they would have gone to are not known, so the same
    share p is applied to every site.
"""
import math

import numpy as np

from .rules import SplitSpeed
from .rules_v5 import OwnDrops
from .rules_v6 import SplitV6


class DropEcho:
    """The ingress side of the aggregate drop counter: count own drops, and say when the count may travel."""

    def __init__(self, every):
        self.every = every                    # seconds between two counts at least
        self.pending = 0
        self.last = -1e9

    def dropped(self):
        self.pending += 1

    def take(self, now):
        """The count to put on the frame being sent now (0 = none)."""
        if self.pending and now - self.last >= self.every:
            n, self.pending, self.last = self.pending, 0, now
            return n
        return 0


class SplitV61(SplitV6):
    uses_drop_echo = True
    ECHO_FRAC = 0.25          # a drop count travels at most every ECHO_FRAC x W seconds
    like_rise = True          # change 2 (False = v6's test, for the ablation)
    KAPPA = None              # sensitivity checks only: a constant backlog penalty (None = v6's rho / (1 - rho))
    DROP_FROM = 0.90          # change 3: overload mode (may drop, no balance rule) above this share of capacity

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        S = self.S
        self.A_last = np.zeros(S)                 # last report of each site: arrivals counter
        self.E_last = np.zeros(S)                 # ... and the sum of the drop counts
        self.fresh = np.zeros(S, dtype=bool)      # reports not yet used in the estimate
        self.seen_off = np.zeros(S, dtype=bool)
        self.echo = DropEcho(self.ECHO_FRAC * self.W)
        self.echo_out = 0
        self.p_all = 0.0                          # the drop share of everyone, last round

    # ---- reports
    def on_report_x(self, now, s, q, g, A, X):
        self.on_report_e(now, s, q, g, A, X, 0)

    def on_report_e(self, now, s, q, g, A, X, E):
        if g <= self.g[s]:
            return
        self.A_last[s], self.E_last[s], self.fresh[s] = A, E, True
        self.own_log.prune(now - 2.0 * self.W - 5.0 - self.BURST_WIN)
        SplitSpeed.on_report_x(self, now, s, q, g, A, X)

    # ---- the estimate
    def _absorb(self, s, A, p):
        """v6's smoothing of the offered traffic at site s, with the share p of this round."""
        W = self.W
        r = A / W / (1.0 - p)
        if not self.seen_off[s]:
            self.rate_off[s] = r
            self.seen_off[s] = True
            return
        if self.like_rise:
            e = self.rate_off[s] * W * (1.0 - p)                 # arrivals the current estimate implies
            rise = A > e + self.RISE_Z * math.sqrt(max(e, 1.0))
        else:
            rise = A > self.rate_off[s] * W + self.RISE_Z * math.sqrt(max(self.rate_off[s] * W, 1.0))
        if self.use_burst and rise:
            self.rate_off[s] = r                                 # a real rise (beyond count noise): take it at once
        else:
            self.rate_off[s] = self.EWMA * r + (1 - self.EWMA) * self.rate_off[s]

    def _update_offered(self):
        if not self.fresh.any():
            return
        A_tot, E_tot = float(self.A_last.sum()), float(self.E_last.sum())
        p = E_tot / (A_tot + E_tot) if A_tot + E_tot > 0 else 0.0
        self.p_all = p = min(p, OwnDrops.MAX)
        for s in np.flatnonzero(self.fresh):
            self._absorb(int(s), self.A_last[s], p)
        self.fresh[:] = False

    def _plan(self, now):
        self._update_offered()
        super()._plan(now)

    def _kappa(self, rho):
        return super()._kappa(rho) if self.KAPPA is None else float(self.KAPPA)

    # ---- the drop counter
    def on_send(self, now, s):
        super().on_send(now, s)
        self.echo_out = self.echo.take(now)

    def on_drop(self, now):
        super().on_drop(now)
        self.echo.dropped()

    def diag(self):
        d = super().diag()
        d["p_all"] = round(float(self.p_all), 4)
        return d


class SplitV61OldRise(SplitV61):
    """Ours v6.1 with v6's clear-rise test (ablation of change 2)."""
    like_rise = False


V61_RULE_CLASSES = {"ours_v61": SplitV61, "ours_v61_oldrise": SplitV61OldRise}
