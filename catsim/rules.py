"""The site-selection rules: ours (v1, v2, v2 + self-check, v2 + measured speeds), 13 comparison rules (one of
them the round-robin control for the measured speeds), and 4 ablations of ours v1.

One rule object per ingress, so a rule only knows what that ingress could know:
  - path delays and site capacities as configured (fixed, known in advance)
  - the reports it received (frames q at the site, time g measured, arrivals counter A)
  - its own sends, and (Liyanage-style and ours v2 + self-check only) the delays of its own completed frames
The oracle is the only exception: it sees the true queues, as a best-case reference.

Every rule implements choose(now) -> (site, predicted risk or NaN).
"""
import math
from collections import deque

import numpy as np

from .queueing import Ager, NoAger, fluid, own_send, point, poisson_jump

NAN = float("nan")


class Rule:
    uses_reports = True      # receives the shared CATS reports (counted in bytes per second)
    uses_counter = False     # also needs the 4-byte arrivals counter A in each report
    needs_replies = False    # learns the delay of its own completed frames
    predicts = False         # outputs a predicted deadline-miss risk (for the calibration check)

    def __init__(self, ctx, i):
        self.ctx, self.i = ctx, i
        self.S = ctx.S
        self.d = ctx.d_known[i]                # known round-trip delay to each site (s)
        self.rng = ctx.rngs[i]
        self.c = ctx.c
        self.cap = ctx.c * ctx.mu
        self.probe_out = []
        self.probe_bytes = 0

    def on_report(self, now, s, q, g, A):
        pass

    def on_report_x(self, now, s, q, g, A, X):
        """A report with the discard count X of a deadline-aware site (X = 0 otherwise). Most rules ignore X."""
        self.on_report(now, s, q, g, A)

    def on_send(self, now, s):
        pass

    def on_drop(self, now):
        """choose() returned -1: this frame is dropped at the ingress (v5 study)."""
        pass

    def on_reply(self, now, s, delay, frame):
        pass

    def on_probe(self, now, s, q, t_meas):
        pass

    def _argmin_random(self, x):
        best = np.flatnonzero(x <= x.min() + 1e-12)
        return int(best[0]) if len(best) == 1 else int(self.rng.choice(best))


# ====================================================================== basic controls
class Nearest(Rule):
    uses_reports = False

    def choose(self, now):
        return int(np.argmin(self.d)), NAN


class CapRandom(Rule):
    uses_reports = False

    def choose(self, now):
        p = self.cap / self.cap.sum()
        return int(self.rng.choice(self.S, p=p)), NAN


class WRR(Rule):
    """Smooth weighted round-robin by capacity. Uses no reports."""
    uses_reports = False

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        self.cur = np.zeros(self.S)

    def choose(self, now):
        self.cur += self.c
        s = int(np.argmax(self.cur))
        self.cur[s] -= self.c.sum()
        return s, NAN


# ====================================================================== rules on the last report
class LastReport(Rule):
    """Keeps the last report of each site."""

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        self.q = np.zeros(self.S)
        self.g = np.full(self.S, -1e9)
        self.has = np.zeros(self.S, dtype=bool)

    def on_report(self, now, s, q, g, A):
        if g >= self.g[s]:
            self.q[s], self.g[s], self.has[s] = q, g, True


class TimeoutSED(LastReport):
    """CATS-draft style: trust the last value for up to 3 report windows; lowest expected delay (SED).
    When every value has expired, fall back to the nearest site."""

    def choose(self, now):
        valid = self.has & (now - self.g <= 3 * self.ctx.W)
        if not valid.any():
            return int(np.argmin(self.d)), NAN
        sed = (self.q + 1.0) / self.cap + self.d
        sed[~valid] = np.inf
        return self._argmin_random(sed), NAN


class PowerOfTwo(LastReport):
    """Two sites at random; the one with fewer frames in the last report."""

    def choose(self, now):
        a, b = self.rng.choice(self.S, size=2, replace=False)
        if self.q[a] == self.q[b]:
            return int(a if self.rng.random() < 0.5 else b), NAN
        return int(a if self.q[a] < self.q[b] else b), NAN


class WPow2Stale(LastReport):
    """After the 2025 heterogeneous-server study: sample two sites in proportion to capacity,
    take the lower load q/c in the last snapshot."""

    def choose(self, now):
        p = self.cap / self.cap.sum()
        a, b = self.rng.choice(self.S, size=2, replace=False, p=p)
        la, lb = self.q[a] / self.c[a], self.q[b] / self.c[b]
        if la == lb:
            return int(a if self.rng.random() < 0.5 else b), NAN
        return int(a if la < lb else b), NAN


class LSQ(LastReport):
    """LSQ-style local view (after Vargaftik et al.): last report + this ingress's own frames sent since,
    counted once, no ageing. Joins the lowest local count PER SERVER (the sites differ in size);
    ties go to the larger site."""

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        self.log = [deque() for _ in range(self.S)]      # estimated arrival times of own frames

    def on_report(self, now, s, q, g, A):
        if g < self.g[s]:
            return
        super().on_report(now, s, q, g, A)
        lg = self.log[s]
        while lg and lg[0] <= g:
            lg.popleft()

    def on_send(self, now, s):
        self.log[s].append(now + self.d[s] / 2)

    def choose(self, now):
        qh = (self.q + np.array([len(x) for x in self.log])) / self.c
        best = np.flatnonzero(qh <= qh.min() + 1e-12)
        if len(best) > 1:
            best = best[self.c[best] == self.c[best].max()]
        return int(best[0]) if len(best) == 1 else int(self.rng.choice(best)), NAN


