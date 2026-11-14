"""Built-in checks: is the simulator right, and are the formulas inside our rule right?

  1. Simulator vs textbook. One M/M/c site (exponential jobs, Poisson arrivals). The simulated mean
     time and deadline-miss rate must match the Erlang C formulas.
  2. late(n). One site; frames that find n frames already there. The simulated share that is late
     vs our late(n) table, for 3 job shapes x 3 site sizes. Exact for exponential jobs, an
     approximation (two-moment Gamma fit) for the other shapes.
  3. Belief ageing b(n). Look at the site at time g, then again dt later. The spread of values our
     rule predicts (the old value aged by the birth-death model) vs what is actually seen.

Checks 2 and 3 use a small stand-alone first-come-first-served simulator (independent of engine.py),
so they test the formulas, while check 1 tests engine.py itself.
"""
import heapq
import math
from dataclasses import replace

import numpy as np
from scipy import stats

from .config import MAIN
from .engine import run
from .queueing import Ager, N_STATES, erlang_c, late_table, point, sample_jobs

MU = 10.0          # frames per second per server (100 ms jobs), as in the main scenario
LOAD = 0.85


# ---------------------------------------------------------------------------------------- check 1
def mmc_tail(t, c, mu, lam):
    """P(time at the site > t) for an M/M/c first-come-first-served site."""
    C = erlang_c(c, lam / mu)
    th = c * mu - lam                                   # rate of the waiting time when one waits
    if abs(th - mu) < 1e-9:
        conv = math.exp(-mu * t) * (1 + mu * t)
    else:
        conv = (th * math.exp(-mu * t) - mu * math.exp(-th * t)) / (th - mu)
    return (1 - C) * math.exp(-mu * t) + C * conv


def mmc_mean(c, mu, lam):
    return 1.0 / mu + erlang_c(c, lam / mu) / (c * mu - lam)


def ci95(x):
    x = np.asarray(x, float)
    if len(x) < 2:
        return float(x.mean()), float("nan")
    return float(x.mean()), float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x)))


def check_engine(quick=False, log=print):
    rows = []
    T, seeds = (600.0, range(1, 4)) if quick else (3000.0, range(1, 6))
    for c in (2, 4, 8):
        sc = replace(MAIN, key=f"check_mmc{c}", servers=(c,), base_delay_ms=(0.0,), ingresses=1,
                     job_shape="exp", job_scv=1.0, load=LOAD, deadline_ms=300.0, sim_time=T)
        outs = [run(sc, "nearest", sd) for sd in seeds]
        lam = LOAD * c * MU
        for what, th, sims, scale in (
                ("mean time (ms)", mmc_mean(c, MU, lam) * 1000, [o["mean_ms"] for o in outs], 1.0),
                ("P(time > 300 ms) (%)", mmc_tail(0.3, c, MU, lam) * 100, [o["miss"] * 100 for o in outs], 1.0)):
            m, h = ci95(sims)
            ok = abs(m - th) <= max(h, 0.02 * abs(th)) + 1e-9
            rows.append(dict(check="1. simulator vs Erlang C", case=f"M/M/{c} at {LOAD:.0%} load", quantity=what,
                             model=round(th, 3), simulated=round(m, 3), ci95=round(h, 3),
                             error=round(m - th, 3), verdict="OK" if ok else "CHECK"))
            log(f"    M/M/{c}: {what:22s} theory {th:8.3f}  simulated {m:8.3f} +/- {h:.3f}  {'OK' if ok else 'CHECK'}")
    return rows


# ---------------------------------------------------------------------------------------- stand-alone FCFS site
def fcfs(rng, lam, c, mu, shape, scv, n_jobs):
    """One first-come-first-served site. Returns arrival times, departure times, frames found at arrival."""
    arr = np.cumsum(rng.exponential(1.0 / lam, n_jobs))
    size = sample_jobs(rng, n_jobs, shape, scv, 1.0 / mu)
    free = [0.0] * c
    insys = []
    dep = np.empty(n_jobs)
    found = np.empty(n_jobs, dtype=int)
    a_l, s_l = arr.tolist(), size.tolist()
    for k in range(n_jobs):
        t = a_l[k]
        while insys and insys[0] <= t:
            heapq.heappop(insys)
        found[k] = len(insys)
        start = max(t, heapq.heappop(free))
        d = start + s_l[k]
        heapq.heappush(free, d)
        heapq.heappush(insys, d)
        dep[k] = d
    return arr, dep, found


SHAPES = (("regular (gamma, v=0.25)", "gamma", 0.25), ("exponential (v=1)", "exp", 1.0),
          ("heavy-tailed (lognormal, v=2)", "lognormal", 2.0))


