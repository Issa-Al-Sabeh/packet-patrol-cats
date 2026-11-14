"""The v5 study: ours v5, the teammate's v4 (ported from its report), and versions of the rivals that may drop.

A rule drops a frame by returning site -1 from choose(): the frame is never sent and counts as one miss.
Every rule here uses only what an ingress could know (the same reports, the same 4-byte counter, its own frames,
and for ours v5 the answers to its own frames), except the oracle, which is a reference.
"""
import math
from collections import deque

import numpy as np
from scipy.special import ndtr

from .queueing import fluid, point
from .rules import NAN, BeliefRule, OwnLog, Rule, SplitRule, SplitSpeed, WRRSpeed, usable_capacity


class OwnDrops:
    """This ingress's own frames and whether it dropped them. The sites count only the frames that reach them,
    so the traffic the cameras really offer is: counted / (1 - drop share). Every ingress drops (nearly) the same
    share, because they all compute the same plan from the same reports, so its own share stands for everyone's."""
    MAX = 0.9

    def __init__(self):
        self.log = deque()                         # (time, dropped?)

    def add(self, t, dropped):
        self.log.append((t, dropped))

    def share(self, t0, t1):
        n = d = 0
        for t, x in self.log:
            if t0 < t <= t1:
                n += 1
                d += x
        return min(self.MAX, d / n) if n else 0.0

    def prune(self, older_than):
        lg = self.log
        while lg and lg[0][0] < older_than:
            lg.popleft()


def _offered(own, rate_off, seen, s, A, g, W, ewma):
    """Update the EWMA of the traffic OFFERED to site s's counter window (arrivals corrected for drops)."""
    r = A / W / (1.0 - own.share(g - W, g))
    rate_off[s] = r if not seen[s] else ewma * r + (1 - ewma) * rate_off[s]