# ====================================================================== shared: estimate the others from the counter
class CounterEstimate:
    """Per-site traffic of the other ingresses, from the 4-byte arrivals counter A in each report.

    lam_tot = A / W (all ingresses), lam_own = own frames that reached the site in the same window.
    Smoothed over windows (EWMA), and corrected by each new report (feedback factor fb).
    """
    EWMA = 0.3
    FB_GAIN, FB_MIN, FB_MAX = 0.1, 0.25, 4.0
    MIN_OWN = 0.2            # below this own rate (frames/s), treat all the others as background
    THETA_CAP = 20.0

    def __init__(self, S):
        self.lt = np.zeros(S)
        self.lo = np.zeros(S)
        self.seen = np.zeros(S, dtype=bool)
        self.fb = np.ones(S)

    def update(self, s, A, own_count, W):
        lt, lo = A / W, own_count / W
        if self.seen[s]:
            a = self.EWMA
            self.lt[s] = a * lt + (1 - a) * self.lt[s]
            self.lo[s] = a * lo + (1 - a) * self.lo[s]
        else:
            self.lt[s], self.lo[s], self.seen[s] = lt, lo, True

    def feedback(self, s, predicted_mean, q):
        step = self.FB_GAIN * (q - predicted_mean) / max(1.0, predicted_mean)
        self.fb[s] = float(np.clip(self.fb[s] * (1.0 + step), self.FB_MIN, self.FB_MAX))

    def others(self, s):
        """(theta, lam_bg): copy-cat frames per own send, and the rest of the others as a steady stream."""
        tot = np.where(self.seen, self.lt, 0.0)
        own = np.where(self.seen, self.lo, 0.0)
        oth = np.maximum(tot - own, 0.0)
        if own.sum() > 0 and oth.sum() > 0:
            w = 1.0 - 0.5 * np.abs(own / own.sum() - oth / oth.sum()).sum()
        else:
            w = 0.0
        others = self.fb[s] * oth[s]
        theta = min(self.fb[s] * w * oth[s] / own[s], self.THETA_CAP) if own[s] >= self.MIN_OWN else 0.0
        lam_bg = max(others - theta * own[s], 0.0)
        return theta, lam_bg

    def other_rate(self, s):
        return self.fb[s] * max(self.lt[s] - self.lo[s], 0.0)


class OwnLog:
    """This ingress's own frames per site, to count them in the counter window and replay them after a reset."""

    def __init__(self, S):
        self.sends = [deque() for _ in range(S)]       # (send time, estimated arrival time at the site)

    def add(self, s, t_send, t_arrive):
        self.sends[s].append((t_send, t_arrive))

    def count_window(self, s, g, W):
        return sum(1 for _, a in self.sends[s] if g - W < a <= g)

    def after(self, s, g):
        return [(st, a) for st, a in self.sends[s] if a > g]

    def prune(self, s, older_than):
        lg = self.sends[s]
        while lg and lg[0][1] < older_than:
            lg.popleft()


# ====================================================================== our rule, expected delay, ablations
class BeliefRule(Rule):
    """OUR RULE: risk(s) = sum over n of b_s(n) * late_s(n); random choice among near-ties.

    b_s(n): the old report aged into a range (frames finish, the others' frames arrive),
            plus our own sends (+1 each, plus Poisson(theta) copy-cat frames of the others).
    Options switch parts off for the ablations, or switch the score to expected delay.
    """
    predicts = True
    uses_counter = True
    counting = True       # estimate the others from the counter
    ageing = True         # let the belief change with time
    exp_late = False      # use the exponential late(n) even if jobs are not exponential
    near_ties = True      # random choice among near-ties, weighted by spare capacity
    score = "risk"        # "risk" or "expected_delay"
    R_MAX = 0.5           # no safe site: send where it finishes soonest
    TIE_REL, TIE_ABS = 0.25, 0.001
    REBUILD = 0.02        # rebuild the ageing tables when the background rate changes by more than 2%

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        S = self.S
        self.late = ctx.late_exp[i] if self.exp_late else ctx.late[i]
        self.mean_t = ctx.mean_t
        self.est = CounterEstimate(S)
        self.own = OwnLog(S)
        self.b = [point(0) for _ in range(S)]
        self.tb = np.zeros(S)
        self.agers = [self._ager(s, 0.0) for s in range(S)]
        self.theta = np.zeros(S)
        self.jump = [np.array([1.0]) for _ in range(S)]
        self.last_g = np.full(S, -1e9)

    def _ager(self, s, lam):
        if not self.ageing:
            return NoAger()
        return Ager(int(self.c[s]), self.ctx.mu, lam)

    def _advance(self, s, t):
        if t > self.tb[s]:
            self.b[s] = self.agers[s].age(self.b[s], t - self.tb[s])
            self.tb[s] = t

    def _set_rates(self, s):
        theta, lam_bg = self.est.others(s) if self.counting else (0.0, 0.0)
        if abs(theta - self.theta[s]) > 1e-3:
            self.theta[s] = theta
            self.jump[s] = poisson_jump(theta)
        old = self.agers[s].lam
        if self.ageing and abs(lam_bg - old) > self.REBUILD * max(old, 0.5):
            self.agers[s] = self._ager(s, lam_bg)

    def on_report(self, now, s, q, g, A):
        if g <= self.last_g[s]:
            return                                       # an older report arriving late: ignore
        self.last_g[s] = g
        W = self.ctx.W
        if self.counting:
            if self.est.seen[s] and now - g < 0.5:       # feedback only when the report is fresh enough
                self._advance(s, now)
                self.est.feedback(s, float(self.b[s] @ np.arange(len(self.b[s]))), q)
            self.est.update(s, A, self.own.count_window(s, g, W), W)
        self._set_rates(s)
        # reset to the report, then replay our own frames that reached the site after it was measured
        self.b[s], self.tb[s] = point(q), g
        for st, _ in self.own.after(s, g):
            self._advance(s, max(st, g))
            self.b[s] = own_send(self.b[s], self.jump[s])
        self._advance(s, now)
        self.own.prune(s, g - W - 1.0)

    def on_send(self, now, s):
        self._advance(s, now)
        self.b[s] = own_send(self.b[s], self.jump[s])
        self.own.add(s, now, now + self.d[s] / 2)

    def choose(self, now):
        S = self.S
        risk = np.empty(S)
        ed = np.empty(S)
        for s in range(S):
            self._advance(s, now)
            ba = self.agers[s].age(self.b[s], self.d[s] / 2)       # when our frame would arrive
            risk[s] = ba @ self.late[s]
            ed[s] = self.d[s] + ba @ self.mean_t[s]
        if self.score == "expected_delay":
            s = self._argmin_random(ed)
            return s, float(risk[s])
        r_star = risk.min()
        if r_star > self.R_MAX:                                     # no safe site: finish soonest
            s = int(np.argmin(ed))
            return s, float(risk[s])
        if not self.near_ties:
            s = self._argmin_random(risk)
            return s, float(risk[s])
        margin = max(self.TIE_ABS, self.TIE_REL * r_star)
        ties = np.flatnonzero(risk <= r_star + margin)
        if len(ties) == 1:
            s = int(ties[0])
        else:
            lam = np.where(self.est.seen, self.est.lt, 0.5 * self.cap) if self.counting else np.zeros(S)
            spare = np.maximum(self.cap[ties] - lam[ties], 0.05 * self.cap[ties])
            s = int(self.rng.choice(ties, p=spare / spare.sum()))
        return s, float(risk[s])


