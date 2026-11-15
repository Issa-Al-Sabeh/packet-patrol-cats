"""OURS V6 = ours v5 + three changes. Everything else (speed meter, belief ageing, late(n), backlog cost, drop option,
calibration, smooth round-robin on the shares) is exactly v5.

  A. BALANCE UNLESS THE PLAN CLEARLY WINS (below overload only). At each plan, two candidate splits are compared:
     v5's risk-based plan, and the balanced split (shares = measured site speeds, skipping the sites v5 never uses).
     Both are scored with the same expected late frames (risk corrected by the ingress's own answers once it has
     enough). The plan is used only if it predicts at least GAIN (a fraction) fewer late frames than the balanced
     split; otherwise the balanced split is used. Reason: below capacity, weighted round-robin beat v5 in 11 of 36
     Beirut tests (reports every 30 s: 4.1% vs 5.5%).
  B. REACT TO BURSTS BETWEEN REPORTS.
     B1. The offered-traffic estimate goes UP at once when a site's count is clearly above it (more than RISE_Z
         standard deviations of a Poisson count; smaller rises and all falls are smoothed as in v5).
     B2. Each ingress counts the frames it was offered (sent + dropped) in the last BURST_WIN seconds. If that rate
         differs from the rate the current plan assumes by more than random noise (BURST_Z standard deviations of a
         Poisson count) and by more than BURST_REL, it re-plans at once, with the total traffic scaled by the same
         ratio (the others are assumed to have changed like this ingress: the k idea). At most every BURST_GAP s.
         Reason: v4 beat v5 in the bursts (15.6% vs 20.1%) because v5 only re-plans at the next report.
  C. THE CORRECTED RISK IS USED FOR THE SHARES TOO, not only for the send-or-drop choice (once the ingress has
     CAL_MIN answers). Reason: v5's model predicts about 3.5 times the real risk (calibration factor 0.28), so the
     plan traded risk against backlog with an inflated risk.
Picking the site for a frame is unchanged: smooth weighted round-robin on the shares, the drop slot included.
"""
import math

import numpy as np

from .queueing import fluid, point
from .rules import SplitSpeed, usable_capacity
from .rules_v5 import SplitDrop