# ====================================================================== OURS V5
class SplitDrop(SplitSpeed):
    """OURS V5 = ours v2 + measured speeds, plus three ideas from v4.

    The plan for the next report interval has one more option besides the sites: DROP, which costs exactly one
    missed frame. Each 1% of the traffic goes to the option that adds the fewest expected late frames: a site
    costs that frame's own chance of being late plus the harm it does to the others (the extra late frames, and
    the backlog it leaves, rho / (1 - rho) late frames per leftover frame, as in v2 + speeds). So a frame is dropped
    only when every site would cost more than one miss for it, and only in overload (see below).
      1. drop instead of overfilling: when every site is at 95% of its usable capacity, the rest is dropped
         (v2 + speeds shared it out by capacity, overfilling every site);
      2. the traffic the cameras offer = the arrivals the counters saw / (1 - this ingress's drop share), so the
         plan sees the overload it is hiding (v4 counts k x its drops for the same reason);
      3. a site where even an empty queue would make this ingress's frames late with chance > 1/2 is never planned
         (v4's report found its balancing mode sending to such sites).
    Only in overload (added after the pilot, pass 1): the drop option exists only while the offered traffic is above
    95% of the MEASURED capacity (the configured one until the meter measures a change), as v4 never drops below
    capacity. In pass 1 v5 also dropped below capacity, trading sure misses for model-estimated harm (0.8% of frames
    in the main scenario), and with wrong weights its drops kept the DC's queue short, so the meter never saw that the
    DC had only 6 servers (missed 28% vs 14% for v2 + speeds).
    Calibrated (the default): whether sending beats dropping depends on the absolute size of the risk, which the
    model over-estimates (v2: 19% predicted vs 4% late in the main scenario). So for that one comparison the risk
    part is scaled by (late / predicted) over this ingress's own answered frames (about the last 100), as the
    self-check of v2 does per site. Until it has CAL_MIN answers to calibrate with, v5 does not drop at all (it is
    then exactly v2 + speeds). Which SITE gets a frame is decided exactly as in v2 + speeds (no scaling), so while
    v5 drops nothing it sends every frame exactly where v2 + speeds would.
    """
    DROP_COST = 1.0
    CAL_MIN = 100             # answers (to frames sent under a plan) before the calibrated drop option is used.
                              # Found while testing the code on a throwaway seed: without it, the first plan of the
                              # main scenario dropped 26% of the frames (nothing to calibrate with yet).
    calibrated = True
    needs_replies = True
    U_LIMIT = SplitRule.U_MAX                 # 95%, as in v2 + speeds

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        S = self.S
        self.own_log = OwnDrops()
        self.rate_off = np.zeros(S)
        self.p_drop = 0.0
        self.credit = np.zeros(S + 1)             # the last slot is the drop option
        self.Pg = self.Lg = self.CHECK_PRIOR      # calibration: smoothed predicted risk / share late, own answers
        self.kcal = 1.0
        self.n_cal = 0
        self.pred_raw = {}
        self.useless = np.zeros(S, dtype=bool)
        self.drop_log = []                        # [plan time, planned drop share], when it changes

    # ---- information
    def on_report_x(self, now, s, q, g, A, X):
        if g <= self.g[s]:
            return
        _offered(self.own_log, self.rate_off, self.seen, s, A, g, self.W, self.EWMA)
        self.own_log.prune(now - 2.0 * self.W - 5.0)
        super().on_report_x(now, s, q, g, A, X)

    def on_send(self, now, s):
        self.own_log.add(now, False)

    def on_drop(self, now):
        self.own_log.add(now, True)

    def on_reply(self, now, s, delay, frame):
        raw = self.pred_raw.pop(frame, None)
        if raw is None or not self.calibrated:
            return
        a = self.CHECK_RATE
        self.n_cal += 1
        self.Pg = (1 - a) * self.Pg + a * raw
        self.Lg = (1 - a) * self.Lg + a * (1.0 if delay > self.D else 0.0)
        self.kcal = float(np.clip((self.Lg + self.CHECK_EPS) / (self.Pg + self.CHECK_EPS),
                                  self.CHECK_MIN, self.CHECK_MAX))

    # ---- the plan
    def _plan(self, now):
        if not self.seen.all():
            return
        total = float(self.rate_off.sum())                # offered by the cameras (dropped frames included)
        if total <= 0:
            return
        S, H, M, mu = self.S, self.W, self.POINTS, self.ctx.mu
        models = [self._model(s) for s in range(S)]
        self.useless = np.array([m[3][0] > self.LATE_SAFE for m in models])
        if self.useless.all():
            self.useless[:] = False                       # nothing is usable: keep the plain plan
        cap = usable_capacity(self.meter, mu, total, self.U_MAX)
        rho = min(self.RHO_MAX, total / cap.sum())
        kappa = rho / (1.0 - rho)
        kc = self.kcal if self.calibrated else 1.0
        overload = total > self.U_LIMIT * float((self.meter.c * mu).sum())   # above 95% of the MEASURED capacity
        may_drop = overload and (self.n_cal >= self.CAL_MIN or not self.calibrated)
        raw_c, cal_c, risks = [], [], []
        for s, (c, lv, ga, late, n_safe) in enumerate(models):
            lam_now = self.p[s] * total
            idx = int(np.argmin(np.abs(lv - lam_now)))
            age = max(0.0, now - self.g[s])
            b0 = ga.age_one(point(self.q[s]), age, idx)
            B = ga.age_all(np.repeat(b0[None, :], self.GRID, axis=0), self.d[s] / 2 + H / (2 * M))
            acc = B @ late
            for _ in range(M - 1):
                B = ga.age_all(B, H / M)
                acc = acc + B @ late
            r = acc / M
            n_now = fluid(float(self.q[s]), lam_now, c, mu, age)
            back = kappa * np.array([max(0.0, fluid(n_now, float(x), c, mu, H) - n_safe) for x in lv]) / H
            risks.append(r)
            raw_c.append(lv * np.minimum(1.0, r) + back)               # exactly the cost of v2 + speeds
            cal_c.append(lv * np.minimum(1.0, kc * r) + back)          # the same with the calibrated risk
        lam = np.zeros(S)
        drop = 0.0
        step = total / self.CHUNKS
        limit = np.where(self.useless, 0.0, self.U_LIMIT * cap)
        cur_raw, cur_cal = [0.0] * S, [0.0] * S
        slope = 1.0 + kappa

        def at(curve, s, x):
            lv = models[s][1]
            return float(np.interp(x, lv, curve[s])) if x <= lv[-1] else float(curve[s][-1] + slope * (x - lv[-1]))

        for _ in range(self.CHUNKS):
            best, best_key = -1, None
            for s in range(S):
                x = lam[s] + step
                if x > limit[s] + 1e-9:
                    continue
                key = (at(raw_c, s, x) - cur_raw[s], x / cap[s])
                if best_key is None or key < best_key:
                    best, best_key = s, key
            if best >= 0:
                x = lam[best] + step
                v_cal = at(cal_c, best, x)
                if not may_drop or v_cal - cur_cal[best] <= step * self.DROP_COST + 1e-12:   # at most one miss
                    lam[best] = x
                    cur_raw[best] = at(raw_c, best, x)
                    cur_cal[best] = v_cal
                    continue
            elif not may_drop:                             # not calibrated yet: exactly v2 + speeds
                lam += (total - lam.sum() - drop) * cap / cap.sum()
                break
            drop += step                                   # every site is full or costs more than a drop
        self.p = lam / total
        self.p_drop = drop / total
        ok = np.where(self.useless, 0.0, cap)
        self.pi = ok / ok.sum()
        self.plan_risk = np.array([np.interp(lam[s], models[s][1], risks[s]) for s in range(S)])
        self.plan_t = now
        pd = round(float(self.p_drop), 4)
        if (self.drop_log[-1][1] if self.drop_log else 0.0) != pd:
            self.drop_log.append([round(float(now), 3), pd])

    def choose(self, now):
        if self.dirty and now >= self.last_rx + self.SETTLE:
            self._plan(now)
            self.dirty = False
        S = self.S
        p, pd = self.p, self.p_drop
        age = now - self.plan_t
        if age > self.W:                                  # no fresh plan: slide back to the capacity split
            w = math.exp(-(age - self.W) / self.W)
            p, pd = w * p + (1 - w) * self.pi, w * pd
        cr = self.credit
        cr[:S] += p
        cr[S] += pd
        j = int(np.argmax(cr))
        cr[j] -= 1.0
        if j == S:
            return -1, 1.0
        raw = float(self.plan_risk[j])
        if self.calibrated and self.plan_t > -1e8:        # only frames sent under a plan say how good it is
            self.pred_raw[self.ctx.frame] = raw
        return j, min(1.0, raw)

    def diag(self):
        return {"speed_changes": self.meter.log, "drop_plan": self.drop_log, "kcal": round(self.kcal, 4)}


