"""Queueing math: job sizes, late(n) tables, belief ageing, and textbook formulas.

A site = c identical servers and one first-come, first-served queue.
n always means the number of frames AT the site (waiting + being processed).
"""
import math

import numpy as np
from scipy import stats
from scipy.linalg import expm

N_STATES = 64          # beliefs track 0 .. 63 frames per site (the last state means "63 or more")


# ------------------------------------------------------------------ job sizes
def _mix():
    from .config import JOB_MIX, JOB_MIX_WITHIN
    return np.array([w for w, _ in JOB_MIX]), np.array([r for _, r in JOB_MIX]), JOB_MIX_WITHIN


def sample_jobs(rng, n, shape, scv, mean):
    """n job sizes (seconds) with the given mean and variability (scv).
    "mix": two kinds of job (config.JOB_MIX), each Gamma-shaped; scv is then the overall variability."""
    if shape == "mix":
        w, r, v = _mix()
        kind = rng.choice(len(w), size=n, p=w)
        return rng.gamma(1.0 / v, v * mean * r[kind])
    if shape == "exp":
        return rng.exponential(mean, n)
    if shape == "gamma":
        return rng.gamma(1.0 / scv, scv * mean, n)
    if shape == "lognormal":
        s2 = math.log(1.0 + scv)
        return rng.lognormal(math.log(mean) - s2 / 2.0, math.sqrt(s2), n)
    raise ValueError(shape)


def job_sf(t, shape, scv, mean):
    """P(one job takes longer than t)."""
    if shape == "exp":
        return math.exp(-t / mean)
    if shape == "gamma":
        return float(stats.gamma.sf(t, a=1.0 / scv, scale=scv * mean))
    if shape == "mix":
        w, r, v = _mix()
        return float(sum(wi * stats.gamma.sf(t, a=1.0 / v, scale=v * mean * ri) for wi, ri in zip(w, r)))
    s2 = math.log(1.0 + scv)
    return float(stats.lognorm.sf(t, s=math.sqrt(s2), scale=math.exp(math.log(mean) - s2 / 2.0)))


# ------------------------------------------------------------------ late(n)
def late_table(c, mu, tau, shape="gamma", scv=0.25, N=N_STATES):
    """late[n] = P(this frame finishes after the time left tau | n frames already at the site).

    tau = deadline - round-trip path delay.
      exponential jobs: exact (wait for j = n-c+1 departures at rate c*mu, then our own job).
      other shapes    : a free server -> exactly our own job time;
                        otherwise a Gamma fitted to the mean and variance of (wait + own job).
    """
    late = np.ones(N)
    if tau <= 0:
        return late
    m = 1.0 / mu
    n = np.arange(N)
    if shape == "exp":
        nu = c * mu
        for k in range(N):
            if k < c:
                late[k] = math.exp(-mu * tau)
            elif c == 1:
                late[k] = stats.poisson.cdf(k, mu * tau)
            else:
                j = k - c + 1
                wait_done = stats.poisson.sf(j - 1, nu * tau)
                mix = stats.poisson.sf(j - 1, (nu - mu) * tau)
                late[k] = 1.0 - wait_done + math.exp(-mu * tau) * (nu / (nu - mu)) ** j * mix
        return np.clip(late, 0.0, 1.0)
    j = np.maximum(0, n - c + 1)
    v_dep = 1.0 + (scv - 1.0) / math.sqrt(c)          # variability of the gaps between departures
    M = j * m / c + m
    V = j * v_dep * (m / c) ** 2 + scv * m * m
    late = stats.gamma.sf(tau, a=M * M / V, scale=V / M)
    late[n < c] = job_sf(tau, shape, scv, m)          # a server is free: only our own job counts
    return np.clip(late, 0.0, 1.0)


def mean_time_table(c, mu, N=N_STATES):
    """Average wait + own processing (seconds) if n frames are at the site."""
    n = np.arange(N)
    return np.maximum(0, n - c + 1) / (c * mu) + 1.0 / mu


# ------------------------------------------------------------------ beliefs
def point(q, N=N_STATES):
    b = np.zeros(N)
    b[min(max(int(q), 0), N - 1)] = 1.0
    return b


def poisson_jump(theta, N=N_STATES):
    """Probabilities of 0, 1, 2, ... extra frames from the other ingresses per own send."""
    if theta <= 1e-9:
        return np.array([1.0])
    k = np.arange(min(N, int(theta + 8 * math.sqrt(theta) + 10)))
    return stats.poisson.pmf(k, theta)


