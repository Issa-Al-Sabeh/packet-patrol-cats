"""One simulation run: one scenario, one rule, one seed.

What happens:
  * Each ingress receives camera frames (Poisson arrivals); each frame is one inference job.
  * For every frame the ingress's rule picks a site. The frame travels (half the round trip,
    plus jitter), waits in the site's queue (first come, first served), is processed by one GPU
    server, and the answer travels back. It is LATE if the whole time exceeds the deadline.
  * Every W seconds each site measures how many frames it holds (q) and how many arrived in the
    last window (A), and sends that report to every ingress (it may be lost or delayed).
  * Stress tests can switch the load, or the number of working servers at one site, halfway. Real-life and
    held-out scenarios add other unannounced events (servers lost and back, slower GPUs, a surge, congestion).
  * v5 study: a rule may DROP a frame at the ingress (site -1): it is never sent and counts as a miss. In the
    overload tests the sites are deadline-aware (site_discard): a frame whose turn comes after its deadline is
    discarded instead of served (it counts as a miss; rules that read answers get a reject back). The 4-byte
    counter then carries two 2-byte counts, arrivals A and discards X (X is always 0 without site_discard).
    With no drops and no discards, a run is exactly the same as before (same events, same numbers).
The frames, job sizes, path delays, jitter and report losses depend only on the seed, so every rule
sees exactly the same world (a paired comparison).

Staleness study (Nov 2026), all off by default (a run with the defaults is event-for-event the same as before):
  * delay_matrix_ms: an explicit round trip for every (ingress, site) pair;
  * report_delay_s: every report spends this much longer in transit (telemetry delay);
  * report_noise_sd: the queue a site reports = true + Normal(0, sd), rounded, at least 0 (one draw per report
    round, the same value to every ingress); drawn from its own random stream;
  * report_mode = "threshold": sampled send-on-delta. Every W the site measures as usual (the arrivals counter still
    covers exactly the last W), but it sends the report only if its queue moved by at least report_threshold x its
    configured servers since the last report it sent, or if report_heartbeat seconds have passed. Skipped reports
    cost no bytes; to the rules a skipped report looks like a lost one. The random numbers for losses and delays are
    drawn for every round whether or not it is sent, so all rules keep exactly the same randomness;
  * share_profile: the share of the traffic each ingress receives changes at given times (shifting traffic);
  * probes of latency-aware probing rules (Prequal HCL) get back the site's requests-in-flight and a server-side
    latency estimate (median time at the site of frames finished in the last 2 s that found a similar number in
    flight). Older probing rules get the queue only, exactly as before.
v6.1 (Nov 2026), off for every rule except those with uses_drop_echo (a run of any other rule is event-for-event the
same as before):
  * aggregate drop counter. Such a rule may put a count of the frames it dropped on a frame it is sending anyway
    (rule.echo_out, echo_bytes each time). Each site adds up the counts that arrive in a report window and reports the
    sum E (echo_bytes more per report); the rule receives it through on_report_e. The bytes of both are counted in
    bytes_per_s. A count is lost with the report that carries it, like every other field of that report.
Event order: the event heap is ordered by (time, insertion number); at equal times heap events (reports, completions,
probes, capacity changes) are handled before a new frame that arrives at that same moment, and heap events with
equal times are handled in the order they were scheduled.
Every run checks request conservation: each counted frame ends exactly once as success, late, expired (discarded
by a deadline-aware site) or rejected (dropped at the ingress).
"""
import heapq
import math
import time
from collections import deque
from types import SimpleNamespace

import numpy as np

from .config import Scenario
from .queueing import GridAger, N_STATES, late_table, mean_time_table, sample_jobs
from .rules import RULE_CLASSES  # noqa: F401  (kept for older scripts that import it from here)
from .baselines import resolve_rule

TRUE_STATE = ("nsys", "c_now", "speed_now", "late_true")   # what only an oracle may read


class _Tripwire:
    """Stands in for the true state in the context of a non-oracle rule when guard=True (tests)."""

    def __init__(self, name):
        self._name = name

    def _boom(self, *a, **k):
        raise RuntimeError(f"a non-oracle rule read the true state ({self._name})")

    __getitem__ = __iter__ = __len__ = __call__ = __array__ = _boom