class Ours(BeliefRule):
    pass


class ExpectedDelay(BeliefRule):
    score = "expected_delay"
    near_ties = False


class OursNoCounting(BeliefRule):
    counting = False


class OursNoAgeing(BeliefRule):
    ageing = False


class OursExpLate(BeliefRule):
    exp_late = True


class OursNoTies(BeliefRule):
    near_ties = False




# ====================================================================== ours v2: a split, not one site per frame
class SplitRule(Rule):
    """OURS V2: choose a SPLIT of the traffic for the next report interval, instead of one best site per frame.

    At each round of reports: start every site from its reported frames. For each traffic level the site could
    get (0 to 120% of its capacity), age that belief over the next interval (same birth-death ageing and late(n)
    as ours v1) and average the chance of being late. Then share out ALL the traffic (everyone's, measured by the
    counters) so that the expected number of late frames is lowest. Every ingress computes the same split from
    the same reports, so the plan holds for the total and no copycat guess is needed. Frames are sent by taking
    turns with those shares (smooth weighted round-robin), so there are no bursts. With no new report for more
    than one interval, the shares slide back to the capacity split (2 : 4 : 8).

    Self-check variant: each ingress compares the risk it predicted with how many of its own frames were actually
    late (the answers come back through it) and scales each site's risk by that ratio.
    """
    predicts = True
    uses_counter = True
    self_check = False
    GRID = 13                 # traffic levels per site: 0, 10%, ..., 120% of its capacity
    POINTS = 4                # moments in the interval at which the chance of being late is averaged
    CHUNKS = 100              # the total traffic is shared out in 1% steps
    EWMA = 0.3                # smoothing of the counter, as in ours v1
    SETTLE = 0.05             # plan 50 ms after the last report arrived (one round of reports arrives together)
    CHECK_RATE = 0.01         # self-check: weight of each new answer (about the last 100 answers per site)
    CHECK_MIN, CHECK_MAX, CHECK_EPS = 0.05, 20.0, 0.005   # wide limits: the factor must be free to show each site's error
    CHECK_PRIOR = 0.02        # start as if 2% were predicted and 2% seen (factor 1), so the first answers can't swing it
    U_MAX = 0.95              # never plan a site above 95% of its capacity (added after the pilot on spare seeds:
                              # without it, at peak load the plan "sacrificed" one site and left a growing backlog)

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        S = self.S
        self.late = ctx.late[i]
        self.W, self.D = ctx.W, ctx.D
        self.pi = self.cap / self.cap.sum()                       # the capacity split
        self.p = self.pi.copy()
        self.credit = np.zeros(S)
        self.q = np.zeros(S)
        self.g = np.full(S, -1e9)
        self.rate = np.zeros(S)                                   # everyone's frames per second, per site
        self.seen = np.zeros(S, dtype=bool)
        self.levels = [np.linspace(0.0, 1.2 * self.cap[s], self.GRID) for s in range(S)]
        self.grid = [ctx.grid_ager(int(self.c[s]), self.levels[s]) for s in range(S)]
        self.raw_risk = [np.zeros(self.GRID) for _ in range(S)]
        self.plan_risk = np.zeros(S)
        self.plan_t = -1e9
        self.dirty, self.last_rx = False, -1e9
        self.k = np.ones(S)                                       # self-check factor per site
        self.P = np.full(S, self.CHECK_PRIOR)                     # smoothed predicted risk of my answered frames
        self.L = np.full(S, self.CHECK_PRIOR)                     # smoothed share of them that were late
        self.pred_of = {}

    def on_report(self, now, s, q, g, A):
        if g <= self.g[s]:
            return                                                # an older report arriving late: ignore
        self.q[s], self.g[s] = q, g
        r = A / self.W
        self.rate[s] = r if not self.seen[s] else self.EWMA * r + (1 - self.EWMA) * self.rate[s]
        self.seen[s] = True
        self.dirty, self.last_rx = True, now

    def _cost(self, s, cost, x):
        """Expected late frames per second at site s if it gets x frames per second."""
        lv = self.levels[s]
        if x <= lv[-1]:
            return float(np.interp(x, lv, cost))
        return float(cost[-1] + (x - lv[-1]))                     # beyond 120% of capacity: every extra frame late

    def _plan(self, now):
        if not self.seen.all():
            return
        total = float(self.rate.sum())
        if total <= 0:
            return
        S, H, M = self.S, self.W, self.POINTS
        cost = []
        for s in range(S):
            ga, lv = self.grid[s], self.levels[s]
            idx = int(np.argmin(np.abs(lv - self.p[s] * total)))           # traffic level of the current plan
            b0 = ga.age_one(point(self.q[s]), max(0.0, now - self.g[s]), idx)   # the report, aged to now
            B = ga.age_all(np.repeat(b0[None, :], self.GRID, axis=0), self.d[s] / 2 + H / (2 * M))
            acc = B @ self.late[s]
            for _ in range(M - 1):
                B = ga.age_all(B, H / M)
                acc = acc + B @ self.late[s]
            self.raw_risk[s] = acc / M                                    # average chance of being late, per level
            cost.append(lv * np.minimum(1.0, self.k[s] * self.raw_risk[s]))
        lam = np.zeros(S)
        step = total / self.CHUNKS
        limit = self.U_MAX * self.cap
        cur = [0.0] * S
        for _ in range(self.CHUNKS):                                      # give each 1% to the cheapest site
            best, best_key, best_v = -1, None, 0.0
            for s in range(S):
                if lam[s] + step > limit[s] + 1e-9:
                    continue                                              # that site would go above 95% of capacity
                v = self._cost(s, cost[s], lam[s] + step)
                key = (v - cur[s], (lam[s] + step) / self.cap[s])         # equal cost: the less loaded site
                if best_key is None or key < best_key:
                    best, best_key, best_v = s, key, v
            if best < 0:                                                  # every site at its limit:
                lam += (total - lam.sum()) * self.cap / self.cap.sum()   # share the rest by capacity
                break
            lam[best] += step
            cur[best] = best_v
        self.p = lam / total
        self.plan_risk = np.array([np.interp(lam[s], self.levels[s], self.raw_risk[s]) for s in range(S)])
        self.plan_t = now

    def choose(self, now):
        if self.dirty and now >= self.last_rx + self.SETTLE:
            self._plan(now)
            self.dirty = False
        p = self.p
        age = now - self.plan_t
        if age > self.W:                                          # no fresh plan: slide back to the capacity split
            w = math.exp(-(age - self.W) / self.W)
            p = w * p + (1 - w) * self.pi
        self.credit += p                                          # take turns with the planned shares
        s = int(np.argmax(self.credit))
        self.credit[s] -= 1.0
        raw = float(self.plan_risk[s])
        if self.self_check:
            self.pred_of[self.ctx.frame] = (s, raw)
        return s, min(1.0, float(self.k[s]) * raw)

    def on_reply(self, now, s, delay, frame):
        rec = self.pred_of.pop(frame, None)
        if rec is None:
            return
        s0, raw = rec
        a = self.CHECK_RATE
        self.P[s0] = (1 - a) * self.P[s0] + a * raw
        self.L[s0] = (1 - a) * self.L[s0] + a * (1.0 if delay > self.D else 0.0)
        self.k[s0] = float(np.clip((self.L[s0] + self.CHECK_EPS) / (self.P[s0] + self.CHECK_EPS),
                                   self.CHECK_MIN, self.CHECK_MAX))


