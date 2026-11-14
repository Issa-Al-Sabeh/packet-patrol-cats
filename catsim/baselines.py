"""Baselines added for the staleness-aware CATS study (Nov 2026), plus the common rejection wrapper.

Every class documents its source, what it follows exactly, and every adaptation. A rule only uses what its ingress
could know (configured capacities and path delays, the telemetry it received, its own sends, and, for rules that need
it, the answers to its own frames). Only classes with oracle = True may read the true state (engine guard).

  prequal_hcl   Prequal (Wydrowski et al., NSDI 2024): asynchronous probes, probe pool, reuse budget, removal, and the
                hot-cold lexicographic (HCL) rule on requests-in-flight (RIF) and server-side latency.
  liyanage26    Liyanage et al. 2026 (arXiv 2604.21483), Algorithms 1-2: Normal + Cantelli risk, feasibility,
                percentile score, hysteresis.
  dahlin_li     Dahlin (TPDS 2000), Basic Load Interpretation (Eq. 4): water-filling of the expected arrivals of a
                phase into the least-loaded servers, randomized choice.
  cats_lb       CATS flow-level load sharing (draft-fu-cats-flow-lb-03): metric-driven weights, threshold-triggered
                regeneration, optional hysteresis, UCMP-to-ECMP table, hash-based forwarding. The draft gives no
                weight formula or values; ours is documented below.
  oracle_adm    The fresh-state oracle plus fresh-state admission (drop when even the best site's true chance of
                being late is >= TAU). A reference, not a practical rule.
  <rule>+adm    The common rejection wrapper around any rule (see AdmissionWrapper).
  <rule>+adm61  The same wrapper with the offered-traffic estimate of ours v6.1 (the aggregate drop counter; see
                AdmissionWrapper61 and rules_v61.py). The matched-admission rival of ours v6.1.
  <rule>@K=V    Any rule with class parameters overridden (used for tuning on pilot seeds and for frozen values).
"""
import math
from collections import deque

import numpy as np

from .rules import LSQ, NAN, Rule, Oracle, RULE_CLASSES
from .rules_v5 import OwnDrops, _offered
from .rules_v61 import DropEcho