class SplitV6(SplitDrop):
    use_balance = True        # change A
    use_burst = True          # change B
    cal_split = True          # change C
    GAIN = 0.25               # A: the plan must predict at least this fraction fewer late frames (set by the pilot)
    BURST_WIN = 2.0           # B2: seconds of own frames counted
    BURST_Z = 4.0             # B2: standard deviations of a Poisson count (checked ~600 times a run, so strict)
    BURST_REL = 0.25          # B2: and at least 25% different
    RISE_Z = 3.0              # B1: a site's count is taken at once only if it is this many sd above the estimate
    BURST_GAP = 0.5           # B2: at most one re-plan per 0.5 s
    CHECK_EVERY = 0.25        # B2: how often the own rate is checked
    MIN_COUNT = 20.0          # B2: only with at least 20 expected own frames in the window (small counts are too noisy)
    # TIE FIX (test of 2 Nov 2026): in overload, a 1% piece whose cost is exactly one miss (a frame the model says is
    # sure to be late, with no harm to others) goes to DROP instead of being sent. Off in ours_v6 (ties go to send).
    tie_drop = False
    no_age = False            # ablation: treat every report as fresh (no staleness awareness)
    allow_drop = True         # ablation: False = never drop (no admission control)
    TIE_TOL = 1e-9            # "exactly one miss": equal up to floating-point noise (relative)
    # hooks added for v6.1 (Nov 2026); at these defaults ours v6 is unchanged
    DROP_FROM = None          # dropping is allowed above this share of the measured capacity (None = U_LIMIT, as v6)
    trace = None              # diagnostics only: called with the cost curves and the greedy result of each plan
                              # (see _after_greedy)

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        self.ref_b = 0            # own frames in the counters' window at the last plan (the plan assumes scale x that)
        self.scale = 1.0
        self.last_check = -1e9
        self.n_plan = self.n_bal = self.n_replan = 0
        self.gains = []           # predicted gain of the plan over the balanced split, at each plan below overload
        # tie-fix diagnostics only (they never change a decision)
        self.t_plans = self.t_plans_drop = 0      # plans; plans in which dropping was allowed (overload)
        self.t_ties = 0           # pieces whose cost was exactly one miss (sent in ours_v6, dropped with the tie fix)
        self.t_near = 0           # pieces sent while dropping was allowed, cost in [0.9, 1) miss (close to a tie)
        self.t_costly = 0         # pieces dropped because the cheapest site cost more than one miss
        self.t_full = 0           # pieces dropped because every site was full (95%)
        self.t_sent_drop = 0      # pieces sent while dropping was allowed
        self.sure = np.zeros(self.S, dtype=bool)  # per site in the current plan: calibrated chance late at plan >= 1
        self.flag = {}            # frames sent to a "sure late" site, waiting for their answer
        self.n_sure = self.n_sure_late = 0

    # ---- B1: offered traffic, up at once, down smoothly
    def on_report_x(self, now, s, q, g, A, X):
        if g <= self.g[s]:
            return
        r = A / self.W / (1.0 - self.own_log.share(g - self.W, g))
        if not self.seen[s]:
            self.rate_off[s] = r
        elif self.use_burst and A > self.rate_off[s] * self.W + self.RISE_Z * math.sqrt(max(self.rate_off[s] * self.W, 1.0)):
            self.rate_off[s] = r                         # a real rise (beyond count noise): take it at once
        else:
            self.rate_off[s] = self.EWMA * r + (1 - self.EWMA) * self.rate_off[s]
        self.own_log.prune(now - 2.0 * self.W - 5.0 - self.BURST_WIN)
        SplitSpeed.on_report_x(self, now, s, q, g, A, X)

    # ---- B2: own offered rate
    def _own_count(self, t0, t1):
        return sum(1 for t, _ in self.own_log.log if t0 < t <= t1)

    def _window_rate(self):
        g = float(np.max(self.g))
        return self._own_count(g - self.W, g) / self.W

    def _changed(self, n, b, scale):
        """Is my rate over the last BURST_WIN s (n frames) really different from the rate the plan assumes
        (scale x b frames in the counters' window of W s)? Both counts are random (Poisson), so the test uses the
        noise of both: z = (r_n - ref) / sqrt(r_max / BURST_WIN + scale^2 x r_b / W)."""
        r_n, r_b = n / self.BURST_WIN, b / self.W
        ref = scale * r_b
        if ref * self.BURST_WIN < self.MIN_COUNT or b < self.MIN_COUNT:
            return False
        var = max(r_n, ref) / self.BURST_WIN + scale * scale * r_b / self.W
        return abs(r_n - ref) > max(self.BURST_Z * math.sqrt(var), self.BURST_REL * ref)

    def _window_count(self):
        g = float(np.max(self.g))
        return self._own_count(g - self.W, g)

    def _scale_now(self, now):
        """Ratio (own rate over the last BURST_WIN s) / (own rate in the counters' window), when the difference is
        more than noise; else 1."""
        if not self.use_burst:
            return 1.0
        n, b = self._own_count(now - self.BURST_WIN, now), self._window_count()
        if self._changed(n, b, 1.0):
            return (max(n, 0.5) / self.BURST_WIN) / (b / self.W)
        return 1.0

    def _after_greedy(self, info):
        """Hook for diagnostics: sees the cost curves and the greedy result of a plan and returns the allocation to
        use. Ours v6 and v6.1 return the greedy result unchanged."""
        if self.trace is not None:
            self.trace(info)
        return info["lam"], info["drop"]

    def _kappa(self, rho):
        """Late frames charged per frame left in a queue above its safe level (rho is already capped at RHO_MAX)."""
        return rho / (1.0 - rho)

    # ---- the plan: v5's, with A, B and C
    def _plan(self, now):
        if not self.seen.all():
            return
        self.scale = self._scale_now(now)
        total = float(self.rate_off.sum()) * self.scale
        if total <= 0:
            return
        self.ref_b = self._window_count()
        S, H, M, mu = self.S, self.W, self.POINTS, self.ctx.mu
        models = [self._model(s) for s in range(S)]
        self.useless = np.array([m[3][0] > self.LATE_SAFE for m in models])
        if self.useless.all():
            self.useless[:] = False
        cap = usable_capacity(self.meter, mu, total, self.U_MAX)
        rho = min(self.RHO_MAX, total / cap.sum())
        kappa = self._kappa(rho)
        ready = self.calibrated and self.n_cal >= self.CAL_MIN
        kc = self.kcal if self.calibrated else 1.0                 # send-or-drop test (as v5)
        ks = self.kcal if (self.cal_split and ready) else 1.0      # C: which site gets the traffic
        kq = self.kcal if ready else 1.0                           # A: plan vs balanced comparison
        drop_from = self.U_LIMIT if self.DROP_FROM is None else self.DROP_FROM
        overload = total > drop_from * float((self.meter.c * mu).sum())
        may_drop = overload and (self.n_cal >= self.CAL_MIN or not self.calibrated) and self.allow_drop
        sel_c, cal_c, cmp_c, risks = [], [], [], []
        for s, (c, lv, ga, late, n_safe) in enumerate(models):
            lam_now = self.p[s] * total
            idx = int(np.argmin(np.abs(lv - lam_now)))
            age = 0.0 if self.no_age else max(0.0, now - self.g[s])
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
            sel_c.append(lv * np.minimum(1.0, ks * r) + back)
            cal_c.append(lv * np.minimum(1.0, kc * r) + back)
            cmp_c.append(lv * np.minimum(1.0, kq * r) + back)
        lam = np.zeros(S)
        drop = 0.0
        step = total / self.CHUNKS
        limit = np.where(self.useless, 0.0, self.U_LIMIT * cap)
        cur_sel, cur_cal = [0.0] * S, [0.0] * S
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
                key = (at(sel_c, s, x) - cur_sel[s], x / cap[s])
                if best_key is None or key < best_key:
                    best, best_key = s, key
            if best >= 0:
                x = lam[best] + step
                v_cal = at(cal_c, best, x)
                dc, lim = v_cal - cur_cal[best], step * self.DROP_COST
                tie = may_drop and abs(dc - lim) <= self.TIE_TOL * max(lim, 1.0)
                self.t_ties += tie
                if self.tie_drop and tie:
                    send = False                                 # the tie fix: a sure miss is dropped
                else:
                    send = not may_drop or v_cal - cur_cal[best] <= step * self.DROP_COST + 1e-12   # as ours_v6
                if send:
                    if may_drop:
                        self.t_sent_drop += 1
                        self.t_near += (not tie) and 0.9 * lim <= dc < lim
                    lam[best] = x
                    cur_sel[best] = at(sel_c, best, x)
                    cur_cal[best] = v_cal
                    continue
                self.t_costly += not tie
            elif not may_drop:
                lam += (total - lam.sum() - drop) * cap / cap.sum()
                break
            else:
                self.t_full += 1
            drop += step
        lam, drop = self._after_greedy(dict(now=now, total=total, step=step, limit=limit, may_drop=may_drop,
                                            kappa=kappa, slope=slope, ks=ks, levels=[m[1] for m in models],
                                            sel_c=sel_c, cal_c=cal_c, risks=risks, lam=lam, drop=drop, cap=cap))
        ok = np.where(self.useless, 0.0, cap)
        # ---- A: balance unless the plan clearly wins (only when there is no overload)
        if self.use_balance and not overload and drop == 0.0:
            bal = total * ok / ok.sum()
            if np.all(bal <= self.U_LIMIT * cap + 1e-9):
                c_plan = sum(at(cmp_c, s, lam[s]) for s in range(S))
                c_bal = sum(at(cmp_c, s, bal[s]) for s in range(S))
                self.gains.append(1.0 - c_plan / c_bal if c_bal > 0 else 0.0)
                if not c_plan < (1.0 - self.GAIN) * c_bal:
                    lam = bal
                    self.n_bal += 1
                else:
                    self.n_plan += 1
        self.p = lam / total
        self.p_drop = drop / total
        self.pi = ok / ok.sum()
        self.plan_risk = np.array([np.interp(lam[s], models[s][1], risks[s]) for s in range(S)])
        kc_d = self.kcal if self.calibrated else 1.0
        self.sure = may_drop & (lam > 0) & (np.minimum(1.0, kc_d * self.plan_risk) >= 1.0 - 1e-12)
        self.t_plans += 1
        self.t_plans_drop += bool(may_drop)
        self.plan_t = now
        pd = round(float(self.p_drop), 4)
        if (self.drop_log[-1][1] if self.drop_log else 0.0) != pd:
            self.drop_log.append([round(float(now), 3), pd])

    def choose(self, now):
        # B2: a burst (or its end) between two reports: re-plan at once
        if (self.use_burst and not self.dirty and self.plan_t > -1e8 and now - self.last_check >= self.CHECK_EVERY):
            self.last_check = now
            if now - self.plan_t >= self.BURST_GAP and self.ref_b > 0:
                n = self._own_count(now - self.BURST_WIN, now)
                if self._changed(n, self.ref_b, self.scale):
                    self._plan(now)
                    self.n_replan += 1
        j, p = super().choose(now)
        if j >= 0 and self.sure[j]:
            self.flag[self.ctx.frame] = True
        return j, p

    def on_reply(self, now, s, delay, frame):
        if self.flag.pop(frame, False):                  # diagnostics: was a "sure late" frame really late?
            self.n_sure += 1
            self.n_sure_late += delay > self.D
        super().on_reply(now, s, delay, frame)

    def diag(self):
        d = super().diag()
        g = np.array(self.gains) if self.gains else np.zeros(1)
        d.update({"plans_risk": self.n_plan, "plans_balanced": self.n_bal, "replans_burst": self.n_replan,
                  "gain_median": round(float(np.median(g)), 4), "gain_p90": round(float(np.percentile(g, 90)), 4)})
        d.update({"tie": {"plans": self.t_plans, "plans_drop": self.t_plans_drop, "ties": int(self.t_ties),
                          "near": int(self.t_near), "costly": int(self.t_costly), "full": int(self.t_full),
                          "sent_drop": int(self.t_sent_drop), "sure_sent": int(self.n_sure),
                          "sure_late": int(self.n_sure_late)}})
        return d