class SplitDropRaw(SplitDrop):
    """Pilot variant of ours v5: the same, without the calibration (the model's own risk decides send vs drop)."""
    calibrated = False
    needs_replies = False


# ====================================================================== v4 (teammate), ported
class TeammateV4(Rule):
    """v4, the teammate's rule, ported from its report ("Packet Patrol stress test of v4", 31 Oct 2026):
      every report: k = all frames / my frames (from the counters);
      overload check: total traffic (frames that reached the sites + k x my drops) vs the total capacity;
      below capacity: the site with the least (reported queue + k x my sends since the report) / site speed; never
      drops;
      overloaded: queue now = reported + k x my sends - speed x time since the report, and how unsure that is;
      score = this frame's miss chance + the harm it does to the frames queued behind it; lowest score; drop when
      even the best score is above 1 + a small margin (dropping costs exactly one miss).
    Where the description is silent, our choices: k uses the latest report of every site and is at least 1; the
    spread of the queue estimate is sqrt((k - 1) x my sends since + speed x time since), arrivals and departures
    counted as Poisson; the miss chance is our late(n) table averaged over a Normal with that mean and spread; the
    harm is the chance that every server is busy when the frame arrives (in overload its work then pushes one other
    frame back by one job); margin 0.05; capacities as configured (v4 has no speed meter)."""
    uses_counter = True
    predicts = True
    drop = True
    MARGIN = 0.05

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        S = self.S
        self.late = ctx.late[i]
        self.N = len(self.late[0])
        self.nn = np.arange(self.N)
        self.q = np.zeros(S)
        self.g = np.full(S, -1e9)
        self.A = np.zeros(S)
        self.seen = np.zeros(S, dtype=bool)
        self.own = OwnLog(S)
        self.since = np.zeros(S)            # my frames that reached each site after its last report
        self.mine = np.zeros(S)             # my frames that reached each site in its last report window
        self.drops = deque()
        self.k = 1.0

    def on_report(self, now, s, q, g, A):
        if g <= self.g[s]:
            return
        W = self.ctx.W
        self.q[s], self.g[s], self.A[s], self.seen[s] = q, g, A, True
        self.mine[s] = self.own.count_window(s, g, W)
        self.since[s] = len(self.own.after(s, g))
        self.own.prune(s, g - W - 1.0)
        self.k = max(1.0, float(self.A[self.seen].sum()) / max(1.0, float(self.mine[self.seen].sum())))

    def on_send(self, now, s):
        self.since[s] += 1
        self.own.add(s, now, now + self.d[s] / 2)

    def on_drop(self, now):
        self.drops.append(now)

    def _belief(self, s, now):
        mean = self.q[s] + self.k * self.since[s] - self.cap[s] * max(0.0, now - self.g[s])
        mean = max(0.0, mean)
        sd = math.sqrt(max(self.k - 1.0, 0.0) * self.since[s] + self.cap[s] * max(0.0, now - self.g[s])) + 0.5
        cdf = ndtr((self.nn + 0.5 - mean) / sd)
        w = np.diff(np.concatenate(([0.0], cdf)))
        w[-1] += 1.0 - cdf[-1]
        return w

    def choose(self, now):
        W = self.ctx.W
        while self.drops and self.drops[0] < now - W:
            self.drops.popleft()
        if not self.seen.all():
            work = self.since / self.cap
            return self._argmin_random(work), NAN
        total = self.A.sum() / W + self.k * len(self.drops) / W
        if total <= self.cap.sum():                       # below capacity: least work per unit of speed
            work = (self.q + self.k * self.since) / self.cap
            return self._argmin_random(work), NAN
        score = np.empty(self.S)
        miss = np.empty(self.S)
        for s in range(self.S):
            w = self._belief(s, now)
            miss[s] = w @ self.late[s]
            score[s] = miss[s] + w[int(self.c[s]):].sum()  # own miss chance + harm (every server busy)
        s = self._argmin_random(score)
        if self.drop and score[s] > 1.0 + self.MARGIN:
            return -1, 1.0
        return s, float(miss[s])