ARR_SITE, DONE, REPORT_GEN, REPORT_RCV, REPLY, PROBE_AT, PROBE_BACK, CAP_CHANGE, SPEED_CHANGE = range(9)
CALIB_EDGES = np.array([0, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0001])


def _arrivals(rng, rate1, rate2, t_switch, T):
    """Poisson arrival times on [0, T): rate1 before t_switch, rate2 after."""
    a = rng.uniform(0, t_switch, rng.poisson(rate1 * t_switch))
    b = rng.uniform(t_switch, T, rng.poisson(rate2 * (T - t_switch))) if T > t_switch else np.empty(0)
    return np.sort(np.concatenate([a, b]))


def _arrivals_profile(rng, cap_share, profile, T):
    """Poisson arrival times on [0, T) whose rate follows a load profile ((time, load), ...), by thinning."""
    ts = np.array([p[0] for p in profile], float)
    ls = np.array([p[1] for p in profile], float)
    top = ls.max() * cap_share
    cand = np.sort(rng.uniform(0, T, rng.poisson(top * T)))
    keep = rng.random(len(cand)) < np.interp(cand, ts, ls) * cap_share / top
    return cand[keep]


def _arrivals_shares(rng, sc, cap, shares_avg, T, R):
    """Poisson arrivals per ingress whose rate = load(t) x capacity x share_i(t), by thinning (shifting traffic).
    load(t) follows load_profile if given, else the constant load; share_i(t) is piecewise constant."""
    prof_t = np.array([p[0] for p in sc.share_profile], float)
    prof_s = np.array([p[1] for p in sc.share_profile], float)        # phases x ingresses
    if prof_s.shape[1] != R:
        raise ValueError("share_profile needs one share per ingress")
    prof_s = prof_s / prof_s.sum(axis=1, keepdims=True)
    if sc.load_profile:
        lt = np.array([p[0] for p in sc.load_profile], float)
        lv = np.array([p[1] for p in sc.load_profile], float)
        top_load = float(lv.max())
    else:
        top_load = float(sc.load)
    times, owner = [], []
    for i in range(R):
        top = top_load * cap * float(prof_s[:, i].max())
        cand = np.sort(rng.uniform(0, T, rng.poisson(top * T)))
        k = np.clip(np.searchsorted(prof_t, cand, side="right") - 1, 0, len(prof_t) - 1)
        load_t = np.interp(cand, lt, lv) if sc.load_profile else np.full(len(cand), float(sc.load))
        rate = load_t * cap * prof_s[k, i]
        keep = rng.random(len(cand)) < rate / top if top > 0 else np.zeros(len(cand), bool)
        times.append(cand[keep])
        owner.append(np.full(int(keep.sum()), i))
    return times, owner