class SplitCheck(SplitRule):
    self_check = True
    needs_replies = True


# ====================================================================== round 3: measured speeds
class SpeedMeter:
    """Measures how many servers each site really has, from the reports this ingress already receives.

    Between two consecutive reports of a site:   frames served = arrivals counter A - (q now - q before).
      1. MEASURED: that is the site's real speed only if its servers never sat idle, so it is measured only after
         the queue stayed long (at least BUSY x the servers the site is said to have, at every report) for at
         least max(W, MIN_SPAN) seconds, pooled over up to max(2 W, MAX_SPAN) seconds. The estimate (whole
         servers, from 1 to the configured number) moves to the rounded measurement only when that is more than
         half a server plus Z standard errors away from it.
      2. SERVED MORE: a site can never serve more than it can, so the frames it served over the last
         max(2 W, MAX_SPAN) seconds (busy or not) are a lower bound; if they prove more servers than the estimate
         (beyond Z standard errors), the estimate goes up at once.
      3. QUIET SPELL: a site measured slower gets one server back after max(BACK_BASE, 4 W) seconds without a long
         queue and with less than one frame waiting beyond its measured servers on average. If it then turns out
         to be still slow (measured lower again soon after), its next quiet spell is twice as long (at most
         BACK_CAP x the base).
    """
    BUSY = 2.0                      # queue >= 2 x configured servers at every report
    MIN_SPAN, MAX_SPAN = 5.0, 10.0  # measure after >= max(W, 5 s) of long queue; pool up to max(2 W, 10 s)
    Z = 2.0                         # standard errors of margin
    BACK_BASE, BACK_CAP = 20.0, 8   # quiet spell before trusting one more server: max(20 s, 4 W), doubling

    def __init__(self, c_told, mu, scv, W):
        self.told = np.array(c_told, dtype=int)
        self.c = self.told.copy()                        # current estimate, whole servers
        self.mu, self.scv, self.W = float(mu), float(scv), float(W)
        S = len(self.told)
        self.prev = [None] * S                           # (time measured, frames) of the last report
        self.span = [deque() for _ in range(S)]          # pooled busy windows: (frames served, seconds)
        self.recent = [deque() for _ in range(S)]        # all recent windows, for the lower bound
        self.min_span = max(self.W, self.MIN_SPAN)
        self.max_span = max(2.0 * self.W, self.MAX_SPAN)
        self.base = max(self.BACK_BASE, 4.0 * self.W)
        self.back = np.full(S, self.base)                # current quiet spell per site
        self.quiet_since = np.zeros(S)
        self.w_sum, self.w_n = np.zeros(S), np.zeros(S)  # frames waiting beyond the measured servers, this spell
        self.up_at = np.full(S, -1e9)                    # when the site last got a server back after a spell
        self.log = []                                    # every change: (time measured, site, new estimate)

    def _pool(self, dq, item):
        dq.append(item)
        while len(dq) > 1 and sum(d for _, d in dq) - dq[0][1] >= self.max_span - 1e-9:
            dq.popleft()
        return sum(x for x, _ in dq), sum(d for _, d in dq)

    def update(self, s, q, g, A, X=0):
        """One new report of site s (newer than any before). Returns True if the estimate changed.
        X (v5 study) = frames the site discarded in the window (deadline-aware sites only; otherwise 0, and then
        everything below is exactly the round-3 meter): they left without being served, and a site that discards
        had every server busy (counted as a long queue when at least every server was occupied at both reports)."""
        p, self.prev[s] = self.prev[s], (g, q)
        if p is None:
            self._quiet(s, g)
            return False
        g0, q0 = p
        dur = g - g0
        if abs(dur - self.W) > 0.25 * self.W:            # a report is missing: start the evidence again
            self.span[s].clear()
            self.recent[s].clear()
            return False
        served_w = A - X - (q - q0)
        busy = min(q0, q) >= self.BUSY * self.told[s] or (X > 0 and min(q0, q) >= self.told[s])
        # 2. served more than the estimate allows: raise at once
        served, T = self._pool(self.recent[s], (served_w, dur))
        if T >= self.min_span - 1e-9:
            lb = served / (self.mu * T)
            k = min(int(math.ceil(lb - self.Z * math.sqrt(self.scv * max(lb, 1.0) / (self.mu * T)) - 1e-9)),
                    int(self.told[s]))                   # never above the configured size
            if k > self.c[s]:
                return self._set(s, k, g)
        # 1. measured while the queue stayed long
        if busy:
            self._quiet(s, g)
            served, T = self._pool(self.span[s], (served_w, dur))
            if T < self.min_span - 1e-9:
                return False                             # the queue has not been long for long enough yet
            est = served / (self.mu * T)                 # servers' worth of work done
            se = math.sqrt(self.scv * max(est, 1.0) / (self.mu * T))
            new = int(min(max(math.floor(est + 0.5), 1), self.told[s]))
            if new != self.c[s] and abs(est - self.c[s]) > 0.5 + self.Z * se:
                if new < self.c[s]:                      # slower: was a recent return wrong?
                    recent = g - self.up_at[s] <= 2.0 * self.back[s]
                    self.back[s] = min(2.0 * self.back[s], self.BACK_CAP * self.base) if recent else self.base
                return self._set(s, new, g)
            return False
        # 3. a quiet spell
        self.span[s].clear()
        self.w_sum[s] += max(0.0, q - self.c[s])
        self.w_n[s] += 1
        if g - self.quiet_since[s] >= self.back[s]:
            if self.c[s] < self.told[s] and self.w_sum[s] / self.w_n[s] < 1.0:
                self.up_at[s] = g
                return self._set(s, int(self.c[s]) + 1, g)
            self._quiet(s, g)                            # not lightly loaded (or nothing to give back): start again
        return False

    def _quiet(self, s, g):
        self.quiet_since[s] = g
        self.w_sum[s] = self.w_n[s] = 0.0

    def _set(self, s, c, g):
        self.c[s] = c
        self._quiet(s, g)
        self.span[s].clear()
        self.recent[s].clear()                           # new evidence only from now on
        self.log.append([round(float(g), 3), int(s), int(c)])
        return True