class TeammateV4NoDrop(TeammateV4):
    """v4 with dropping turned off (as in v4's own report), to show how much of its result comes from dropping."""
    drop = False


# ====================================================================== the rivals, allowed to drop
class WRRDrop(Rule):
    """Weighted round-robin (configured capacities) that drops just enough frames to keep what it sends at 95% of
    the total capacity when the cameras offer more (offered traffic from the counters, corrected for its own drops
    exactly as in ours v5). The frames it sends follow exactly the round-robin order. Identical to weighted
    round-robin while the offered traffic stays below 95%."""
    uses_counter = True
    EWMA = SplitRule.EWMA
    U = SplitRule.U_MAX

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        S = self.S
        self.cur = np.zeros(S)
        self.w = self.c
        self.own_log = OwnDrops()
        self.rate_off = np.zeros(S)
        self.seen = np.zeros(S, dtype=bool)
        self.last_g = np.full(S, -1e9)
        self.last_rx = -1e9
        self.acc = 0.0
        self.p_drop = 0.0

    def on_report_x(self, now, s, q, g, A, X):
        if g <= self.last_g[s]:
            return
        self.last_g[s] = g
        self._count(now, s, g, A)
        self._weights()

    def _count(self, now, s, g, A):
        _offered(self.own_log, self.rate_off, self.seen, s, A, g, self.ctx.W, self.EWMA)
        self.seen[s] = True
        self.own_log.prune(now - 2.0 * self.ctx.W - 5.0)
        self.last_rx = now

    def _capacity(self):
        return float(self.cap.sum())

    def _weights(self):
        total = float(self.rate_off.sum()) if self.seen.all() else 0.0
        room = self.U * self._capacity()
        self.p_drop = 1.0 - room / total if total > room else 0.0

    def on_send(self, now, s):
        self.own_log.add(now, False)

    def on_drop(self, now):
        self.own_log.add(now, True)

    def choose(self, now):
        pd = self.p_drop
        age = now - self.last_rx
        if age > 2.0 * self.ctx.W:                        # reports stopped: stop dropping, gradually
            pd *= math.exp(-(age - 2.0 * self.ctx.W) / self.ctx.W)
        if pd > 0:
            self.acc += pd
            if self.acc >= 1.0:                           # drops evenly spread over the frames
                self.acc -= 1.0
                return -1, NAN
        w = self.w
        self.cur += w
        s = int(np.argmax(self.cur))
        self.cur[s] -= w.sum()
        return s, NAN


