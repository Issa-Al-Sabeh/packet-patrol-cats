"""From saved runs to tables: averages with 95% confidence intervals, paired comparisons with our rule,
ablation effects, and calibration of the predicted risk.

Paired comparison: for the same scenario and seed, every rule saw exactly the same frames, job sizes,
delays and report losses. So we compare rule minus ours seed by seed, and give a 95% confidence
interval for the average difference (Student t). "Ours better" = the whole interval says the other
rule misses more; "ours worse" = the whole interval says it misses less; otherwise "no clear difference".
"""
import json
import math
import os
import warnings

import numpy as np
from scipy import stats

from .config import (ABLATIONS, LABELS, OURS_FAMILY, RULES, SITE_NAMES, build_held_out, build_real_life,
                     build_scenarios)
from .engine import CALIB_EDGES
from .experiments import run_path

PRACTICAL = [r for r in RULES if r != "oracle"]
PREDICTORS = ["ours", "ours_v2", "ours_v2_check", "ours_v2_speed", "expected_delay", "dahlin", "liyanage"] + ABLATIONS
METERED = ["ours_v2_speed", "wrr_speed"]          # rules with a speed meter (their runs log what it measured)


def capacity_truth(sc):
    """What really happens to the sites' servers in a scenario: (site, first change time s, [(t, servers), ...])
    in whole-server equivalents (servers x speed), or None if every site always matches what the rules are told."""
    told = sc.servers_known or sc.servers
    T = sc.duration()
    if sc.servers_known and tuple(sc.servers_known) != tuple(sc.servers):
        s = next(i for i, (a, b) in enumerate(zip(sc.servers, sc.servers_known)) if a != b)
        return s, 0.0, [(0.0, float(sc.servers[s])), (T, float(sc.servers[s]))]
    ev = []
    if sc.cap_drop:
        ev.append((T / 2, sc.cap_drop[0], float(sc.cap_drop[1])))
    ev += [(t, s, float(n)) for t, s, n in sc.cap_events]
    ev += [(t, s, sc.servers[s] * f) for t, s, f in sc.speed_events]
    if not ev:
        return None
    ev.sort()
    s = ev[0][1]
    steps = [(0.0, float(told[s]))] + [(t, v) for t, ss, v in ev if ss == s] + [(T, None)]
    out = []
    for (t, v), (t2, _) in zip(steps, steps[1:]):
        out.append((t, v))
    out.append((T, out[-1][1]))
    return s, ev[0][0], out


def ci95(x):
    x = np.asarray(x, float)
    n = len(x)
    if n == 0:
        return float("nan"), float("nan")
    if n == 1:
        return float(x[0]), float("nan")
    return float(x.mean()), float(stats.t.ppf(0.975, n - 1) * x.std(ddof=1) / math.sqrt(n))


def wilson(k, n):
    if n == 0:
        return float("nan"), float("nan")
    z = 1.96
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, mid - half), min(1.0, mid + half)