def own_send(b, jump):
    """Our frame (+1) and a random number of copy-cat frames from the others."""
    N = len(b)
    nb = np.convolve(b, jump) if len(jump) > 1 else b
    out = np.zeros(N)
    out[1:] = nb[:N - 1]
    out[-1] += nb[N - 1:].sum()
    return out


class Ager:
    """Moves a belief forward in time: frames finish (rate mu*min(n,c)), background frames arrive (lam).

    Exact for exponential jobs (a birth-death chain); an approximation for other job shapes.
    Precomputes the transition matrix for 1 ms, 2 ms, 4 ms, ... so any time step costs a few
    small matrix-vector products.
    """
    DT0 = 0.001
    LEVELS = 18                         # largest single step: 2^17 ms ~ 131 s (longer = stationary anyway)

    def __init__(self, c, mu, lam, N=N_STATES):
        self.lam = lam
        Q = np.zeros((N, N))
        i = np.arange(N - 1)
        Q[i, i + 1] = lam
        Q[i + 1, i] = mu * np.minimum(np.arange(1, N), c)
        Q[np.arange(N), np.arange(N)] = -Q.sum(axis=1)
        P = expm(Q * self.DT0)
        self.P = [P]
        for _ in range(self.LEVELS - 1):
            P = P @ P
            self.P.append(P)

    def age(self, b, dt):
        k = int(dt / self.DT0 + 0.5)
        if k <= 0:
            return b
        k = min(k, (1 << self.LEVELS) - 1)
        j = 0
        while k:
            if k & 1:
                b = b @ self.P[j]
            k >>= 1
            j += 1
        s = b.sum()
        return b / s if s > 0 else b


class GridAger:
    """Ages one belief under several arrival rates at once (one row per rate): used by ours v2 to try every
    traffic level for a site in one go. Same birth-death model and the same 1 ms, 2 ms, 4 ms ... steps as Ager."""
    DT0, LEVELS = Ager.DT0, Ager.LEVELS

    def __init__(self, c, mu, lams, N=N_STATES):
        mats = [Ager(c, mu, float(lam), N).P for lam in lams]
        self.single = mats
        self.P = [np.stack([m[j] for m in mats]) for j in range(self.LEVELS)]     # per step size: (rates, N, N)

    def _steps(self, dt):
        k = int(dt / self.DT0 + 0.5)
        k = min(max(k, 0), (1 << self.LEVELS) - 1)
        j = 0
        while k:
            if k & 1:
                yield j
            k >>= 1
            j += 1

    def age_all(self, B, dt):
        """B: one belief per rate (rows). Each row is aged under its own rate."""
        for j in self._steps(dt):
            B = np.einsum("kn,knm->km", B, self.P[j])
        s = B.sum(axis=1, keepdims=True)
        return B / np.where(s > 0, s, 1.0)

    def age_one(self, b, dt, idx):
        """One belief aged under rate number idx."""
        for j in self._steps(dt):
            b = b @ self.single[idx][j]
        s = b.sum()
        return b / s if s > 0 else b


class NoAger:
    """Ablation: the belief does not change with time."""
    lam = 0.0

    def age(self, b, dt):
        return b


# ------------------------------------------------------------------ one aged number (Dahlin-style)
def fluid(n, lam, c, mu, T):
    """Deterministic ageing of one number: dn/dt = lam - mu*min(n, c), n >= 0."""
    t = 0.0
    for _ in range(4):
        rem = T - t
        if rem <= 1e-12:
            return max(n, 0.0)
        if n > c + 1e-12:
            drift = lam - c * mu
            if drift >= 0:
                return n + drift * rem
            tc = (n - c) / (-drift)
            if tc >= rem:
                return n + drift * rem
            n, t = float(c), t + tc
        else:
            ninf = lam / mu
            if ninf <= c or n < c - 1e-12 and math.exp(-mu * rem) * (n - ninf) + ninf <= c:
                return max(ninf + (n - ninf) * math.exp(-mu * rem), 0.0)
            if n >= c - 1e-12:
                return c + (lam - c * mu) * rem
            tc = -math.log((ninf - c) / (ninf - n)) / mu
            n, t = float(c), t + tc
    return max(n, 0.0)


# ------------------------------------------------------------------ textbook formulas (for the checks)
def erlang_c(c, a):
    """Chance that an arriving frame has to wait in an M/M/c queue, a = lam / mu."""
    top = a ** c / math.factorial(c) * c / (c - a)
    return top / (sum(a ** k / math.factorial(k) for k in range(c)) + top)


def stationary(c, mu, lam, N=400):
    """Long-run distribution of frames at an M/M/c site."""
    p = np.zeros(N)
    p[0] = 1.0
    for n in range(1, N):
        p[n] = p[n - 1] * lam / (min(n, c) * mu)
    return p / p.sum()