def usable_capacity(meter, mu, total, u_max):
    """Frames per second each site can take, from the measured servers. If those cannot carry the measured
    traffic at u_max, the sites measured below their configured size get back just enough of the difference
    (a low measurement must not push the healthy sites over the limit; if a site really is that slow, its queue
    grows and it is measured again)."""
    cap = meter.c * mu
    need = total / u_max
    missing = (meter.told - meter.c) * mu
    if cap.sum() < need and missing.sum() > 0:
        cap = cap + min(1.0, (need - cap.sum()) / missing.sum()) * missing
    return cap.astype(float)


class SplitSpeed(SplitRule):
    """OURS V2 + MEASURED SPEEDS (round 3). Ours v2 with two changes:
      1. each site's working servers are measured from the reports (SpeedMeter) and used everywhere in the
         model: late(n), the belief ageing, the 95% limit and the capacity split it slides back to. If the
         measured capacities cannot carry the measured traffic at 95%, the sites measured below their configured
         size get back just enough capacity in the limit (usable_capacity);
      2. the plan also counts the backlog it leaves behind. Every frame still queued at the end of the interval,
         beyond the queue at which a new frame is late with chance 1/2, counts as rho / (1 - rho) late frames:
         at load rho, clearing one extra frame takes as long as rho / (1 - rho) new arrivals, which are late
         meanwhile. That end-of-interval queue comes from the average (fluid) model, so it has no upper cap.
    No self-check."""
    LATE_SAFE = 0.5
    RHO_MAX = 0.95

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        self.meter = SpeedMeter(ctx.c, ctx.mu, ctx.scv, ctx.W)
        self.models = {}

    def _model(self, s):
        """(servers, traffic levels, ager, late(n), safe queue) for the CURRENT measured servers of site s."""
        c = int(self.meter.c[s])
        m = self.models.get((s, c))
        if m is None:
            lv = np.linspace(0.0, 1.2 * (c * self.ctx.mu), self.GRID)
            late = self.ctx.late_for(self.i, s, c)
            ok = np.flatnonzero(late <= self.LATE_SAFE)
            n_safe = max(c, int(ok[-1]) if len(ok) else 0)
            m = (c, lv, self.ctx.grid_ager(c, lv), late, n_safe)
            self.models[(s, c)] = m
        return m

    def on_report(self, now, s, q, g, A):
        self.on_report_x(now, s, q, g, A, 0)

    def on_report_x(self, now, s, q, g, A, X):
        if g <= self.g[s]:
            return
        self.meter.update(s, q, g, A, X)
        SplitRule.on_report(self, now, s, q, g, A)

    def _plan(self, now):
        if not self.seen.all():
            return
        total = float(self.rate.sum())
        if total <= 0:
            return
        S, H, M, mu = self.S, self.W, self.POINTS, self.ctx.mu
        models = [self._model(s) for s in range(S)]
        cap = usable_capacity(self.meter, mu, total, self.U_MAX)  # measured; topped up if it cannot carry the traffic
        rho = min(self.RHO_MAX, total / cap.sum())
        kappa = rho / (1.0 - rho)                         # late frames per leftover frame
        costs, risks = [], []
        for s, (c, lv, ga, late, n_safe) in enumerate(models):
            lam_now = self.p[s] * total
            idx = int(np.argmin(np.abs(lv - lam_now)))
            age = max(0.0, now - self.g[s])
            b0 = ga.age_one(point(self.q[s]), age, idx)                    # the report, aged to now
            B = ga.age_all(np.repeat(b0[None, :], self.GRID, axis=0), self.d[s] / 2 + H / (2 * M))
            acc = B @ late
            for _ in range(M - 1):
                B = ga.age_all(B, H / M)
                acc = acc + B @ late
            r = acc / M                                                    # average chance of being late
            n_now = fluid(float(self.q[s]), lam_now, c, mu, age)
            back = np.array([max(0.0, fluid(n_now, float(x), c, mu, H) - n_safe) for x in lv])
            risks.append(r)
            costs.append(lv * np.minimum(1.0, r) + kappa * back / H)       # late frames per second
        lam = np.zeros(S)
        step = total / self.CHUNKS
        limit = self.U_MAX * cap
        cur = [0.0] * S
        slope = 1.0 + kappa                                # beyond 120% of capacity: late, and left behind
        for _ in range(self.CHUNKS):
            best, best_key, best_v = -1, None, 0.0
            for s in range(S):
                x = lam[s] + step
                if x > limit[s] + 1e-9:
                    continue
                lv = models[s][1]
                v = float(np.interp(x, lv, costs[s])) if x <= lv[-1] else float(costs[s][-1] + slope * (x - lv[-1]))
                key = (v - cur[s], x / cap[s])
                if best_key is None or key < best_key:
                    best, best_key, best_v = s, key, v
            if best < 0:                                   # every site at its limit: share the rest by capacity
                lam += (total - lam.sum()) * cap / cap.sum()
                break
            lam[best] += step
            cur[best] = best_v
        self.p = lam / total
        self.pi = cap / cap.sum()
        self.plan_risk = np.array([np.interp(lam[s], models[s][1], risks[s]) for s in range(S)])
        self.plan_t = now

    def diag(self):
        return {"speed_changes": self.meter.log}