# ====================================================================== Prequal (HCL)
class PrequalHCL(Rule):
    """Prequal (NSDI 2024), asynchronous mode, adapted to CATS sites. Followed exactly (paper section 4):
      * each query triggers probes to replicas sampled uniformly at random without replacement; the current query
        uses probes received earlier (asynchronous);
      * a probe reply carries the replica's requests-in-flight (RIF) and its server-side latency estimate (median
        latency of recently finished queries at a RIF near the current one; computed by the engine at the site);
      * the probe pool holds at most POOL probes; when full, the oldest is dropped; probes older than MAX_AGE are
        removed; a probe is removed after b_reuse uses, b_reuse = max(1, (1 + DELTA) / ((1 - m/n) r_probe - r_remove))
        with random rounding; r_remove probes are removed per query, alternately the oldest and the worst
        (hottest by RIF if any is hot, otherwise the cold one with the highest latency);
      * HCL: a probe is hot if its RIF is above the Q_RIF quantile of recently probed RIFs; if every probe in the pool
        is hot, take the lowest RIF; otherwise the cold probe with the lowest latency;
      * after using a probe, its RIF is incremented locally; fewer than 2 probes in the pool -> fallback.
    Adaptations (CATS sites are few, unequal in size, and far apart; probes cost WAN bytes):
      * probing rate = the telemetry budget (ctx.budget_bps, by default exactly the bytes a report-based rule with the
        counter receives); r_probe per query follows from it (a token bucket), instead of Prequal's fixed r_probe;
      * RIF is divided by the site's configured servers (sites differ in size; Prequal's replicas are alike);
      * the latency used by HCL = server-side estimate + the known round trip to the site (deadline is end to end);
      * pool size m = max(2, n // 2) (the paper's 16 needs many more replicas than our 8; b_reuse needs m < n);
      * r_remove = REMOVE_FRAC x r_probe (the testbed ratio 1 : 3), so the budget formula stays defined when probes
        are scarce;
      * fallback = random in proportion to configured capacity (uniform in the paper; the same when sites are equal).
    Not modelled: sinkholing/error aversion heuristics (omitted by the authors too), idle probing."""
    uses_reports = False
    probes_latency = True
    POOL = 0
    Q_RIF = 0.84
    MAX_AGE = 1.0
    DELTA = 1.0
    REMOVE_FRAC = 1.0 / 3.0
    RIF_HIST = 32
    BUDGET_X = 1.0          # multiple of the budget (supplementary runs only; > 1 = over budget)
    R_PROBE = 0.0           # > 0: Prequal's own fixed probes per query instead of the budget (over budget)

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        S = self.S
        self.m = self.POOL if self.POOL > 0 else max(2, S // 2)
        self.pb = ctx.probe_bytes
        self.rate = ctx.budget_bps * self.BUDGET_X          # bytes per second this ingress may spend on probes
        self.tokens = float(self.pb) if self.R_PROBE <= 0 else 0.0   # one probe at the start
        self.t_last = 0.0
        self.pool = []                                       # [site, rif per server, latency, t received, uses, b]
        self.rif_hist = deque(maxlen=self.RIF_HIST)
        self.p_cap = self.cap / self.cap.sum()
        self.n_q = 0
        self.n_p = 0
        self.r_probe = 0.0                                   # probes per query (running estimate)
        self.rm_acc = 0.0
        self.rm_oldest = True

    def _b_reuse(self):
        rp = max(self.r_probe, 1e-6)
        den = rp * ((1.0 - self.m / self.S) - self.REMOVE_FRAC)
        b = (1.0 + self.DELTA) / den if den > 0 else 1e9
        b = max(1.0, min(b, 1e6))
        lo = math.floor(b)
        return lo + (1 if self.rng.random() < b - lo else 0)

    def on_probe_x(self, now, s, rif, t_meas, lat):
        r = rif / self.c[s]
        self.rif_hist.append(r)
        if len(self.pool) >= self.m:
            self.pool.pop(min(range(len(self.pool)), key=lambda k: self.pool[k][3]))   # oldest out
        self.pool.append([s, r, float(lat), now, 0, self._b_reuse()])

    def _hot_threshold(self):
        if not self.rif_hist:
            return float("inf")
        return float(np.quantile(np.fromiter(self.rif_hist, float), self.Q_RIF))

    def _remove_one(self, thr):
        if not self.pool:
            return
        if self.rm_oldest:
            k = min(range(len(self.pool)), key=lambda j: self.pool[j][3])
        else:
            hot = [j for j, e in enumerate(self.pool) if e[1] > thr]
            if hot:
                k = max(hot, key=lambda j: self.pool[j][1])
            else:
                k = max(range(len(self.pool)), key=lambda j: self.pool[j][2] + self.d[self.pool[j][0]])
        self.rm_oldest = not self.rm_oldest
        self.pool.pop(k)

    def choose(self, now):
        # issue this query's probes (asynchronous: their answers serve later queries)
        if self.R_PROBE > 0:                                  # Prequal's native rate, budget ignored
            self.tokens += self.R_PROBE
            k = int(self.tokens)
            self.tokens -= k
            k = min(k, self.S)
        else:
            self.tokens = min(self.tokens + (now - self.t_last) * self.rate, max(4.0 * self.pb, self.rate))
            k = min(int(self.tokens // self.pb), self.S)
            self.tokens -= k * self.pb
        self.t_last = now
        if k > 0:
            self.probe_bytes += k * self.pb
            self.probe_out.extend(int(x) for x in self.rng.choice(self.S, size=k, replace=False))
        self.n_q += 1
        self.n_p += k
        self.r_probe = self.n_p / self.n_q
        # removals: age, then r_remove per query (alternately oldest and worst)
        self.pool = [e for e in self.pool if now - e[3] <= self.MAX_AGE]
        thr = self._hot_threshold()
        self.rm_acc += self.REMOVE_FRAC * self.r_probe
        while self.rm_acc >= 1.0:
            self.rm_acc -= 1.0
            self._remove_one(thr)
        if len(self.pool) < 2:
            return int(self.rng.choice(self.S, p=self.p_cap)), NAN
        cold = [j for j, e in enumerate(self.pool) if e[1] <= thr]
        if cold:
            j = min(cold, key=lambda q: self.pool[q][2] + self.d[self.pool[q][0]])
        else:
            j = min(range(len(self.pool)), key=lambda q: self.pool[q][1])
        e = self.pool[j]
        s = int(e[0])
        e[4] += 1
        e[1] += 1.0 / self.c[s]                               # local RIF increment
        if e[4] >= e[5]:
            self.pool.pop(j)
        return s, NAN


# ====================================================================== Liyanage et al. 2026
class Liyanage26(Rule):
    """Liyanage et al. 2026, Algorithms 1-2 (paper III-IV). Followed exactly:
      * per server: mean mu_i and sample standard deviation sigma_i of the last WINDOW_N latency observations
        (the available history when fewer exist);
      * p_Norm = 1 - Phi((tau - mu) / sigma); p_Cant = 1 / (1 + ((tau - mu) / sigma)^2) (1 when mu >= tau);
      * feasible set F = {i : p_Norm < EPS and p_Cant < EPS}; challenger j = argmin over F of mu + K sigma;
      * switch only if score_cur - score_j >= DELTA x score_cur for N consecutive decisions; the counter resets when
        the test fails, when j is the current server, or when F is empty (then the client stays);
      * defaults from the paper: EPS = 0.15, K = 1.645, DELTA = 0.05, N = 5; decisions per frame.
    Adaptations:
      * tau = the frame deadline (end to end), and the observed latency = the end-to-end time of the client's own
        frames (the paper measures network latency to each server; in CATS compute queueing dominates);
      * a client = one camera (FRAMES_PER_CLIENT frames/s); an ingress runs several (one client per ingress would
        send a quarter of all traffic to one site); clients start spread in proportion to capacity;
      * a server without observations uses a prior: mean = round trip + one service time, sd = service-time sd; with
        one observation, the sd is the prior's (the sample sd needs two);
      * WINDOW_N is not given in the paper (tuned on pilot seeds);
      * the paper observes the latency of every server at each step. Here a client observes its own frames
        (passive) and, if PROBE, the ingress also spends the telemetry budget (the same bytes as Prequal) on probes to
        random sites; a probe answer (server-side latency estimate + round trip) is one observation of that site for
        every client of the ingress. PROBE=False = passive only (a pilot candidate)."""
    uses_reports = False
    needs_replies = True
    predicts = True
    probes_latency = True
    WINDOW_N = 20
    EPS, K, DELTA, N_PERSIST = 0.15, 1.645, 0.05, 5
    FRAMES_PER_CLIENT = 10.0
    PROBE = True

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        m = 1.0 / ctx.mu
        self.tau = ctx.D
        self.prior_mean = self.d + m
        self.prior_sd = m * math.sqrt(ctx.scv)
        nc = max(1, int(round(ctx.ingress_rate[i] / self.FRAMES_PER_CLIENT)))
        self.nc = nc
        S = self.S
        self.win = [[deque() for _ in range(S)] for _ in range(nc)]
        self.sum = np.zeros((nc, S))
        self.sq = np.zeros((nc, S))
        p = self.cap / self.cap.sum()
        self.cur = [int(x) for x in self.rng.choice(S, size=nc, p=p)]
        self.cnt = [0] * nc
        self.pb = ctx.probe_bytes
        self.rate = ctx.budget_bps if self.PROBE else 0.0
        self.tokens = float(self.pb) if self.PROBE else 0.0
        self.t_last = 0.0

    def _observe(self, k, s, delay):
        dq = self.win[k][s]
        dq.append(delay)
        self.sum[k, s] += delay
        self.sq[k, s] += delay * delay
        if len(dq) > self.WINDOW_N:
            x = dq.popleft()
            self.sum[k, s] -= x
            self.sq[k, s] -= x * x

    def on_reply(self, now, s, delay, frame):
        self._observe(frame % self.nc, s, delay)

    def on_probe_x(self, now, s, rif, t_meas, lat):
        for k in range(self.nc):                          # one observation of site s for every client
            self._observe(k, s, float(lat) + self.d[s])

    def _summary(self, k):
        n = np.array([len(self.win[k][s]) for s in range(self.S)], float)
        mean = np.where(n > 0, self.sum[k] / np.maximum(n, 1), self.prior_mean)
        var = np.where(n > 1, (self.sq[k] - n * mean * mean) / np.maximum(n - 1, 1), self.prior_sd ** 2)
        return mean, np.sqrt(np.maximum(var, 1e-8))

    def choose(self, now):
        if self.PROBE:                                    # spend the budget on probes to random sites
            self.tokens = min(self.tokens + (now - self.t_last) * self.rate, max(4.0 * self.pb, self.rate))
            n = min(int(self.tokens // self.pb), self.S)
            if n > 0:
                self.tokens -= n * self.pb
                self.probe_bytes += n * self.pb
                self.probe_out.extend(int(x) for x in self.rng.choice(self.S, size=n, replace=False))
        self.t_last = now
        k = self.ctx.frame % self.nc
        mean, sd = self._summary(k)
        z = (self.tau - mean) / sd
        p_norm = 0.5 * np.array([math.erfc(v / math.sqrt(2.0)) for v in z])
        p_cant = np.where(z > 0, 1.0 / (1.0 + z * z), 1.0)
        score = mean + self.K * sd
        feas = np.flatnonzero((p_norm < self.EPS) & (p_cant < self.EPS))
        cur = self.cur[k]
        if len(feas) == 0:
            self.cnt[k] = 0
        else:
            j = int(feas[np.argmin(score[feas])])
            if j == cur:
                self.cnt[k] = 0
            elif score[cur] - score[j] >= self.DELTA * score[cur]:
                self.cnt[k] += 1
                if self.cnt[k] >= self.N_PERSIST:
                    self.cur[k], self.cnt[k] = j, 0
            else:
                self.cnt[k] = 0
        s = self.cur[k]
        return s, float(p_norm[s])


# ====================================================================== Dahlin, Basic Load Interpretation
def dahlin_fill(load, c, arrivals):
    """Dahlin's Basic LI (Eq. 4), with servers of unequal size: the expected arrivals of a phase fill the
    least-loaded servers (load per server L_i / c_i) up to a common level; p_i = c_i (level - L_i / c_i) / arrivals.
    With equal servers this is exactly Eq. 4 (and Eq. 2 when every server can be reached)."""
    load = np.asarray(load, float)
    c = np.asarray(c, float)
    if arrivals <= 0:
        return c / c.sum()
    x = load / c
    order = np.argsort(x, kind="stable")
    cum_c = cum_cx = 0.0
    level = None
    for rank, j in enumerate(order):
        cum_c += c[j]
        cum_cx += c[j] * x[j]
        lv = (arrivals + cum_cx) / cum_c
        nxt = x[order[rank + 1]] if rank + 1 < len(order) else math.inf
        if lv <= nxt:
            level = lv
            break
    p = c * np.maximum(0.0, level - x)
    return p / p.sum()


class DahlinLI(Rule):
    """Dahlin, "Interpreting Stale Load Information" (IEEE TPDS 2000), Basic LI (section 4, Eq. 4). Followed:
      * a client keeps each server's last reported load L_i and computes, for the current phase, how the expected
        arrivals from all clients (lambda x T) would fill the least-loaded servers up to a common level;
      * each request goes to server i with probability proportional to that fill (randomized, so clients that read
        the same report do not herd); departures are ignored, as in the paper (equal departure rate per server).
    Adaptations:
      * servers of unequal size: loads per server L_i / c_i and fill weighted by c_i (dahlin_fill); with equal
        servers this is Eq. 4 exactly; "equal departure rate per server" becomes "per GPU";
      * lambda = total arrival rate from the 4-byte arrivals counter in the reports (smoothed); the paper assumes it is
        known or estimated;
      * T = the phase length W (periodic model), plus, if PHASE_AGE, the mean age of a report when it arrives
        (reports arrive late; the paper's continuous model uses the information's age as T)."""
    uses_counter = True
    PHASE_AGE = True
    EWMA = 0.3

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        S = self.S
        self.L = np.zeros(S)
        self.g = np.full(S, -1e9)
        self.rate = np.zeros(S)
        self.seen = np.zeros(S, dtype=bool)
        self.age_rx = 0.0
        self.n_rx = 0
        self.p = self.cap / self.cap.sum()
        self.dirty = False

    def on_report(self, now, s, q, g, A):
        if g <= self.g[s]:
            return
        self.g[s] = g
        self.L[s] = q
        r = A / self.ctx.W
        self.rate[s] = r if not self.seen[s] else self.EWMA * r + (1 - self.EWMA) * self.rate[s]
        self.seen[s] = True
        a = max(0.0, now - g)
        self.n_rx += 1
        self.age_rx += (a - self.age_rx) / min(self.n_rx, 50)
        self.dirty = True

    def choose(self, now):
        if self.dirty:
            self.dirty = False
            if self.seen.all():
                T = self.ctx.W + (self.age_rx if self.PHASE_AGE else 0.0)
                self.p = dahlin_fill(self.L, self.c, float(self.rate.sum()) * T)
        return int(self.rng.choice(self.S, p=self.p)), NAN


# ====================================================================== CATS draft load sharing
def expand_table(weights, size):
    """UCMP-to-ECMP expansion: integer entries per alternative, in proportion to the weights (largest remainder)."""
    w = np.asarray(weights, float)
    if w.sum() <= 0:
        w = np.ones_like(w)
    raw = w / w.sum() * size
    n = np.floor(raw).astype(int)
    rest = size - n.sum()
    if rest > 0:
        order = np.argsort(-(raw - n), kind="stable")
        n[order[:rest]] += 1
    return np.repeat(np.arange(len(w)), n)


class CatsLB(Rule):
    """CATS flow-level load sharing (draft-fu-cats-flow-lb-03, section 6-7), our instantiation. From the draft:
      * the Path Selector keeps, per service, the Forwarding Alternatives that satisfy the SLA, each with a load
        sharing weight computed from service-instance metrics and path characteristics;
      * it regenerates the table only when metric changes cross a predefined threshold, optionally with hysteresis;
      * the table is expanded UCMP-to-ECMP into entries in proportion to the weights; the forwarder hashes the flow id
        onto an entry. Each frame is its own request/flow here (affinity then has no effect).
    Not specified in the draft, so chosen here (documented): metric = reported frames per server q_s / c_s (CATS
    reports); SLA filter = round trip + one service time + the visible wait max(0, q_s - c_s + 1) / (c_s mu) <=
    deadline (all sites if none qualifies); weight = c_s / (1 + q_s / c_s); threshold THETA on any site's metric
    change since the last regeneration; hysteresis = at least HOLD seconds between regenerations and a new table only
    if the weights moved by at least HYST (L1); optional smoothing toward the new weights (SMOOTH < 1); TABLE entries;
    hash = Knuth multiplicative hash of the frame id."""
    TABLE = 100
    THETA = 0.25
    HOLD = 0.0
    HYST = 0.0
    SLA_QUEUE = True          # SLA estimate includes the reported wait (False: round trip + service only)
    SMOOTH = 1.0              # 1 = take the new weights; < 1 = move only this far toward them (anti-oscillation)

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        S = self.S
        self.q = np.zeros(S)
        self.g = np.full(S, -1e9)
        self.m0 = None
        self.t_regen = -1e9
        self.w = self.c.astype(float) / self.c.sum()
        self.table = expand_table(self.w, self.TABLE)
        self.dirty = False
        self.n_regen = 0

    def on_report(self, now, s, q, g, A):
        if g > self.g[s]:
            self.q[s], self.g[s] = q, g
            self.dirty = True

    def _regen(self, now):
        mu = self.ctx.mu
        m = self.q / self.c
        if self.m0 is not None:
            if now - self.t_regen < self.HOLD or np.max(np.abs(m - self.m0)) < self.THETA:
                return
        est = self.d + 1.0 / mu + (np.maximum(0.0, self.q - self.c + 1) / (self.c * mu) if self.SLA_QUEUE else 0.0)
        ok = est <= self.ctx.D
        if not ok.any():
            ok[:] = True
        w = np.where(ok, self.c / (1.0 + m), 0.0)
        w = w / w.sum()
        if self.SMOOTH < 1.0:
            w = self.SMOOTH * w + (1.0 - self.SMOOTH) * self.w
        self.m0 = m.copy()
        self.t_regen = now
        if np.abs(w - self.w).sum() < self.HYST:
            return
        self.w = w
        self.table = expand_table(w, self.TABLE)
        self.n_regen += 1

    def choose(self, now):
        if self.dirty and (self.g > -1e8).all():
            self.dirty = False
            self._regen(now)
        h = (self.ctx.frame * 2654435761) & 0xFFFFFFFF
        return int(self.table[h % len(self.table)]), NAN

    def diag(self):
        return {"regenerations": self.n_regen}


# ====================================================================== oracle with fresh-state admission
class OracleAdm(Oracle):
    """The fresh-state oracle (true queues, servers, speeds; lowest true chance of being late) that also drops a frame
    when even that lowest chance is >= TAU (tuned on pilot seeds). A reference only."""
    oracle = True
    TAU = 0.8

    def choose(self, now):
        s, r = super().choose(now)
        if r >= self.TAU:
            return -1, r
        return s, r


# ====================================================================== F2: LSQ-Sample (supplementary)
class LSQSample(LSQ):
    """LSQ-Sample (Vargaftik, Keslassy, Orda, IEEE/ACM ToN 2020, Sec. V-A), at the telemetry budget. Supplementary.

    Same local view as `lsq` (last sampled value + this ingress's own frames sent since, no ageing; shortest local
    queue per server; ties to the larger site), but the view is refreshed the way the paper does it: each dispatcher
    samples queues uniformly at random, independently of the other dispatchers, instead of all ingresses receiving
    the same periodic report at the same moment.
    Adaptations: the paper samples d = 2 queues at every arrival; here the number of samples follows the byte budget
    (a token bucket, as for Prequal: ctx.budget_bps / probe bytes per second, about 2 per second at the medium budget,
    i.e. far fewer than 2 per arrival). A sample is a probe: it reaches the site after the one-way delay, and its
    answer (frames in the system, time measured) serves later frames (asynchronous), so it is also stale."""
    uses_reports = False

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        self.pb = ctx.probe_bytes
        self.rate = ctx.budget_bps
        self.tokens = float(self.pb)                          # one sample at the start
        self.t_last = 0.0

    def on_probe(self, now, s, q, t_meas):
        self.on_report(now, s, q, t_meas, 0)                  # replaces the local entry, drops own frames it covers

    def choose(self, now):
        self.tokens = min(self.tokens + (now - self.t_last) * self.rate, max(4.0 * self.pb, self.rate))
        self.t_last = now
        k = min(int(self.tokens // self.pb), self.S)
        if k > 0:
            self.tokens -= k * self.pb
            self.probe_bytes += k * self.pb
            self.probe_out.extend(int(x) for x in self.rng.choice(self.S, size=k, replace=False))
        return super().choose(now)


# ====================================================================== common rejection wrapper
class AdmissionWrapper(Rule):
    """The common rejection wrapper (fair admission control): the same admission rule in front of any routing rule.
    It drops just enough frames to keep the traffic it lets through at U = 95% of the configured total capacity,
    spreading the drops evenly (a deterministic credit), and lets the inner rule route every admitted frame exactly as
    it would on its own. Offered traffic = the arrivals counters in the reports / (1 - this ingress's drop share), as
    in ours v5 and round-robin + drop. It needs the reports with the counter: for an inner rule that does not use
    reports, those bytes are added (and reported). The inner rule never sees dropped frames."""
    U = 0.95
    EWMA = 0.3
    inner_cls = None

    def __init__(self, ctx, i):                               # no Rule.__init__: probe_out/probe_bytes are the inner's
        self.ctx, self.i = ctx, i
        self.S = ctx.S
        self.d = ctx.d_known[i]
        self.rng = ctx.rngs[i]
        self.c = ctx.c
        self.cap = ctx.c * ctx.mu
        self.inner = self.inner_cls(ctx, i)
        S = self.S
        self.own_log = OwnDrops()
        self.rate_off = np.zeros(S)
        self.seen = np.zeros(S, dtype=bool)
        self.last_g = np.full(S, -1e9)
        self.last_rx = -1e9
        self.acc = 0.0
        self.p_drop = 0.0

    @property
    def probe_out(self):
        return self.inner.probe_out

    @property
    def probe_bytes(self):
        return self.inner.probe_bytes

    def on_report_x(self, now, s, q, g, A, X):
        if g > self.last_g[s]:
            self.last_g[s] = g
            _offered(self.own_log, self.rate_off, self.seen, s, A, g, self.ctx.W, self.EWMA)
            self.seen[s] = True
            self.own_log.prune(now - 2.0 * self.ctx.W - 5.0)
            self.last_rx = now
            total = float(self.rate_off.sum()) if self.seen.all() else 0.0
            room = self.U * float(self.cap.sum())
            self.p_drop = 1.0 - room / total if total > room else 0.0
        if self.inner_cls.uses_reports:
            self.inner.on_report_x(now, s, q, g, A, X)

    def on_send(self, now, s):
        self.own_log.add(now, False)
        self.inner.on_send(now, s)

    def on_drop(self, now):
        self.own_log.add(now, True)

    def on_reply(self, now, s, delay, frame):
        self.inner.on_reply(now, s, delay, frame)

    def on_probe(self, now, s, q, t_meas):
        self.inner.on_probe(now, s, q, t_meas)

    def on_probe_x(self, now, s, q, t_meas, lat):
        self.inner.on_probe_x(now, s, q, t_meas, lat)

    def choose(self, now):
        pd = self.p_drop
        age = now - self.last_rx
        if age > 2.0 * self.ctx.W:                            # reports stopped: stop dropping, gradually
            pd *= math.exp(-(age - 2.0 * self.ctx.W) / self.ctx.W)
        if pd > 0:
            self.acc += pd
            if self.acc >= 1.0:
                self.acc -= 1.0
                return -1, NAN
        return self.inner.choose(now)

    def diag(self):
        return self.inner.diag() if hasattr(self.inner, "diag") else {}


class AdmissionWrapper61(AdmissionWrapper):
    """The common rejection wrapper with the offered-traffic estimate of ours v6.1: the same admission rule (keep the
    admitted traffic at U = 95% of the configured capacity, drops spread evenly), but the offered traffic comes from
    the aggregate drop counter instead of this ingress's own drop share:
        offered at site s = (A_s / W) / (1 - p),    p = all drops / (all arrivals + all drops)   (rules_v61.py).
    p is one number per round of reports, so the estimate is updated SETTLE seconds after the last report of a round
    arrived (as ours v6.1 does at its plan). The wrapper sends its own drop counts like ours v6.1 (same ECHO_FRAC), and
    those bytes are counted. Smoothing: the EWMA of the wrapper (no clear-rise rule, as before)."""
    uses_drop_echo = True
    SETTLE = 0.05
    ECHO_FRAC = 0.25

    def __init__(self, ctx, i):
        super().__init__(ctx, i)
        S = self.S
        self.A_last = np.zeros(S)
        self.E_last = np.zeros(S)
        self.fresh = np.zeros(S, dtype=bool)
        self.dirty = False
        self.echo = DropEcho(self.ECHO_FRAC * ctx.W)
        self.echo_out = 0

    def on_report_x(self, now, s, q, g, A, X):
        self.on_report_e(now, s, q, g, A, X, 0)

    def on_report_e(self, now, s, q, g, A, X, E):
        if g > self.last_g[s]:
            self.last_g[s] = g
            self.A_last[s], self.E_last[s], self.fresh[s] = A, E, True
            self.own_log.prune(now - 2.0 * self.ctx.W - 5.0)
            self.dirty, self.last_rx = True, now
        if self.inner_cls.uses_reports:
            self.inner.on_report_x(now, s, q, g, A, X)

    def _update(self):
        W = self.ctx.W
        A_tot, E_tot = float(self.A_last.sum()), float(self.E_last.sum())
        p = min(E_tot / (A_tot + E_tot), OwnDrops.MAX) if A_tot + E_tot > 0 else 0.0
        for s in np.flatnonzero(self.fresh):
            r = self.A_last[s] / W / (1.0 - p)
            self.rate_off[s] = r if not self.seen[s] else self.EWMA * r + (1 - self.EWMA) * self.rate_off[s]
            self.seen[s] = True
        self.fresh[:] = False
        total = float(self.rate_off.sum()) if self.seen.all() else 0.0
        room = self.U * float(self.cap.sum())
        self.p_drop = 1.0 - room / total if total > room else 0.0

    def choose(self, now):
        if self.dirty and now >= self.last_rx + self.SETTLE:
            self._update()
            self.dirty = False
        return super().choose(now)

    def on_send(self, now, s):
        super().on_send(now, s)
        self.echo_out = self.echo.take(now)

    def on_drop(self, now):
        super().on_drop(now)
        self.echo.dropped()


_CACHE = {}


def make_admission(inner_cls, name, wrapper=AdmissionWrapper):
    attrs = {"inner_cls": inner_cls, "uses_reports": True, "uses_counter": True,
             "needs_replies": inner_cls.needs_replies, "predicts": inner_cls.predicts,
             "probes_latency": getattr(inner_cls, "probes_latency", False),
             "oracle": getattr(inner_cls, "oracle", False)}
    tag = "Adm" if wrapper is AdmissionWrapper else "Adm61"
    return type(f"{tag}[{name}]", (wrapper,), attrs)


def _parse(v):
    for f in (int, float):
        try:
            return f(v)
        except ValueError:
            pass
    if v in ("True", "False"):
        return v == "True"
    return v


def resolve_rule(name):
    """'rule', 'rule@K=V,K2=V2' (class parameters overridden), and either followed by '+adm' (common wrapper) or
    '+adm61' (the common wrapper with the v6.1 estimate)."""
    if name in _CACHE:
        return _CACHE[name]
    if name.endswith("+adm61"):
        base = resolve_rule(name[:-6])
        cls = make_admission(base, name[:-6], AdmissionWrapper61)
    elif name.endswith("+adm"):
        base = resolve_rule(name[:-4])
        cls = make_admission(base, name[:-4])
    elif "@" in name:
        base_name, params = name.split("@", 1)
        base = resolve_rule(base_name)
        attrs = {}
        for kv in params.split(","):
            k, v = kv.split("=", 1)
            if not hasattr(base, k):
                raise KeyError(f"{base_name} has no parameter {k}")
            attrs[k] = _parse(v)
        cls = type(f"{base.__name__}@{params}", (base,), attrs)
    else:
        cls = RULE_CLASSES[name]
    _CACHE[name] = cls
    return cls


BASELINE_CLASSES = {"lsq_sample": LSQSample, "prequal_hcl": PrequalHCL, "liyanage26": Liyanage26, "dahlin_li": DahlinLI,
                    "cats_lb": CatsLB, "oracle_adm": OracleAdm}
RULE_CLASSES.update(BASELINE_CLASSES)