class SplitV6NoBalance(SplitV6):
    """Ours v6 without change A (always the risk-based plan, as v5)."""
    use_balance = False


class SplitV6NoBurst(SplitV6):
    """Ours v6 without change B (re-plans only at reports, offered traffic smoothed both ways, as v5)."""
    use_burst = False


class SplitV6NoCal(SplitV6):
    """Ours v6 without change C (the shares use the model's raw risk, as v5)."""
    cal_split = False


class SplitV6NoAge(SplitV6):
    """Ours v6 without staleness awareness: each report is used as if it described the site now (age 0)."""
    no_age = True


class SplitV6NoDrop(SplitV6):
    """Ours v6 without admission control: the drop option is never available (overload is shared out)."""
    allow_drop = False


class SplitV6TieDrop(SplitV6):
    """Ours v6 with the tie fix: in overload, a piece that costs exactly one miss is dropped instead of sent."""
    tie_drop = True


# pilot only: the candidate thresholds for change A (the pilot picks one; ours_v6 is then frozen with it)
class SplitV6G02(SplitV6):
    GAIN = 0.02


class SplitV6G05(SplitV6):
    GAIN = 0.05


class SplitV6G10(SplitV6):
    GAIN = 0.10


class SplitV6G25(SplitV6):
    GAIN = 0.25


V6_RULE_CLASSES = {"ours_v6": SplitV6, "ours_v6_nobal": SplitV6NoBalance, "ours_v6_noburst": SplitV6NoBurst,
                   "ours_v6_nocal": SplitV6NoCal, "ours_v6_tiedrop": SplitV6TieDrop, "ours_v6_noage": SplitV6NoAge, "ours_v6_nodrop": SplitV6NoDrop, "ours_v6_g02": SplitV6G02, "ours_v6_g05": SplitV6G05,
                   "ours_v6_g10": SplitV6G10, "ours_v6_g25": SplitV6G25}