class WRRSpeed(Rule):
    """CONTROL for ours v2 + measured speeds (round 3): smooth weighted round-robin whose weights are the capacities
    measured from the reports by the same SpeedMeter (and topped up the same way when they cannot carry the
    traffic), instead of the configured ones. Same reports and counter as ours, no model of the queues. With
    nothing measured it decides exactly like weighted round-robin."""
    uses_counter = True
    EWMA = SplitRule.EWMA
    U_MAX = SplitRule.U_MAX

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        self.meter = SpeedMeter(ctx.c, ctx.mu, ctx.scv, ctx.W)
        self.cur = np.zeros(self.S)
        self.last_g = np.full(self.S, -1e9)
        self.rate = np.zeros(self.S)
        self.seen = np.zeros(self.S, dtype=bool)
        self.w = self.c.copy()

    def on_report(self, now, s, q, g, A):
        self.on_report_x(now, s, q, g, A, 0)

    def on_report_x(self, now, s, q, g, A, X):
        if g <= self.last_g[s]:
            return
        self.last_g[s] = g
        r = A / self.ctx.W
        self.rate[s] = r if not self.seen[s] else self.EWMA * r + (1 - self.EWMA) * self.rate[s]
        self.seen[s] = True
        self.meter.update(s, q, g, A, X)
        self._after_report(now)

    def _after_report(self, now):
        if (self.meter.c == self.meter.told).all():
            self.w = self.c                              # nothing measured: exactly weighted round-robin
        else:
            self.w = usable_capacity(self.meter, self.ctx.mu, float(self.rate.sum()), self.U_MAX) / self.ctx.mu

    def choose(self, now):
        w = self.w
        self.cur += w
        s = int(np.argmax(self.cur))
        self.cur[s] -= w.sum()
        return s, NAN

    def diag(self):
        return {"speed_changes": self.meter.log}


