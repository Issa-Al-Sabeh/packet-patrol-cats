"""Ours v6.2 candidates (Batch C): v6.1 with ONE change, in how the offered-traffic estimate comes DOWN.

Why (feedback/batchC/diagnosis.md): after a burst ends, v6.1's estimate of the offered traffic stays too high for
about 30 s (1.39 x the truth at first, pilot seed 101), so it keeps dropping frames it no longer needs to drop. The
estimate goes up at once on a clear rise, but it comes down only by smoothing: each report moves it 30% of the way.

The candidates change only that, through two parameters of the estimate (nothing else in v6.1 changes):
  OFF_W   weight of the newest round in the estimate when there is no clear rise (v6.1: 0.3, its EWMA).
          It is used for the estimate only; the other uses of EWMA in the inherited code are untouched.
  FALL_Z  None in v6.1. A number z: a CLEAR FALL (arrivals below the arrivals the estimate implies by more than
          z standard deviations of a Poisson count) is taken at once, as a clear rise already is. The mirror of
          v6.1's rise test, with the same z (RISE_Z = 3).

At OFF_W = 0.3 and FALL_Z = None, SplitV62 is exactly ours v6.1 (checked in tests/test_v62.py).
Which candidate becomes v6.2 is decided on pilot seeds by the rule written in feedback/batchC/design.py.
"""
import math

from . import rules as _rules  # noqa: F401  (load rules first: it imports rules_v61 at its end)
from .rules_v61 import SplitV61


class SplitV62(SplitV61):
    OFF_W = 0.3               # v6.1's smoothing of the estimate (its EWMA)
    FALL_Z = None             # v6.1: no fall test

    def _absorb(self, s, A, p):
        W = self.W
        r = A / W / (1.0 - p)
        if not self.seen_off[s]:
            self.rate_off[s] = r
            self.seen_off[s] = True
            return
        e = self.rate_off[s] * W * (1.0 - p)                      # arrivals the current estimate implies
        sd = math.sqrt(max(e, 1.0))
        if self.like_rise:
            rise = A > e + self.RISE_Z * sd
        else:
            rise = A > self.rate_off[s] * W + self.RISE_Z * math.sqrt(max(self.rate_off[s] * W, 1.0))
        fall = self.FALL_Z is not None and A < e - self.FALL_Z * sd
        if self.use_burst and (rise or fall):
            self.rate_off[s] = r                                  # a real change (beyond count noise): at once
        else:
            self.rate_off[s] = self.OFF_W * r + (1 - self.OFF_W) * self.rate_off[s]


class SplitV62Fall(SplitV62):
    FALL_Z = 3.0


class SplitV62W06(SplitV62):
    OFF_W = 0.6


class SplitV62W10(SplitV62):
    OFF_W = 1.0


V62_CANDIDATES = {"v62c_same": SplitV62, "v62c_fall": SplitV62Fall, "v62c_w06": SplitV62W06,
                  "v62c_w10": SplitV62W10}

# Chosen on pilot seeds by feedback/batchC/design.py (rules A-E; feedback/batchC/choice.json): the clear-fall test.
# Frozen as ours v6.2 (FREEZE_v6.2.md).
V62_RULE_CLASSES = {"ours_v62": SplitV62Fall}


def register():
    from .rules import RULE_CLASSES
    RULE_CLASSES.update(V62_CANDIDATES)
    RULE_CLASSES.update(V62_RULE_CLASSES)


register()