class Study:
    """Everything the report needs, computed once."""

    def __init__(self, steps, run_dir):
        self.main, self.sweeps, self.stress = build_scenarios()
        self.real = build_real_life(self.main)
        self.heldout = build_held_out(self.main)
        self.runs = {}
        self.missing = []
        self.seeds = sorted({sd for _, tasks in steps for _, _, sd in tasks})
        for _, tasks in steps:
            for sc, r, sd in tasks:
                p = run_path(run_dir, sc, r, sd)
                if os.path.exists(p):
                    with open(p) as f:
                        self.runs[(sc.key, r, sd)] = json.load(f)
                else:
                    self.missing.append((sc.key, r, sd))
        # scenario list in report order (each key once)
        self.scen = {}
        order = [self.main]
        for _, (_, _, pts) in self.sweeps.items():
            order += pts
        order += self.stress + self.real + self.heldout
        for sc in order:
            if sc.key not in self.scen:
                self.scen[sc.key] = sc
        self.keys = [k for k in self.scen if any((k, r, sd) in self.runs for r in RULES for sd in self.seeds)]
        self.rules = [r for r in RULES + ABLATIONS if any((k, r, sd) in self.runs for k in self.keys for sd in self.seeds)]
        self._summary()
        self._paired()
        self._calibration()
        self._speed_meter()

    # ------------------------------------------------------------------ helpers
    def values(self, key, rule, field="miss", scale=100.0):
        return [self.runs[(key, rule, sd)][field] * scale for sd in self.seeds if (key, rule, sd) in self.runs]

    def label(self, key):
        sc = self.scen[key]
        if key == "main":
            return "Main scenario (Beirut)"
        return sc.label

    # ------------------------------------------------------------------ averages
    def _summary(self):
        warnings.filterwarnings("ignore", message="Mean of empty slice")
        self.summary = {}
        for k in self.keys:
            for r in self.rules:
                outs = [self.runs[(k, r, sd)] for sd in self.seeds if (k, r, sd) in self.runs]
                if not outs:
                    continue
                m, h = ci95([o["miss"] * 100 for o in outs])
                self.summary[(k, r)] = dict(
                    seeds=len(outs), miss=m, miss_ci=h,
                    mean_ms=float(np.mean([o["mean_ms"] for o in outs])),
                    p99_ms=float(np.mean([o["p99_ms"] for o in outs])),
                    swing=float(np.mean([o["swing"] for o in outs])),
                    bytes=float(np.mean([o["bytes_per_s"] for o in outs])),
                    share=np.mean([o["share"] for o in outs], axis=0).tolist(),
                    miss_by_site=np.nanmean([o.get("miss_by_site", [np.nan] * 3) for o in outs], axis=0).tolist(),
                    frames=int(np.mean([o["frames"] for o in outs])),
                    runtime=float(np.sum([o["runtime_s"] for o in outs])))
        # paired design check: same frames for every rule (same scenario, same seed)
        self.paired_ok = True
        for k in self.keys:
            for sd in self.seeds:
                fr = {self.runs[(k, r, sd)]["frames"] for r in self.rules if (k, r, sd) in self.runs}
                if len(fr) > 1:
                    self.paired_ok = False

    # ------------------------------------------------------------------ paired with ours
    def diff(self, key, rule, base="ours"):
        """rule minus base, seed by seed (percentage points): mean, 95% CI half-width, verdict, n."""
        common = [sd for sd in self.seeds if (key, rule, sd) in self.runs and (key, base, sd) in self.runs]
        if len(common) < 2:
            return None
        d = [100 * (self.runs[(key, rule, sd)]["miss"] - self.runs[(key, base, sd)]["miss"]) for sd in common]
        m, h = ci95(d)
        if np.isnan(h):
            v = "n/a"
        elif m - h > 0:
            v = "ours better" if base == "ours" else "base better"
        elif m + h < 0:
            v = "ours worse" if base == "ours" else "base worse"
        else:
            v = "no clear difference"
        return dict(diff=m, ci=h, verdict=v, n=len(common))

    def _paired(self):
        self.paired = {}
        for k in self.keys:
            for r in self.rules:
                if r == "ours":
                    continue
                d = self.diff(k, r)
                if d:
                    self.paired[(k, r)] = d
        self.tally = {}
        for r in self.rules:
            if r == "ours" or r in ABLATIONS:
                continue
            t = {"ours better": 0, "no clear difference": 0, "ours worse": 0}
            for k in self.keys:
                d = self.paired.get((k, r))
                if d and d["verdict"] in t:
                    t[d["verdict"]] += 1
            self.tally[r] = t
        # the same count for every version of ours: base better / no clear difference / base worse
        self.tallies = {}
        for base in OURS_FAMILY:
            if base not in self.rules:
                continue
            T = {}
            for r in self.rules:
                if r == base or r in ABLATIONS:
                    continue
                t = {"better": 0, "same": 0, "worse": 0}
                for k in self.keys:
                    d = self.diff(k, r, base=base)
                    if not d or d["verdict"] == "n/a":
                        continue
                    if d["verdict"] in ("ours better", "base better"):
                        t["better"] += 1
                    elif d["verdict"] in ("ours worse", "base worse"):
                        t["worse"] += 1
                    else:
                        t["same"] += 1
                T[r] = t
            self.tallies[base] = T

    def room_to_win(self, key):
        """Round-robin's miss rate minus the oracle's (percentage points): how much any report-based rule could win."""
        a, b = self.summary.get((key, "wrr")), self.summary.get((key, "oracle"))
        return a["miss"] - b["miss"] if a and b else float("nan")

    def ranking(self, key, rules=None):
        rules = rules or PRACTICAL
        rows = [(r, self.summary[(key, r)]["miss"]) for r in rules if (key, r) in self.summary]
        return sorted(rows, key=lambda x: x[1])

    def best_practical(self, key):
        rk = self.ranking(key)
        return rk[0] if rk else (None, float("nan"))

    def tied_with_best(self, key):
        """Practical rules whose paired difference with the best practical rule is not clearly positive."""
        best, _ = self.best_practical(key)
        if best is None:
            return []
        out = [best]
        for r, _ in self.ranking(key)[1:]:
            d = self.diff(key, r, base=best)
            if d and d["verdict"] != "base better":        # not clearly worse than the best rule
                out.append(r)
        return out

    # ------------------------------------------------------------------ calibration
    def _calibration(self):
        self.calib = {}
        nb = len(CALIB_EDGES) - 1
        for k in self.keys:
            for r in self.rules:
                if r not in PREDICTORS:
                    continue
                n = np.zeros(nb)
                ps = np.zeros(nb)
                lt = np.zeros(nb)
                got = False
                for sd in self.seeds:
                    o = self.runs.get((k, r, sd))
                    if o and "calib" in o:
                        got = True
                        n += o["calib"]["n"]
                        ps += o["calib"]["pred_sum"]
                        lt += o["calib"]["late"]
                if not got:
                    continue
                rows = []
                for b in range(nb):
                    if n[b] < 1:
                        continue
                    lo, hi = wilson(lt[b], n[b])
                    rows.append(dict(bin_lo=float(CALIB_EDGES[b]), bin_hi=float(min(CALIB_EDGES[b + 1], 1.0)),
                                     frames=int(n[b]), predicted=float(ps[b] / n[b]), actual=float(lt[b] / n[b]),
                                     actual_lo=lo, actual_hi=hi))
                tot = n.sum()
                self.calib[(k, r)] = dict(rows=rows, mean_pred=float(ps.sum() / tot) if tot else float("nan"),
                                          mean_actual=float(lt.sum() / tot) if tot else float("nan"))

    # ------------------------------------------------------------------ the speed meter
    def _speed_meter(self):
        """What the speed meter of ingress A measured, per test and metered rule:
        runs with any change, changes per run, and (when a site really changed) when the meter first reacted."""
        self.meter = {}
        for k in self.keys:
            truth = capacity_truth(self.scen[k])
            for r in METERED:
                logs = [self.runs[(k, r, sd)].get("diag", {}).get("speed_changes", [])
                        for sd in self.seeds if (k, r, sd) in self.runs]
                if not logs:
                    continue
                row = dict(runs=len(logs), runs_changed=sum(1 for x in logs if x),
                           changes=float(np.mean([len(x) for x in logs])), truth=truth)
                if truth:
                    s, t0, _ = truth
                    first = [min((c[0] for c in x if c[1] == s and c[0] >= t0), default=None) for x in logs]
                    got = [f - t0 for f in first if f is not None]
                    row["detected"] = len(got)
                    row["delay_median"] = float(np.median(got)) if got else float("nan")
                    row["other_site_changes"] = int(sum(1 for x in logs for c in x if c[1] != s))
                self.meter[(k, r)] = row

    def meter_logs(self, key, rule):
        return {sd: self.runs[(key, rule, sd)].get("diag", {}).get("speed_changes", [])
                for sd in self.seeds if (key, rule, sd) in self.runs}

    # ------------------------------------------------------------------ CSV tables
    def write_csv(self, out):
        import csv
        def w(name, header, rows):
            with open(os.path.join(out, name), "w", newline="", encoding="utf-8") as f:
                cw = csv.writer(f)
                cw.writerow(header)
                cw.writerows(rows)

        def r3(x):
            return "" if x is None or (isinstance(x, float) and math.isnan(x)) else round(x, 3)

        rows = []
        for k in self.keys:
            sc = self.scen[k]
            for r in self.rules:
                s = self.summary.get((k, r))
                if not s:
                    continue
                d = self.paired.get((k, r))
                rows.append([k, self.label(k), sc.group, r, LABELS[r], s["seeds"], r3(s["miss"]), r3(s["miss_ci"]),
                             r3(s["mean_ms"]), r3(s["p99_ms"]), r3(s["swing"]), r3(s["bytes"])] +
                            [r3(x) for x in s["share"]] +
                            ([r3(d["diff"]), r3(d["ci"]), d["verdict"]] if d else ["", "", ""]))
        w("summary.csv", ["scenario", "scenario_label", "group", "rule", "rule_label", "seeds", "miss_pct",
                          "miss_ci95", "mean_ms", "p99_ms", "load_swing", "bytes_per_s"] +
          [f"share_{n.split()[0].lower()}" for n in SITE_NAMES] +
          ["minus_ours_pts", "minus_ours_ci95", "verdict"], rows)
        rows = []
        for (k, r), c in self.calib.items():
            for b in c["rows"]:
                rows.append([k, r, b["bin_lo"], b["bin_hi"], b["frames"], r3(100 * b["predicted"]),
                             r3(100 * b["actual"]), r3(100 * b["actual_lo"]), r3(100 * b["actual_hi"])])
        w("calibration.csv", ["scenario", "rule", "predicted_from", "predicted_to", "frames", "mean_predicted_pct",
                              "actual_late_pct", "actual_ci_low", "actual_ci_high"], rows)
        rows = []
        for base, T in self.tallies.items():
            for r, t in T.items():
                rows.append([base, LABELS[base], r, LABELS[r], t["better"], t["same"], t["worse"]])
        w("ours_vs_each_rule.csv", ["ours_version", "ours_label", "rule", "rule_label", "tests_ours_better",
                                    "no_clear_difference", "tests_ours_worse"], rows)
        rows = [[k, self.label(k), r3(self.room_to_win(k))] for k in self.keys]
        w("room_to_win.csv", ["scenario", "scenario_label", "wrr_minus_oracle_pts"], rows)
        rows = []
        for (k, r), m in self.meter.items():
            t = m["truth"]
            rows.append([k, self.label(k), r, LABELS[r], m["runs"], m["runs_changed"], r3(m["changes"]),
                         SITE_NAMES[t[0]] if t else "", r3(t[1]) if t else "", m.get("detected", ""),
                         r3(m.get("delay_median", float("nan"))), m.get("other_site_changes", "")])
        w("speed_meter.csv", ["scenario", "scenario_label", "rule", "rule_label", "runs", "runs_with_a_change",
                              "changes_per_run", "site_that_really_changed", "first_change_s",
                              "runs_where_meter_reacted", "median_delay_s", "changes_at_other_sites"], rows)