# ====================================================================== Dahlin-style: one aged number
class Dahlin(Rule):
    """Ages the report into ONE number: n(t) follows dn/dt = (others' arrival rate) - mu*min(n, c),
    plus +1 for each own frame. Then scores that one number with the same late(n) as ours.
    (Dahlin's paper also splits frames at random to avoid herding; this deterministic version does not.)"""
    predicts = True
    uses_counter = True

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        S = self.S
        self.late = ctx.late[i]
        self.est = CounterEstimate(S)
        self.own = OwnLog(S)
        self.n = np.zeros(S)
        self.tn = np.zeros(S)
        self.lam = np.zeros(S)
        self.last_g = np.full(S, -1e9)
        self.mu = ctx.mu

    def _advance(self, s, t):
        if t > self.tn[s]:
            self.n[s] = fluid(self.n[s], self.lam[s], int(self.c[s]), self.mu, t - self.tn[s])
            self.tn[s] = t

    def on_report(self, now, s, q, g, A):
        if g <= self.last_g[s]:
            return
        self.last_g[s] = g
        W = self.ctx.W
        self.est.update(s, A, self.own.count_window(s, g, W), W)
        self.lam[s] = self.est.other_rate(s)
        self.n[s], self.tn[s] = float(q), g
        for st, _ in self.own.after(s, g):
            self._advance(s, max(st, g))
            self.n[s] += 1.0
        self._advance(s, now)
        self.own.prune(s, g - W - 1.0)

    def on_send(self, now, s):
        self._advance(s, now)
        self.n[s] += 1.0
        self.own.add(s, now, now + self.d[s] / 2)

    def choose(self, now):
        risk = np.empty(self.S)
        for s in range(self.S):
            self._advance(s, now)
            na = fluid(self.n[s], self.lam[s], int(self.c[s]), self.mu, self.d[s] / 2)
            lo = min(int(na), len(self.late[s]) - 2)
            f = min(max(na - lo, 0.0), 1.0)
            risk[s] = (1 - f) * self.late[s][lo] + f * self.late[s][lo + 1]
        s = self._argmin_random(risk)
        return s, float(risk[s])


# ====================================================================== Liyanage-style (2026)
class Liyanage(Rule):
    """After Liyanage et al. 2026: each CLIENT measures the end-to-end delay of its own frames.
    Our adaptation: a client = one camera (about 10 frames/s), so an ingress runs several clients.
    Per client and site: mean and spread over the last 10 s (at least the last 5 measurements, so a
    bad site is not forgotten). A site is feasible if both the Normal estimate and the Cantelli bound
    of P(delay > D) are at most 15%. Among feasible sites, lowest mean + 1.645 * spread.
    Hysteresis: switch only if a challenger is at least 5% better for 5 decisions in a row
    (or at once if the current site is no longer feasible). Uses no reports."""
    uses_reports = False
    needs_replies = True
    predicts = True
    WINDOW, EPS, K, MARGIN, STREAK, MIN_SAMPLES, MAX_SAMPLES = 10.0, 0.15, 1.645, 0.05, 5, 5, 200
    FRAMES_PER_CLIENT = 10.0

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        m = 1.0 / ctx.mu
        self.D = ctx.D
        self.prior_mean = self.d + m                       # before any measurement: no queueing
        self.prior_sd = m * math.sqrt(ctx.scv)
        self.n_clients = max(1, int(round(ctx.ingress_rate[i] / self.FRAMES_PER_CLIENT)))
        nc = self.n_clients
        self.samples = [[deque() for _ in range(self.S)] for _ in range(nc)]
        p = self.cap / self.cap.sum()
        self.cur = [int(x) for x in self.rng.choice(self.S, size=nc, p=p)]   # clients start spread by capacity
        self.challenger = [-1] * nc
        self.streak = [0] * nc

    def on_reply(self, now, s, delay, frame):
        self.samples[frame % self.n_clients][s].append((now, delay))

    def _stats(self, k, s, now):
        dq = self.samples[k][s]
        while len(dq) > self.MIN_SAMPLES and dq[0][0] < now - self.WINDOW:
            dq.popleft()                                  # sliding 10 s window, but keep the last few samples
        while len(dq) > self.MAX_SAMPLES:
            dq.popleft()
        n = len(dq)
        if n == 0:
            return self.prior_mean[s], self.prior_sd
        x = np.fromiter((v for _, v in dq), float, n)
        mean, var = x.mean(), x.var()
        if n < self.MIN_SAMPLES:                          # blend with the prior until there are enough samples
            wp = (self.MIN_SAMPLES - n) / self.MIN_SAMPLES
            pm, pv = self.prior_mean[s], self.prior_sd ** 2
            m2 = (1 - wp) * mean + wp * pm
            var = (1 - wp) * (var + (mean - m2) ** 2) + wp * (pv + (pm - m2) ** 2)
            mean = m2
        return mean, max(math.sqrt(var), 1e-3)

    def choose(self, now):
        k = self.ctx.frame % self.n_clients              # which camera this frame comes from
        S = self.S
        mu_ = np.empty(S)
        sd = np.empty(S)
        for s in range(S):
            mu_[s], sd[s] = self._stats(k, s, now)
        gap = self.D - mu_
        p_norm = 0.5 * np.array([math.erfc(z / math.sqrt(2)) for z in gap / sd])
        p_cant = np.where(gap > 0, sd ** 2 / (sd ** 2 + np.maximum(gap, 1e-9) ** 2), 1.0)
        score = mu_ + self.K * sd
        feas = (p_norm <= self.EPS) & (p_cant <= self.EPS)
        pool = np.flatnonzero(feas) if feas.any() else np.arange(S)
        best = int(pool[np.argmin(score[pool])])
        cur = self.cur[k]
        if best == cur:
            self.streak[k] = 0
        elif feas.any() and not feas[cur]:
            self.cur[k], self.streak[k] = best, 0          # current site no longer feasible: switch now
        elif score[best] <= (1 - self.MARGIN) * score[cur]:
            self.streak[k] = self.streak[k] + 1 if best == self.challenger[k] else 1
            self.challenger[k] = best
            if self.streak[k] >= self.STREAK:
                self.cur[k], self.streak[k] = best, 0
        else:
            self.streak[k] = 0
        return self.cur[k], float(p_norm[self.cur[k]])