# ---------------------------------------------------------------------------------------- check 2
def check_late(quick=False, log=print):
    """Returns (summary rows, detail rows for the plot)."""
    rows, detail = [], []
    n_jobs = 60_000 if quick else 300_000
    tau = 0.25                                          # time left = deadline 300 ms - about 50 ms of path
    for name, shape, scv in SHAPES:
        for c in (2, 4, 8):
            rng = np.random.default_rng([7, c, int(scv * 100)])
            arr, dep, found = fcfs(rng, LOAD * c * MU, c, MU, shape, scv, n_jobs)
            keep = arr > 50.0
            late = (dep - arr)[keep] > tau
            fnd = found[keep]
            model = late_table(c, MU, tau, shape, scv)
            nmax = min(N_STATES - 1, int(fnd.max()))
            cnt = np.bincount(fnd, minlength=nmax + 1)[:N_STATES]
            sim = np.bincount(fnd, weights=late, minlength=nmax + 1)[:N_STATES] / np.maximum(cnt, 1)
            ok_n = np.flatnonzero(cnt >= 300)
            err = np.abs(sim[ok_n] - model[ok_n])
            w = cnt[ok_n] / cnt[ok_n].sum()
            avg_model = float((w * model[ok_n]).sum())
            avg_sim = float((w * sim[ok_n]).sum())
            for n in ok_n:
                detail.append(dict(shape=name, c=c, n=int(n), frames=int(cnt[n]),
                                   simulated=float(sim[n]), model=float(model[n])))
            exact = shape == "exp"
            tol = 0.03 if exact else 0.10
            ok = err.max() <= tol
            rows.append(dict(check="2. late(n) formula", case=f"{name}, {c} servers",
                             quantity="largest error over n (pts)", model=round(avg_model * 100, 2),
                             simulated=round(avg_sim * 100, 2), ci95=float("nan"),
                             error=round(float(err.max()) * 100, 2),
                             verdict="APPROX" if not exact else ("OK" if ok else "CHECK")))
            log(f"    {name:30s} c={c}: largest |error| {err.max() * 100:5.2f} pts, average late "
                f"model {avg_model * 100:5.2f}% vs simulated {avg_sim * 100:5.2f}%")
    return rows, detail


# ---------------------------------------------------------------------------------------- check 3
def check_ageing(quick=False, log=print):
    rows = []
    c = 4
    lam = LOAD * c * MU
    n_jobs = 60_000 if quick else 250_000
    tau = 0.25
    for name, shape, scv in SHAPES[:2]:
        rng = np.random.default_rng([11, int(scv * 100)])
        arr, dep, _ = fcfs(rng, lam, c, MU, shape, scv, n_jobs)
        dep_sorted = np.sort(dep)
        ager = Ager(c, MU, lam)
        late = late_table(c, MU, tau, shape, scv)

        def n_at(t):
            return np.searchsorted(arr, t, "right") - np.searchsorted(dep_sorted, t, "right")

        for dt in (0.1, 0.5, 2.0):
            g = np.arange(50.0, arr[-1] - dt - 1.0, 0.25)
            q0, q1 = n_at(g), n_at(g + dt)
            q0c = np.minimum(q0, N_STATES - 1)
            pred = {}
            for q in np.unique(q0c):
                pred[q] = ager.age(point(q), dt)
            P = np.array([pred[q] for q in q0c])          # predicted distribution for every snapshot
            emp = np.bincount(np.minimum(q1, N_STATES - 1), minlength=N_STATES) / len(q1)
            tv = 0.5 * np.abs(P.mean(0) - emp).sum()
            risk_pred = float((P @ late).mean())
            risk_true = float(late[np.minimum(q1, N_STATES - 1)].mean())
            exact = shape == "exp"
            ok = tv <= (0.03 if exact else 0.15)
            rows.append(dict(check="3. belief ageing b(n)", case=f"{name}, 4 servers, report {dt:g} s old",
                             quantity="late chance predicted vs seen (%); error = TV distance", model=round(risk_pred * 100, 2),
                             simulated=round(risk_true * 100, 2), ci95=float("nan"), error=round(tv, 3),
                             verdict=("OK" if ok else "CHECK") if exact else "APPROX"))
            log(f"    {name:30s} dt={dt:4.1f} s: TV distance {tv:.3f}; risk predicted {risk_pred * 100:5.2f}% "
                f"vs seen {risk_true * 100:5.2f}%")
    return rows


def run_checks(quick=False, log=print):
    log("  check 1 - simulator vs Erlang C (M/M/c)")
    rows = check_engine(quick, log)
    log("  check 2 - late(n) vs simulation")
    r2, detail = check_late(quick, log)
    log("  check 3 - belief ageing vs simulation")
    rows += r2 + check_ageing(quick, log)
    return rows, detail