def run(sc: Scenario, rule: str, seed: int, keep_series=False, guard=False, hook=None):
    """One run. guard=True (tests): non-oracle rules get a context whose true state raises on any access.
    hook (tests): called at the end with the per-frame records and the rule objects."""
    t_wall = time.time()
    S, R = len(sc.servers), sc.ingresses
    c = np.array(sc.servers, dtype=int)                                   # servers that really work
    c_known = np.array(sc.servers_known, dtype=int) if sc.servers_known else c   # what the rules are told
    mu, m = sc.mu, 1.0 / sc.mu
    T, W, warm = sc.duration(), sc.report_interval, sc.warmup_time()
    D = sc.deadline_ms / 1000.0

    rng_t = np.random.default_rng([seed, 11])     # traffic and job sizes
    rng_n = np.random.default_rng([seed, 22])     # path delays and jitter
    rng_r = np.random.default_rng([seed, 33])     # report losses and late reports
    rng_p = np.random.default_rng([seed, 44])     # probe jitter (Prequal-style only)

    # ---- path delays: Ingress A exactly 8/16/60 ms, the others within +/- 25%
    if sc.delay_matrix_ms:                             # staleness study: one explicit row per ingress
        d_true = np.array(sc.delay_matrix_ms, dtype=float) / 1000.0
        if d_true.shape != (R, S):
            raise ValueError(f"delay_matrix_ms must be {R} x {S}")
    else:
        base = np.array(sc.base_delay_ms) / 1000.0
        spread = rng_n.uniform(-1, 1, size=(R, S)) * sc.delay_spread
        spread[0] = 0.0
        d_true = base[None, :] * (1.0 + spread)       # round trip, seconds
    jit = sc.jitter_ms / 1000.0
    d_known = d_true + 2.0 * jit                       # rules know the average delay

    # ---- traffic
    shares = np.arange(R, 0, -1, dtype=float) if sc.traffic == "unequal" else np.ones(R)
    shares /= shares.sum()
    cap = c.sum() * mu
    lam1 = sc.load * cap
    lam2 = sc.load_jump_to * cap if sc.load_jump_to > 0 else lam1
    t_switch = T / 2 if sc.load_jump_to > 0 else T
    times, owner = [], []
    if sc.share_profile:                               # staleness study: shifting traffic between ingresses
        times, owner = _arrivals_shares(rng_t, sc, cap, shares, T, R)
        ps = np.array([p[1] for p in sc.share_profile], float)
        ps = ps / ps.sum(axis=1, keepdims=True)
        pt = [p[0] for p in sc.share_profile] + [T]
        shares = sum(ps[k] * max(0.0, min(pt[k + 1], T) - pt[k]) for k in range(len(ps))) / T
    else:
        for i in range(R):
            if sc.load_profile:
                a = _arrivals_profile(rng_t, cap * shares[i], sc.load_profile, T)
            else:
                a = _arrivals(rng_t, lam1 * shares[i], lam2 * shares[i], t_switch, T)
            times.append(a)
            owner.append(np.full(len(a), i))
    if sc.surge:                                       # one ingress sends extra frames for a while
        k_in, factor, s0, s1 = sc.surge
        rng_s = np.random.default_rng([seed, 66])
        extra = rng_s.uniform(s0, s1, rng_s.poisson((factor - 1.0) * lam1 * shares[k_in] * (s1 - s0)))
        times.append(np.sort(extra))
        owner.append(np.full(len(extra), k_in))
    times = np.concatenate(times)
    owner = np.concatenate(owner)
    order = np.argsort(times, kind="stable")
    created = times[order].tolist()
    ing = owner[order].tolist()
    nf = len(created)
    size = sample_jobs(rng_t, nf, sc.job_shape, sc.job_scv, m).tolist()
    if jit > 0:
        j_out = rng_n.exponential(jit, nf).tolist()
        j_back = rng_n.exponential(jit, nf).tolist()
    else:
        j_out = j_back = [0.0] * nf

    # ---- what the rules know
    late = [[late_table(int(c_known[s]), mu, D - d_known[i, s], sc.job_shape, sc.job_scv) for s in range(S)]
            for i in range(R)]
    late_exp = [[late_table(int(c_known[s]), mu, D - d_known[i, s], "exp", 1.0) for s in range(S)] for i in range(R)]
    nsys = [0] * S
    c_now = c.tolist()                                 # servers working right now (changes only in a stress test)
    spd = [1.0] * S                                    # speed of each site's servers (changes only in "slow GPUs")
    extra_late = {}

    def late_for(i, s, cs):                            # late(n) for another number of servers (same speed)
        if cs == int(c_known[s]):
            return late[i][s]
        key = (i, s, cs)
        if key not in extra_late:
            extra_late[key] = late_table(cs, mu, D - d_known[i, s], sc.job_shape, sc.job_scv)
        return extra_late[key]

    def late_true(i, s, cs, sp):                       # the oracle: true servers AND their true speed
        if sp == 1.0:
            return late_for(i, s, cs)
        key = (i, s, cs, sp)
        if key not in extra_late:
            extra_late[key] = late_table(cs, mu * sp, D - d_known[i, s], sc.job_shape, sc.job_scv)
        return extra_late[key]

    grid_cache = {}

    def grid_ager(cs, lams):                           # shared by all ingresses of this run (ours v2)
        key = (cs, tuple(np.round(lams, 9)))
        if key not in grid_cache:
            grid_cache[key] = GridAger(cs, mu, lams)
        return grid_cache[key]

    ctx = SimpleNamespace(S=S, c=c_known, mu=mu, scv=sc.job_scv, D=D, W=W, d_known=d_known, late=late,
                          late_exp=late_exp, mean_t=[mean_time_table(int(c_known[s]), mu) for s in range(S)],
                          nsys=nsys, c_now=c_now, speed_now=spd, late_for=late_for, late_true=late_true,
                          frame=0, grid_ager=grid_ager,
                          ingress_rate=(lam1 * shares).tolist(),
                          report_bytes=sc.report_bytes, counter_bytes=sc.counter_bytes,
                          budget_bps=(sc.budget_bps if sc.budget_bps > 0
                                      else S * (sc.report_bytes + sc.counter_bytes) / W),
                          probe_bytes=sc.probe_bytes,
                          rngs=[np.random.default_rng([seed, 55, i]) for i in range(R)])
    cls = resolve_rule(rule)
    ctx_r = ctx                                        # the context the rules see
    if guard and not getattr(cls, "oracle", False):
        ctx_r = SimpleNamespace(**vars(ctx))
        for name in TRUE_STATE:
            setattr(ctx_r, name, _Tripwire(name))
    rules = [cls(ctx_r, i) for i in range(R)]
    uses_reports, needs_replies = cls.uses_reports, cls.needs_replies
    echo = bool(getattr(cls, "uses_drop_echo", False))   # v6.1: aggregate drop counter (off for every other rule)
    echo_b = int(sc.echo_bytes) if echo else 0
    one_report = sc.report_bytes + (sc.counter_bytes if cls.uses_counter else 0) + echo_b
    lat_probes = bool(getattr(cls, "probes_latency", False))
    # ---- telemetry options (staleness study)
    rep_delay = float(sc.report_delay_s)
    noise_sd = float(sc.report_noise_sd)
    rng_m = np.random.default_rng([seed, 77]) if noise_sd > 0 else None
    if sc.report_mode not in ("periodic", "threshold"):
        raise ValueError(f"unknown report_mode {sc.report_mode!r}")
    thr_mode = sc.report_mode == "threshold"
    thr = float(sc.report_threshold)
    heartbeat = sc.report_heartbeat if sc.report_heartbeat > 0 else 4.0 * W
    last_sent_q = [None] * S
    last_sent_t = [-1e9] * S
    report_msgs = 0
    rounds_sent = rounds_total = 0
    half = (d_true / 2.0).tolist()                     # one-way delays as plain lists (faster in the loop)
    c_l = c_now
    if sc.path_event:                                  # congestion: one site's path delays x factor for a while
        pe_site, pe_f, pe_t0, pe_t1 = sc.path_event

        def hop(i, s, t):
            return half[i][s] * pe_f if (s == pe_site and pe_t0 <= t < pe_t1) else half[i][s]
    else:
        def hop(i, s, t):
            return half[i][s]

    # ---- state
    busy = [0] * S
    waiting = [deque() for _ in range(S)]
    arrived_in_window = [0] * S
    site_of = [0] * nf
    pred = [math.nan] * nf
    finish = [math.nan] * nf
    discard = bool(sc.site_discard)
    dropped = [False] * nf                             # dropped at the ingress by the rule
    discarded = [False] * nf                           # discarded by a deadline-aware site
    disc_in_window = [0] * S
    rx_x = {}                                          # discards carried by a report in flight (by event number)
    echo_in_window = [0] * S                           # v6.1: drop counts that reached each site in its window
    rx_e = {}                                          # v6.1: their sum, carried by a report in flight
    echo_msgs = 0
    heap = []
    seq = 0
    report_sent_bytes = 0
    # ---- measurements only (they never change a decision)
    nan = math.nan
    arr_t = [nan] * nf                                 # arrival at the site
    start_t = [nan] * nf                               # service start
    info_g = [[-1e9] * S for _ in range(R)]            # newest telemetry (report or probe) each ingress holds
    info_q = [[0] * S for _ in range(R)]
    aoi, est_err = [], []                              # at each counted decision: age and error of that telemetry
    last_site = [-1] * R
    n_switch = n_sent_counted = 0
    rif_arr = [0] * nf if lat_probes else None
    site_hist = [deque(maxlen=400) for _ in range(S)] if lat_probes else None
    t_lo, t_hi = warm, T                               # time integrals over the measured window
    tl = [t_lo] * S
    area_n, area_b, area_c = [0.0] * S, [0.0] * S, [0.0] * S
    maxq = [0] * S
    LAT_WIN = 2.0

    def touch(s, t):                                   # integrate frames, busy and working servers up to t
        t1 = t if t < t_hi else t_hi
        t0 = tl[s]
        if t1 > t0:
            dt = t1 - t0
            area_n[s] += nsys[s] * dt
            area_b[s] += busy[s] * dt
            area_c[s] += c_l[s] * dt
            tl[s] = t1

    def lat_estimate(s, t):
        """Server-side latency estimate for a probe (Prequal): median time at the site of the frames finished in the
        last LAT_WIN seconds that found a number in flight closest to the current one (within 1 of the closest)."""
        rif = nsys[s]
        cand = []
        for tf, rf, so in reversed(site_hist[s]):
            if tf < t - LAT_WIN:
                break
            cand.append((abs(rf - rif), so))
        if not cand:                                   # nothing recent: one service time plus the visible wait
            return (1.0 + max(0, rif - c_l[s]) / max(c_l[s], 1)) * m / spd[s]
        best = min(dd for dd, _ in cand)
        return float(np.median([so for dd, so in cand if dd <= best + 1]))
    offsets = [(s * W / S) if sc.stagger_reports else 0.0 for s in range(S)]
    for s in range(S):
        heapq.heappush(heap, (offsets[s] + W, seq, REPORT_GEN, s, 0, 0, 0.0, 0)); seq += 1
    if sc.cap_drop:
        heapq.heappush(heap, (T / 2, seq, CAP_CHANGE, sc.cap_drop[0], sc.cap_drop[1], 0, 0.0, 0)); seq += 1
    for t_ev, s_ev, n_ev in sc.cap_events:
        heapq.heappush(heap, (t_ev, seq, CAP_CHANGE, s_ev, n_ev, 0, 0.0, 0)); seq += 1
    for t_ev, s_ev, f_ev in sc.speed_events:           # the factor travels in the float slot
        heapq.heappush(heap, (t_ev, seq, SPEED_CHANGE, s_ev, 0, 0, float(f_ev), 0)); seq += 1

    series = [] if keep_series else None
    ts_next, ts_end, ts_step = warm + 20.0, warm + 50.0, 0.2

    def throw_away(s, idx, t):
        """A deadline-aware site discards a frame whose turn came after its deadline (it is not served)."""
        nonlocal seq
        touch(s, t)
        nsys[s] -= 1
        discarded[idx] = True
        disc_in_window[s] += 1
        if needs_replies:                              # the ingress gets a reject back
            i = ing[idx]
            fin = t + hop(i, s, t) + j_back[idx]
            heapq.heappush(heap, (fin, seq, REPLY, i, s, idx, fin - created[idx], 0)); seq += 1

    def expire(s, t):
        """Discard the frames at the head of site s's queue whose deadline has passed (site_discard only)."""
        w = waiting[s]
        while w and created[w[0]] + D < t:
            throw_away(s, w.popleft(), t)

    k = 0
    INF = float("inf")
    while k < nf or heap:
        t_frame = created[k] if k < nf else INF
        if heap and heap[0][0] <= t_frame:
            t, sq, ev, a, b, q, g, A = heapq.heappop(heap)
        else:
            t, ev = t_frame, -1
        if series is not None:
            while ts_next <= t and ts_next <= ts_end:
                series.append([ts_next] + list(nsys))
                ts_next += ts_step

        if ev == -1:                                   # a new frame at its ingress
            idx = k
            k += 1
            i = ing[idx]
            r = rules[i]
            ctx_r.frame = idx
            s, p = r.choose(t)
            if s < 0:                                  # dropped at the ingress: never sent, counts as a miss
                r.on_drop(t)
                site_of[idx], pred[idx] = -1, p
                dropped[idx] = True
            else:
                r.on_send(t, s)
                site_of[idx], pred[idx] = s, p
                tag = 0
                if echo and r.echo_out:                # v6.1: this frame carries the ingress's drop count
                    tag, r.echo_out = int(r.echo_out), 0
                    echo_msgs += 1
                heapq.heappush(heap, (t + hop(i, s, t) + j_out[idx], seq, ARR_SITE, s, idx, tag, 0.0, 0)); seq += 1
                if t >= warm:                          # measurements: age and error of the telemetry it held
                    gi = info_g[i][s]
                    if gi > -1e8:
                        aoi.append(t - gi)
                        est_err.append(abs(info_q[i][s] - nsys[s]))
                    if last_site[i] >= 0 and last_site[i] != s:
                        n_switch += 1
                    n_sent_counted += 1
                last_site[i] = s
            if r.probe_out:
                for s2 in r.probe_out:
                    tj = rng_p.exponential(jit) if jit > 0 else 0.0
                    heapq.heappush(heap, (t + hop(i, s2, t) + tj, seq, PROBE_AT, i, s2, 0, 0.0, 0)); seq += 1
                r.probe_out.clear()

        elif ev == ARR_SITE:
            s, idx = a, b
            touch(s, t)
            nsys[s] += 1
            arr_t[idx] = t
            if lat_probes:
                rif_arr[idx] = nsys[s]
            if nsys[s] > maxq[s] and warm <= t <= T:
                maxq[s] = nsys[s]
            arrived_in_window[s] += 1
            if q:                                      # v6.1: the drop count this frame carries
                echo_in_window[s] += q
            if busy[s] < c_l[s]:
                if discard and created[idx] + D < t:   # arrived after its deadline (only with huge delays)
                    throw_away(s, idx, t)
                else:
                    busy[s] += 1
                    start_t[idx] = t
                    heapq.heappush(heap, (t + size[idx] / spd[s], seq, DONE, s, idx, 0, 0.0, 0)); seq += 1
            else:
                waiting[s].append(idx)

        elif ev == DONE:
            s, idx = a, b
            touch(s, t)
            nsys[s] -= 1
            i = ing[idx]
            fin = t + hop(i, s, t) + j_back[idx]
            finish[idx] = fin
            if lat_probes:
                site_hist[s].append((t, rif_arr[idx], t - arr_t[idx]))
            if needs_replies:
                heapq.heappush(heap, (fin, seq, REPLY, i, s, idx, fin - created[idx], 0)); seq += 1
            if discard:
                expire(s, t)
            if waiting[s] and busy[s] <= c_l[s]:
                nxt = waiting[s].popleft()                 # the freed server takes the next frame
                start_t[nxt] = t
                heapq.heappush(heap, (t + size[nxt] / spd[s], seq, DONE, s, nxt, 0, 0.0, 0)); seq += 1
            else:
                busy[s] -= 1                               # (also when the site just lost servers)

        elif ev == REPORT_GEN:
            s = a
            if discard:
                expire(s, t)                           # the site's count holds no frame already past its deadline
            q_now, A_now = nsys[s], arrived_in_window[s]
            X_now = disc_in_window[s]
            arrived_in_window[s] = 0
            disc_in_window[s] = 0
            E_now = echo_in_window[s]
            echo_in_window[s] = 0
            if noise_sd > 0:                           # measurement noise (staleness study)
                q_now = max(0, int(round(q_now + rng_m.normal(0.0, noise_sd))))
            send = True
            if thr_mode:                               # sampled send-on-delta (staleness study)
                send = (last_sent_q[s] is None or abs(q_now - last_sent_q[s]) >= thr * c_known[s] - 1e-9
                        or t - last_sent_t[s] >= heartbeat - 1e-9)
                if send:
                    last_sent_q[s], last_sent_t[s] = q_now, t
            rounds_total += 1
            rounds_sent += send
            for i in range(R):
                lost = rng_r.random() < sc.report_loss
                extra = rng_r.uniform(0, sc.report_extra_delay_s) if sc.report_extra_delay_s > 0 else 0.0
                tj = rng_r.exponential(jit) if jit > 0 else 0.0
                if uses_reports and send:
                    report_sent_bytes += one_report
                    report_msgs += 1
                    if not lost:
                        if X_now:
                            rx_x[seq] = X_now
                        if E_now:
                            rx_e[seq] = E_now
                        heapq.heappush(heap, (t + hop(i, s, t) + tj + extra + rep_delay, seq, REPORT_RCV,
                                              i, s, q_now, t, A_now)); seq += 1
            if t + W < T:
                heapq.heappush(heap, (t + W, seq, REPORT_GEN, s, 0, 0, 0.0, 0)); seq += 1

        elif ev == REPORT_RCV:
            if g > info_g[a][b]:
                info_g[a][b], info_q[a][b] = g, q
            if echo:
                rules[a].on_report_e(t, b, q, g, A, rx_x.pop(sq, 0), rx_e.pop(sq, 0))
            else:
                rules[a].on_report_x(t, b, q, g, A, rx_x.pop(sq, 0))

        elif ev == REPLY:
            rules[a].on_reply(t, b, g, q)

        elif ev == PROBE_AT:
            i, s = a, b
            lat = lat_estimate(s, t) if lat_probes else 0
            heapq.heappush(heap, (t + hop(i, s, t), seq, PROBE_BACK, i, s, nsys[s], t, lat)); seq += 1

        elif ev == PROBE_BACK:
            if g > info_g[a][b]:
                info_g[a][b], info_q[a][b] = g, q
            if lat_probes:
                rules[a].on_probe_x(t, b, q, g, A)
            else:
                rules[a].on_probe(t, b, q, g)

        elif ev == CAP_CHANGE:                         # a site loses (or gains) working servers, unannounced
            s = a
            touch(s, t)
            c_l[s] = b
            if discard:
                expire(s, t)
            while busy[s] < c_l[s] and waiting[s]:
                nxt = waiting[s].popleft()
                busy[s] += 1
                start_t[nxt] = t
                heapq.heappush(heap, (t + size[nxt] / spd[s], seq, DONE, s, nxt, 0, 0.0, 0)); seq += 1

        elif ev == SPEED_CHANGE:                       # a site's servers get slower or faster, unannounced
            spd[a] = g                                 # (frames already in service keep their time)

    # ---- results (frames created after the warm-up)
    created_a = np.array(created)
    keep = created_a >= warm
    drop_k = np.array(dropped, dtype=bool)[keep]
    disc_k = np.array(discarded, dtype=bool)[keep]
    answered = ~(drop_k | disc_k)
    resp_all = (np.array(finish) - created_a)[keep]
    resp = resp_all[answered]                          # times of the frames that got an answer
    late_flag = np.ones(len(resp_all), dtype=bool)     # missed = late, dropped or discarded
    late_flag[answered] = resp > D
    sites = np.array(site_of)[keep]
    share = np.bincount(sites[sites >= 0], minlength=S) / max(1, keep.sum())

    # stability: each site's offered load per 1-second bin, relative to its capacity
    bins = np.arange(math.floor(warm), math.floor(T) + 1)
    swing = []
    for s in range(S):
        h, _ = np.histogram(created_a[keep][sites == s], bins=bins)
        swing.append(float(np.std(h / (c[s] * mu))))
    probe_bytes = sum(r.probe_bytes for r in rules)
    echo_bytes = echo_msgs * echo_b                    # v6.1: drop counts sent ingress -> site (0 for other rules)
    out = {
        "scenario": sc.key, "rule": rule, "seed": seed,
        "frames": int(keep.sum()),
        "miss": float(late_flag.mean()),
        "mean_ms": float(resp.mean() * 1000) if len(resp) else float("nan"),       # answered frames only
        "p99_ms": float(np.percentile(resp, 99) * 1000) if len(resp) else float("nan"),
        "share": share.tolist(),
        "miss_by_site": [float(late_flag[sites == s].mean()) if (sites == s).any() else float("nan")
                         for s in range(S)],
        "swing": float(np.mean(swing)),
        "bytes_per_s": (report_sent_bytes + probe_bytes + echo_bytes) / T,
        "runtime_s": round(time.time() - t_wall, 2),
        # v5 study: the three kinds of miss (they add up to "miss")
        "late": float((late_flag & answered).mean()),
        "dropped": float(drop_k.mean()),
        "discarded": float(disc_k.mean()),
    }
    if cls.predicts:
        pr = np.array(pred)[keep]
        ok = np.isfinite(pr)
        idx = np.clip(np.digitize(pr[ok], CALIB_EDGES) - 1, 0, len(CALIB_EDGES) - 2)
        nb = len(CALIB_EDGES) - 1
        out["calib"] = {
            "n": np.bincount(idx, minlength=nb).tolist(),
            "pred_sum": np.bincount(idx, weights=pr[ok], minlength=nb).tolist(),
            "late": np.bincount(idx, weights=late_flag[ok].astype(float), minlength=nb).tolist(),
        }
    if series is not None:
        out["series"] = series
    if hasattr(rules[0], "diag"):                      # rules with a speed meter: what ingress A measured
        out["diag"] = rules[0].diag()

    # ---- staleness study: full measurements (observations only)
    n = int(keep.sum())
    n_rej = int(drop_k.sum())
    n_exp = int(disc_k.sum())
    n_late = int((late_flag & answered).sum())
    n_succ = int((~late_flag).sum())
    if n_succ + n_late + n_exp + n_rej != n:           # request conservation
        raise AssertionError("request conservation violated")
    unresolved = sum(1 for x in range(nf) if not (dropped[x] or discarded[x] or finish[x] == finish[x]))
    if unresolved:
        raise AssertionError(f"{unresolved} frames never finished")
    span = max(T - warm, 1e-9)
    for s in range(S):
        touch(s, T)
    util = [area_b[s] / area_c[s] if area_c[s] > 0 else float("nan") for s in range(S)]
    u = np.array(util, float)
    st_a = np.array(start_t)[keep]
    ar_a = np.array(arr_t)[keep]
    served = np.isfinite(st_a)
    wait = (st_a - ar_a)[served]
    size_a = np.array(size)[keep]
    bins2 = np.arange(math.floor(warm), math.ceil(T) + 1)
    ck = created_a[keep]

    def per_second(mask):
        h, _ = np.histogram(ck[mask], bins=bins2)
        return h.astype(int).tolist()

    aoi_a = np.array(aoi, float)
    err_a = np.array(est_err, float)
    probe_msgs = 2 * probe_bytes // max(1, sc.probe_bytes)      # a probe = request + reply
    out.update({
        "success": n_succ / n if n else float("nan"),
        "late_completed": n_late / n if n else float("nan"),
        "expired": n_exp / n if n else float("nan"),
        "rejected": n_rej / n if n else float("nan"),
        "admitted": 1.0 - n_rej / n if n else float("nan"),
        "counts": {"frames": n, "success": n_succ, "late": n_late, "expired": n_exp, "rejected": n_rej},
        "p50_ms": float(np.percentile(resp, 50) * 1000) if len(resp) else float("nan"),
        "p95_ms": float(np.percentile(resp, 95) * 1000) if len(resp) else float("nan"),
        "wait_ms": float(wait.mean() * 1000) if len(wait) else float("nan"),
        "wait_p95_ms": float(np.percentile(wait, 95) * 1000) if len(wait) else float("nan"),
        "offered_load": float(size_a.sum() / (span * c.sum())),     # generated work / configured capacity
        "offered_rate": n / span,                                   # frames per second
        "completed_rate": int(answered.sum()) / span,              # answered (on time or late) per second
        "goodput": n_succ / span,                                   # on time per second
        "util": util,
        "util_mean": float(np.nanmean(u)),
        "imbalance": float(np.nanstd(u) / np.nanmean(u)) if np.nanmean(u) > 0 else float("nan"),
        "avg_queue": [area_n[s] / span for s in range(S)],
        "avg_queue_mean": float(np.mean([area_n[s] / span for s in range(S)])),
        "max_queue": maxq,
        "max_queue_max": int(max(maxq)),
        "report_bytes_per_s": report_sent_bytes / T,
        "probe_bytes_per_s": probe_bytes / T,
        "bytes_per_s_per_ingress": (report_sent_bytes + probe_bytes + echo_bytes) / T / R,
        "echo_bytes_per_s": echo_bytes / T,
        "echo_msgs": int(echo_msgs),
        "report_msgs": int(report_msgs),
        "probe_msgs": int(probe_msgs),
        "msgs_per_s": (report_msgs + probe_msgs) / T,
        "report_rounds_sent": rounds_sent / rounds_total if rounds_total else float("nan"),
        "aoi_mean_s": float(aoi_a.mean()) if len(aoi_a) else float("nan"),
        "aoi_p95_s": float(np.percentile(aoi_a, 95)) if len(aoi_a) else float("nan"),
        "est_err_mean": float(err_a.mean()) if len(err_a) else float("nan"),
        "est_err_p95": float(np.percentile(err_a, 95)) if len(err_a) else float("nan"),
        "decisions": n,
        "switch_rate": n_switch / n_sent_counted if n_sent_counted else float("nan"),
        "ts": {"t0": int(bins2[0]), "frames": per_second(np.ones(n, bool)), "success": per_second(~late_flag),
               "rejected": per_second(drop_k), "expired": per_second(disc_k),
               "late": per_second(late_flag & answered)},
        "runtime_s": round(time.time() - t_wall, 2),
    })
    if hook is not None:
        hook({"rules": rules, "ctx": ctx, "ctx_rules": ctx_r, "created": created, "size": size, "ing": ing,
              "site_of": site_of, "finish": finish, "dropped": dropped, "discarded": discarded,
              "arr_t": arr_t, "start_t": start_t, "D": D, "warm": warm, "T": T, "d_true": d_true,
              "aoi": aoi, "est_err": est_err})
    return out