# ====================================================================== Prequal-style probing
class Prequal(Rule):
    """After Prequal (NSDI 2024), at the SAME bytes per second as the reports: instead of receiving reports,
    the ingress spends that budget on probes (request + reply) to random sites. Like Prequal, each probe
    answer is used at most REUSE times and then dropped (this avoids herding on one old answer); with no
    usable answer, it picks a site at random in proportion to capacity. Among usable answers it takes
    the lowest expected delay (SED). Our simplification of Prequal's selection rule."""
    uses_reports = False
    PROBE_BYTES = 124
    REUSE = 2
    MAX_AGE = 2.0

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        self.rate = self.S * (ctx.report_bytes + ctx.counter_bytes) / ctx.W   # bytes/s this ingress would get
        self.tokens = self.PROBE_BYTES                     # one probe at the start
        self.t_last = 0.0
        self.pool = []                                     # [site, q, time measured, uses left]
        self.p = self.cap / self.cap.sum()

    def on_probe(self, now, s, q, t_meas):
        self.pool = [e for e in self.pool if e[0] != s]    # keep only the newest answer per site
        self.pool.append([s, q, t_meas, self.REUSE])

    def choose(self, now):
        self.tokens = min(self.tokens + (now - self.t_last) * self.rate, 4 * self.PROBE_BYTES)
        self.t_last = now
        if self.tokens >= self.PROBE_BYTES:
            self.tokens -= self.PROBE_BYTES
            self.probe_bytes += self.PROBE_BYTES
            self.probe_out.append(int(self.rng.integers(self.S)))
        self.pool = [e for e in self.pool if e[3] > 0 and now - e[2] <= self.MAX_AGE]
        if not self.pool:
            return int(self.rng.choice(self.S, p=self.p)), NAN
        sed = [(e[1] + 1.0) / self.cap[e[0]] + self.d[e[0]] for e in self.pool]
        e = self.pool[int(np.argmin(sed))]
        e[3] -= 1
        return int(e[0]), NAN


# ====================================================================== oracle
class Oracle(Rule):
    """Knows the true number of frames (and working servers, and their speed) at every site right now --
    impossible in practice; lowest risk. A best-case reference, not a competitor."""
    uses_reports = False
    oracle = True            # the only kind of rule allowed to read the true state

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        self.late = ctx.late[i]
        self.N = len(self.late[0])

    def choose(self, now):
        n = self.ctx.nsys
        c_now = self.ctx.c_now
        spd = self.ctx.speed_now
        risk = np.array([self.ctx.late_true(self.i, s, c_now[s], spd[s])[min(n[s], self.N - 1)]
                         for s in range(self.S)])
        best = np.flatnonzero(risk <= risk.min() + 1e-12)
        if len(best) > 1:
            free = np.array([(c_now[s] - n[s]) / c_now[s] for s in best])
            best = best[free >= free.max() - 1e-12]
        s = int(best[0]) if len(best) == 1 else int(self.rng.choice(best))
        return s, float(risk[s])


RULE_CLASSES = {
    "ours": Ours, "ours_v2": SplitRule, "ours_v2_check": SplitCheck, "ours_v2_speed": SplitSpeed,
    "expected_delay": ExpectedDelay, "dahlin": Dahlin, "liyanage": Liyanage,
    "lsq": LSQ, "timeout_sed": TimeoutSED, "power_of_two": PowerOfTwo, "wpow2_stale": WPow2Stale,
    "prequal": Prequal, "nearest": Nearest, "cap_random": CapRandom, "wrr": WRR, "wrr_speed": WRRSpeed,
    "oracle": Oracle,
    "ours_no_counting": OursNoCounting, "ours_no_ageing": OursNoAgeing,
    "ours_exp_late": OursExpLate, "ours_no_ties": OursNoTies,
}

# the v5 study (ours v5, v4, rivals that may drop): defined in rules_v5.py, registered here
from .rules_v5 import V5_RULE_CLASSES  # noqa: E402

RULE_CLASSES.update(V5_RULE_CLASSES)

# the v6 study (ours v6 and its ablations): defined in rules_v6.py, registered here
from .rules_v6 import V6_RULE_CLASSES  # noqa: E402

RULE_CLASSES.update(V6_RULE_CLASSES)

# the staleness study (Nov 2026) registers its baselines from catsim/baselines.py (imported by engine.py)