class WRRSpeedDrop(WRRSpeed):
    """Round-robin + measured speeds that drops instead of topping up: weights = the measured servers (the same
    meter as ours), and when the offered traffic is above 95% of the MEASURED capacity it drops just enough frames
    (same offered-traffic estimate as ours v5). Identical to round-robin + measured speeds while it drops nothing."""

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        self.own_log = OwnDrops()
        self.rate_off = np.zeros(self.S)
        self.last_rx = -1e9
        self.acc = 0.0
        self.p_drop = 0.0

    def on_report_x(self, now, s, q, g, A, X):
        if g <= self.last_g[s]:
            return
        _offered(self.own_log, self.rate_off, self.seen, s, A, g, self.ctx.W, self.EWMA)
        self.own_log.prune(now - 2.0 * self.ctx.W - 5.0)
        self.last_rx = now
        super().on_report_x(now, s, q, g, A, X)

    def _after_report(self, now):
        mu = self.ctx.mu
        measured = self.meter.c * mu
        total = float(self.rate_off.sum()) if self.seen.all() else 0.0
        room = self.U_MAX * float(measured.sum())
        self.p_drop = 1.0 - room / total if total > room else 0.0
        if (self.meter.c == self.meter.told).all():
            self.w = self.c                               # nothing measured: exactly weighted round-robin
        elif self.p_drop > 0:
            self.w = measured / mu                        # drop the excess instead of topping up
        else:
            self.w = usable_capacity(self.meter, mu, float(self.rate.sum()), self.U_MAX) / mu

    def on_send(self, now, s):
        self.own_log.add(now, False)

    def on_drop(self, now):
        self.own_log.add(now, True)

    def choose(self, now):
        pd = self.p_drop
        age = now - self.last_rx
        if age > 2.0 * self.ctx.W:
            pd *= math.exp(-(age - 2.0 * self.ctx.W) / self.ctx.W)
        if pd > 0:
            self.acc += pd
            if self.acc >= 1.0:
                self.acc -= 1.0
                return -1, NAN
        return super().choose(now)


class ExpectedDelayDrop(BeliefRule):
    """The rival that did best against v4 in overload in v4's own report: expected delay on the belief of ours v1,
    and drop the frame when even the lowest expected response time is over the deadline."""
    score = "expected_delay"
    near_ties = False

    def choose(self, now):
        S = self.S
        risk = np.empty(S)
        ed = np.empty(S)
        for s in range(S):
            self._advance(s, now)
            ba = self.agers[s].age(self.b[s], self.d[s] / 2)
            risk[s] = ba @ self.late[s]
            ed[s] = self.d[s] + ba @ self.mean_t[s]
        s = self._argmin_random(ed)
        if ed[s] > self.ctx.D:
            return -1, 1.0
        return s, float(risk[s])


V5_RULE_CLASSES = {
    "ours_v5": SplitDrop, "ours_v5_raw": SplitDropRaw,
    "v4": TeammateV4, "v4_nodrop": TeammateV4NoDrop,
    "wrr_drop": WRRDrop, "wrr_speed_drop": WRRSpeedDrop,
    "expected_delay_drop": ExpectedDelayDrop,
}
