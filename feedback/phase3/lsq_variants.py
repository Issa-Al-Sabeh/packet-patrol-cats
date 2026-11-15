"""Phase 3 diagnostics of the LSQ baseline (NOT rules of the study; nothing here is used by any result table).

Question (feedback of 11 Nov 2026): our "LSQ" falls from 93.9% to 49.0% deadline success when reports go from every
10 s to every 0.5 s. Is that LSQ, or our adaptation of it (every ingress receives the same report at the same moment
and takes the minimum deterministically)?

Variants, each changing ONE thing of `lsq`:
  lsq_randtie       ties between sites are broken at random (lsq: the larger site)
  lsq_poll_sync     CONTROL: the view is refreshed by polls instead of reports, every W seconds, every ingress at the
                    same moment. Same information, same age as the reports. Must behave like `lsq`.
  lsq_poll_phase    the same polls, but every ingress at its own random moment within the interval
  lsq_poll_site     the same polls, every (ingress, site) pair at its own random moment
  wrr_phase         capacity round-robin started at a random point of its cycle at each ingress (wrr: all the same)
A poll is a probe (the site answers with its frames in the system). To give it exactly the age of a report, the answer
is used HOLD seconds after it arrives (HOLD = the report delay of the scenario, 50 ms). Polls cost more bytes than
reports (124 against 62 per site), so these are mechanism checks, not budget-matched rules.
"""
import numpy as np

from catsim.rules import LSQ, NAN, RULE_CLASSES, WRR


class LSQRandTie(LSQ):
    def choose(self, now):
        qh = (self.q + np.array([len(x) for x in self.log])) / self.c
        best = np.flatnonzero(qh <= qh.min() + 1e-12)
        return int(best[0]) if len(best) == 1 else int(self.rng.choice(best)), NAN


class LSQPoll(LSQ):
    uses_reports = False
    PHASE = "sync"            # sync | ingress | site
    HOLD = 0.05

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        W = ctx.W
        if self.PHASE == "sync":
            self.next = np.full(self.S, W)                        # every ingress polls at W, 2W, ... like the reports
        elif self.PHASE == "ingress":
            self.next = np.full(self.S, self.rng.uniform(0.0, W))
        else:
            self.next = self.rng.uniform(0.0, W, size=self.S)
        self.W = W
        self.held = []                                            # answers waiting HOLD seconds: (use at, s, q, t_meas)

    def on_probe(self, now, s, q, t_meas):
        self.held.append((now + self.HOLD, s, q, t_meas))

    def choose(self, now):
        while self.held and self.held[0][0] <= now:
            _, s, q, t_meas = self.held.pop(0)
            self.on_report(now, s, q, t_meas, 0)
        due = np.flatnonzero(self.next <= now)
        if len(due):
            self.probe_out.extend(int(s) for s in due)
            self.probe_bytes += len(due) * self.ctx.probe_bytes
            self.next[due] += self.W * np.ceil((now - self.next[due]) / self.W + 1e-12)
        return super().choose(now)


class WRRPhase(WRR):
    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        for _ in range(int(self.rng.integers(0, int(self.c.sum())))):   # start somewhere in the cycle
            self.cur += self.c
            self.cur[int(np.argmax(self.cur))] -= self.c.sum()


RULE_CLASSES.update({
    "lsq_randtie": LSQRandTie,
    "lsq_poll_sync": type("LSQPollSync", (LSQPoll,), {"PHASE": "sync"}),
    "lsq_poll_phase": type("LSQPollPhase", (LSQPoll,), {"PHASE": "ingress"}),
    "lsq_poll_site": type("LSQPollSite", (LSQPoll,), {"PHASE": "site"}),
    "wrr_phase": WRRPhase,
})
