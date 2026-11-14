"""Analysis and report of the v5 study (results_v5/report_v5.html). Every sentence that states a result is
generated from the numbers of the runs on disk."""
import csv
import json
import os

import numpy as np

from . import plots, report
from .analysis import capacity_truth, ci95
from .config import LABELS
from .experiments import run_path
from .v5 import (DESCRIBE_V5, FAMILY, FAMILY_TITLES, GROUP_TITLES, LABELS_V5,
                 PILOT_SEEDS_V5, PILOT_TESTS_V5, PRACTICAL_V5, SHORT_V5, V5_ALL, test_id)

esc, pct, img, ms = report.esc, report.pct, report.img, report.ms
LAB = dict(LABELS, **LABELS_V5)
BASE = "ours_v5"
METERED_V5 = ["ours_v5", "ours_v2_speed", "wrr_speed", "wrr_speed_drop"]
TWINS = [("ours_v5", "ours_v2_speed"), ("wrr_drop", "wrr"), ("wrr_speed_drop", "wrr_speed"), ("v4", "v4_nodrop")]
FAMILIES = ["beirut", "large", "overload"]
PLOTTED = ["ours_v5", "ours_v2_speed", "v4", "wrr_speed_drop", "wrr"]          # coloured in the charts
COLV5 = {"ours_v5": "#eb6834", "ours_v2_speed": "#2a78d6", "v4": "#eda100", "wrr_speed_drop": "#1baf7a",
         "wrr": "#1baf7a", "oracle": "#52514e"}
HOLLOW_V5 = {"wrr_speed_drop"}


# ============================================================================================ capacity bound
def capacity_bound(sc, dt=0.05):
    """The fewest frames ANY rule must miss (%, fluid bound over the counted part of the run): the traffic offered
    above what the working servers can serve at that moment. 0 when there is always enough capacity."""
    T, warm = sc.duration(), sc.warmup_time()
    t = np.arange(warm, T, dt) + dt / 2
    R, S = sc.ingresses, len(sc.servers)
    full = sum(sc.servers) * sc.mu
    if sc.load_profile:
        lam = np.interp(t, [p[0] for p in sc.load_profile], [p[1] for p in sc.load_profile]) * full
    else:
        lam = np.full(len(t), sc.load * full)
        if sc.load_jump_to > 0:
            lam[t >= T / 2] = sc.load_jump_to * full
    if sc.surge:
        shares = np.arange(R, 0, -1, dtype=float) if sc.traffic == "unequal" else np.ones(R)
        shares /= shares.sum()
        k, f, s0, s1 = sc.surge
        lam = lam + np.where((t >= s0) & (t < s1), (f - 1.0) * sc.load * full * shares[k], 0.0)
    servers = np.tile(np.array(sc.servers, float), (len(t), 1))
    speed = np.ones((len(t), S))
    ev = [(T / 2, sc.cap_drop[0], sc.cap_drop[1])] if sc.cap_drop else []
    for te, s, n in sorted(ev + list(sc.cap_events)):
        servers[t >= te, s] = n
    for te, s, f in sorted(sc.speed_events):
        speed[t >= te, s] = f
    cap = (servers * speed).sum(axis=1) * sc.mu
    return 100.0 * float(np.maximum(lam - cap, 0.0).sum() / lam.sum())


# ============================================================================================ the study
class V5Study:
    def __init__(self, steps, run_dir):
        self.tests, self.order, self.runs, self.missing = {}, [], {}, []
        for _, tasks in steps:
            for sc, r, sd in tasks:
                tid = test_id(sc)
                if tid not in self.tests:
                    self.tests[tid] = sc
                    self.order.append(tid)
                p = run_path(run_dir, sc, r, sd)
                if os.path.exists(p):
                    with open(p) as f:
                        o = json.load(f)
                    o.pop("series", None)
                    o.setdefault("late", o["miss"])               # runs of earlier rounds: no drops, no discards
                    o.setdefault("dropped", 0.0)
                    o.setdefault("discarded", 0.0)
                    self.runs[(tid, r, sd)] = o
                else:
                    self.missing.append((tid, r, sd))
        self.seeds = sorted({sd for _, tasks in steps for _, _, sd in tasks})
        self.keys = [k for k in self.order if any((k, r, sd) in self.runs for r in V5_ALL for sd in self.seeds)]
        self.rules = [r for r in V5_ALL if any((k, r, sd) in self.runs for k in self.keys for sd in self.seeds)]
        self.bound = {k: capacity_bound(self.tests[k]) for k in self.keys}
        self._summary()
        self._checks()
        self._meter()

    def family(self, k):
        return FAMILY[self.tests[k].group]

    def label(self, k):
        sc = self.tests[k]
        if sc.group == "main":
            return "Main scenario (Beirut)"
        if sc.group == "L_main":
            return "Main scenario (large network)"
        if sc.group == "L_sweep":
            return "Large: " + sc.label
        if sc.group in ("L_real",):
            return "Large: " + sc.label.split(":")[0]
        return sc.label.replace("Held out - ", "Held out: ")

    def short(self, k):
        sc = self.tests[k]
        if sc.group == "sweep" and sc.factor in report.SHORT_FACTOR:
            a, b = report.SHORT_FACTOR[sc.factor]
            return f"{a}{sc.value}{b}"
        if sc.group == "heldout":
            return "Held out: " + sc.label.replace("Held out - ", "").split(":")[0]
        if sc.group == "real":
            return sc.label.split(":")[0]
        return self.label(k).replace("Large network: ", "Large: ")

    # ------------------------------------------------------------------ numbers
    def _summary(self):
        self.summary = {}
        for k in self.keys:
            for r in self.rules:
                outs = [self.runs[(k, r, sd)] for sd in self.seeds if (k, r, sd) in self.runs]
                if not outs:
                    continue
                m, h = ci95([o["miss"] * 100 for o in outs])
                p99 = [o["p99_ms"] for o in outs if o["p99_ms"] == o["p99_ms"]]
                self.summary[(k, r)] = dict(
                    n=len(outs), miss=m, ci=h,
                    late=float(np.mean([o["late"] for o in outs]) * 100),
                    dropped=float(np.mean([o["dropped"] for o in outs]) * 100),
                    discarded=float(np.mean([o["discarded"] for o in outs]) * 100),
                    runs_dropping=sum(1 for o in outs if o["dropped"] > 0),
                    runs_planning_drops=sum(1 for o in outs if o.get("diag", {}).get("drop_plan")),
                    p99=float(np.mean(p99)) if p99 else float("nan"),
                    mean_ms=float(np.mean([o["mean_ms"] for o in outs if o["mean_ms"] == o["mean_ms"]] or [np.nan])),
                    share=np.mean([o["share"] for o in outs], axis=0).tolist(),
                    kcal=[o["diag"]["kcal"] for o in outs if "kcal" in o.get("diag", {})],
                    runtime=float(sum(o["runtime_s"] for o in outs)))

    def diff(self, k, rule, base=BASE):
        """rule minus base, seed by seed (percentage points): mean, 95% CI half-width, verdict, n."""
        common = [sd for sd in self.seeds if (k, rule, sd) in self.runs and (k, base, sd) in self.runs]
        if len(common) < 2:
            return None
        d = [100 * (self.runs[(k, rule, sd)]["miss"] - self.runs[(k, base, sd)]["miss"]) for sd in common]
        m, h = ci95(d)
        if h != h:
            v = "n/a"
        elif m - h > 0:
            v = "base better"
        elif m + h < 0:
            v = "base worse"
        else:
            v = "no clear difference"
        return dict(diff=m, ci=h, verdict=v, n=len(common))

    def tally(self, base, rule, family):
        t = {"better": 0, "same": 0, "worse": 0}
        for k in self.keys:
            if self.family(k) != family:
                continue
            d = self.diff(k, rule, base)
            if not d or d["verdict"] == "n/a":
                continue
            t[{"base better": "better", "base worse": "worse"}.get(d["verdict"], "same")] += 1
        return t

    def best(self, k):
        rows = [(r, self.summary[(k, r)]["miss"]) for r in PRACTICAL_V5 if (k, r) in self.summary]
        return min(rows, key=lambda x: x[1]) if rows else (None, float("nan"))

    def tied_with_best(self, k):
        b, _ = self.best(k)
        if b is None:
            return []
        out = [b]
        for r in PRACTICAL_V5:
            if r != b and (k, r) in self.summary:
                d = self.diff(k, r, base=b)
                if d and d["verdict"] != "base better":
                    out.append(r)
        return out

    # ------------------------------------------------------------------ consistency checks on the runs
    def _checks(self):
        """(1) late + dropped + discarded = missed, in every run; (2) the same frames for every rule (paired);
        (3) a rule that dropped nothing in a run (ours v5: planned no drop) behaves exactly like its twin that never
        drops."""
        self.check_rows = []
        bad = sum(1 for o in self.runs.values() if abs(o["late"] + o["dropped"] + o["discarded"] - o["miss"]) > 1e-9)
        self.check_rows.append(("Late + dropped + discarded = missed, in every run", f"{len(self.runs) - bad} of "
                                f"{len(self.runs)} runs", bad == 0))
        unpaired = 0
        for k in self.keys:
            for sd in self.seeds:
                fr = {self.runs[(k, r, sd)]["frames"] for r in self.rules if (k, r, sd) in self.runs}
                unpaired += len(fr) > 1
        self.paired_ok = unpaired == 0
        self.check_rows.append(("Every rule saw the same frames (paired design)",
                                "all tests and seeds" if self.paired_ok else f"{unpaired} test-seeds differ",
                                self.paired_ok))
        for a, b in TWINS:
            n = same = 0
            for (k, r, sd), o in self.runs.items():
                if r != a or o["dropped"] > 0 or (k, b, sd) not in self.runs:
                    continue
                if a == "ours_v5" and o.get("diag", {}).get("drop_plan"):
                    continue                                       # it planned a drop share at some point
                t = self.runs[(k, b, sd)]
                n += 1
                same += (o["miss"] == t["miss"] and o["share"] == t["share"] and o["p99_ms"] == t["p99_ms"])
            if n:
                what = "planned no drop" if a == "ours_v5" else "dropped nothing"
                self.check_rows.append((f"{LAB[a]} {what}: identical to {LAB[b]} (same seed)",
                                        f"{same} of {n} runs", same == n))

    # ------------------------------------------------------------------ the speed meter
    def _meter(self):
        self.meter = {}
        for k in self.keys:
            truth = capacity_truth(self.tests[k])
            for r in METERED_V5:
                logs = [self.runs[(k, r, sd)].get("diag", {}).get("speed_changes", [])
                        for sd in self.seeds if (k, r, sd) in self.runs]
                if not logs:
                    continue
                row = dict(runs=len(logs), runs_changed=sum(1 for x in logs if x), truth=truth)
                if truth:
                    s, t0, _ = truth
                    first = [min((c[0] for c in x if c[1] == s and c[0] >= t0), default=None) for x in logs]
                    got = [f - t0 for f in first if f is not None]
                    row["detected"] = len(got)
                    row["delay"] = float(np.median(got)) if got else float("nan")
                self.meter[(k, r)] = row


# ============================================================================================ text
def _tally_text(st, family, rules):
    bits = []
    for r in rules:
        t = st.tally(BASE, r, family)
        if sum(t.values()):
            bits.append(f"{esc(SHORT_V5[r])} {t['better']} / {t['same']} / {t['worse']}")
    return "; ".join(bits)


def headline(st):
    S, out = st.summary, []
    for fam in FAMILIES:
        keys = [k for k in st.keys if st.family(k) == fam]
        if not keys or not any((k, BASE) in S for k in keys):
            continue
        others = [r for r in st.rules if r != BASE]
        tt = _tally_text(st, fam, others)
        if tt:
            out.append(f"<b>{esc(FAMILY_TITLES[fam])}</b>, ours v5 against each rule (tests where v5 is clearly lower "
                       f"/ no clear difference / clearly higher, paired 95% CI): {tt}.")
        else:
            out.append(f"<b>{esc(FAMILY_TITLES[fam])}</b>: paired comparisons need at least 2 seeds.")
        wins = {}
        for k in keys:
            b, _ = st.best(k)
            wins[b] = wins.get(b, 0) + 1
        tied = sum(1 for k in keys if BASE in st.tied_with_best(k))
        out.append("Lowest practical rule per test: " + ", ".join(
            f"{esc(SHORT_V5[r])} {n}" for r, n in sorted(wins.items(), key=lambda x: -x[1])) +
            f". Ours v5 is lowest or not clearly different from the lowest in {tied} of {len(keys)}.")
    for k, name in (("main", "Beirut main scenario"), ("L:main", "Large-network main scenario")):
        if (k, BASE) in S:
            s = S[(k, BASE)]
            line = f"<b>{name}:</b> ours v5 {pct(s['miss'], s['ci'])}"
            for r in ("ours_v2_speed", "wrr", "v4"):
                if (k, r) in S:
                    line += f"; {esc(SHORT_V5[r])} {pct(S[(k, r)]['miss'], S[(k, r)]['ci'])}"
            out.append(line + ".")
    nd = [k for k in st.keys if st.family(k) != "overload" and (k, BASE) in S]
    if nd:
        dropping = [k for k in nd if S[(k, BASE)]["runs_dropping"] > 0]
        n_runs = sum(S[(k, BASE)]["n"] for k in nd)
        planned = sum(S[(k, BASE)]["runs_planning_drops"] for k in nd)
        out.append(f"<b>Below capacity</b> (the {len(nd)} tests of the two networks), ours v5 dropped frames in "
                   f"{len(dropping)} test(s)" + (": " + ", ".join(
                       f"{esc(st.short(k))} ({S[(k, BASE)]['dropped']:.2f}% of frames)" for k in dropping)
                       if dropping else "") + f". It planned a drop at some point in {planned} of its {n_runs} runs; "
                   "in the others it sent every frame exactly where v2 + speeds would (check in section 7).")
    ov = [k for k in st.keys if st.family(k) == "overload" and (k, BASE) in S]
    if ov:
        gaps = [S[(k, BASE)]["miss"] - st.bound[k] for k in ov]
        out.append(f"<b>Overload:</b> ours v5 missed on average {np.mean([S[(k, BASE)]['miss'] for k in ov]):.1f}% "
                   f"of frames, {np.mean(gaps):.1f} points above the capacity bound (the fewest any rule must miss). "
                   "Without dropping, v2 + speeds missed " +
                   f"{np.mean([S[(k, 'ours_v2_speed')]['miss'] for k in ov if (k, 'ours_v2_speed') in S]):.1f}%.")
    return out


# ============================================================================================ tables
def tally_table(st):
    others = [r for r in st.rules if r != BASE]
    fams = [f for f in FAMILIES if any(st.family(k) == f for k in st.keys)]
    h = ['<div class="tw"><table><tr><th class="l" rowspan="2">Ours v5 compared with</th>' +
         "".join(f'<th colspan="3">{esc(FAMILY_TITLES[f])}</th>' for f in fams) + "</tr><tr>" +
         "".join("<th>v5 lower</th><th>no clear diff.</th><th>v5 higher</th>" for _ in fams) + "</tr>"]
    for r in others:
        cells = []
        for f in fams:
            t = st.tally(BASE, r, f)
            cells.append(f'<td class="good">{t["better"]}</td><td>{t["same"]}</td><td class="bad">{t["worse"]}</td>'
                         if sum(t.values()) else "<td></td><td>-</td><td></td>")
        h.append(f'<tr><td class="l">{esc(LAB[r])}</td>{"".join(cells)}</tr>')
    h.append("</table></div><p class='muted'>Counts of tests (paired 95% CI over the seeds). Expected delay + drop "
             "and v4 without dropping run only in the overload tests and the two main scenarios.</p>")
    return "".join(h)


def matrix(st):
    rules = [r for r in V5_ALL if r in st.rules]
    h = ['<div class="tw"><table class="matrix"><tr><th class="l">Test</th>' +
         "".join(f'<th class="{"oursh" if r == BASE else ""}">{esc(SHORT_V5[r])}</th>' for r in rules) +
         "<th>Capacity bound</th></tr>"]
    group = None
    for k in st.keys:
        g = st.tests[k].group
        if g != group:
            group = g
            h.append(f'<tr><td class="l" colspan="{len(rules) + 2}"><b>{esc(GROUP_TITLES[g])}</b></td></tr>')
        best = st.best(k)[0]
        h.append(f'<tr><td class="l lab">{esc(st.short(k))}</td>')
        for r in rules:
            s = st.summary.get((k, r))
            if not s:
                h.append("<td>-</td>")
                continue
            bg, fg = report.cell_color(s["miss"])
            v = f"{s['miss']:.1f}" if s["miss"] >= 1 else f"{s['miss']:.2f}"
            tip = f"{LAB[r]}: {s['miss']:.2f}% missed (late {s['late']:.2f}, dropped {s['dropped']:.2f}, " \
                  f"discarded {s['discarded']:.2f})"
            if r == best:
                v = "&#9733;&nbsp;" + v
            h.append(f'<td class="{"best" if r == best else ""}" style="background:{bg};color:{fg}" '
                     f'title="{esc(tip)}">{v}</td>')
        b = st.bound[k]
        h.append(f"<td>{b:.1f}</td>" if b >= 0.05 else "<td>0</td>")
        h.append("</tr>")
    h.append("</table></div>")
    return "".join(h)


def overload_table(st):
    keys = [k for k in st.keys if st.family(k) == "overload"]
    rules = [r for r in V5_ALL if r in st.rules and r != "oracle"]
    if not keys:
        return ""
    h = ['<div class="tw"><table><tr><th class="l">Test</th><th>Capacity bound</th>' +
         "".join(f"<th>{esc(SHORT_V5[r])}</th>" for r in rules) + "</tr>"]
    for k in keys:
        h.append(f'<tr><td class="l" style="min-width:170px">{esc(st.short(k))}</td><td>{st.bound[k]:.1f}%</td>')
        best = st.best(k)[0]
        for r in rules:
            s = st.summary.get((k, r))
            if not s:
                h.append("<td>-</td>")
                continue
            h.append(f'<td class="{"best" if r == best else ""}">{s["miss"]:.1f}%<br><small>{s["late"]:.1f} / '
                     f'{s["dropped"]:.1f} / {s["discarded"]:.1f}</small></td>')
        h.append("</tr>")
    h.append("</table></div><p class='muted'>Each cell: missed (%), and below it late / dropped at the ingress / "
             "discarded by the site because its deadline had passed (they add up to missed). Capacity bound = the traffic offered above what the working servers can serve: "
             "no rule can miss fewer.</p>")
    return "".join(h)


def versus_table(st):
    cols = [r for r in ("ours_v2_speed", "wrr_speed_drop", "wrr_drop", "v4", "wrr") if r in st.rules]
    h = ['<div class="tw"><table><tr><th class="l">Test</th><th>Ours v5</th><th>v5 dropped</th>' +
         "".join(f"<th>{esc(SHORT_V5[r])} minus v5 (pts)</th>" for r in cols) + "</tr>"]
    for k in st.keys:
        s = st.summary.get((k, BASE))
        if not s:
            continue
        h.append(f'<tr><td class="l">{esc(st.short(k))}</td><td>{pct(s["miss"], s["ci"])}</td>'
                 f'<td>{s["dropped"]:.2f}%</td>')
        for r in cols:
            d = st.diff(k, r)
            if not d:
                h.append("<td>-</td>")
                continue
            cls = {"base better": "good", "base worse": "bad"}.get(d["verdict"], "neutral")
            h.append(f'<td class="{cls}">{d["diff"]:+.2f} <small>&plusmn;{d["ci"]:.2f}</small></td>')
        h.append("</tr>")
    h.append("</table></div><p class='muted'>Positive (green) = that rule missed more than ours v5, clearly (paired "
             "95% CI); red = it missed clearly fewer; grey = no clear difference.</p>")
    return "".join(h)


def meter_table(st):
    rules = [r for r in METERED_V5 if any(rr == r for _, rr in st.meter)]
    if not rules:
        return ""
    h = ['<div class="tw"><table class="wrap"><tr><th class="l">Tests</th>' +
         "".join(f"<th>{esc(SHORT_V5[r])}</th>" for r in rules) + "</tr>"]
    calm = [k for k in st.keys if not any(st.meter.get((k, r), {}).get("truth") for r in rules)]
    h.append(f'<tr><td class="l">{len(calm)} tests where every site works as configured: runs where the meter '
             'changed its estimate (false changes)</td>')
    for r in rules:
        ms_ = [st.meter[(k, r)] for k in calm if (k, r) in st.meter]
        h.append(f"<td>{sum(m['runs_changed'] for m in ms_)} of {sum(m['runs'] for m in ms_)}</td>")
    h.append("</tr>")
    for k in [k for k in st.keys if k not in calm]:
        h.append(f'<tr><td class="l">{esc(st.short(k))}: reacted to the real change (median delay)</td>')
        for r in rules:
            m = st.meter.get((k, r))
            if not m:
                h.append("<td>-</td>")
                continue
            dl = m.get("delay", float("nan"))
            h.append(f"<td>{m.get('detected', 0)} of {m['runs']}" + (f" ({dl:.0f} s)" if dl == dl else "") + "</td>")
        h.append("</tr>")
    h.append("</table></div><p class='muted'>What the meter of ingress A measured. In the overload tests the meter "
             "also reads the discard count of the report (frames that left unserved).</p>")
    return "".join(h)


def checks_table(st, extra):
    rows = list(extra) + st.check_rows
    h = ['<div class="tw"><table class="wrap"><tr><th class="l">Check</th><th class="l">Result</th>'
         '<th class="l">Verdict</th></tr>']
    for what, res, ok in rows:
        v = "OK" if ok is True else ("-" if ok is None else "CHECK")
        cls = "good" if ok is True else ("neutral" if ok is None else "bad")
        h.append(f'<tr><td class="l">{esc(what)}</td><td class="l">{esc(res)}</td>'
                 f'<td class="l"><span class="{cls}">{v}</span></td></tr>')
    h.append("</table></div>")
    return "".join(h)


def rules_table(st):
    h = ['<div class="tw"><table class="wrap"><tr><th class="l">Rule</th><th class="l">How it picks a site '
         '(and when it drops)</th></tr>']
    for r in st.rules:
        h.append(f'<tr class="{"ours" if r == BASE else ""}"><td class="l">{esc(LAB[r])}</td>'
                 f'<td class="l">{esc(DESCRIBE_V5[r])}</td></tr>')
    h.append("</table></div>")
    return "".join(h)


def _pilot_table(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    tests = list(dict.fromkeys(r["test"] for r in rows))
    rules = list(dict.fromkeys(x["rule"] for x in rows))
    val = {(x["test"], x["rule"]): x for x in rows}
    h = ['<div class="tw"><table><tr><th class="l">Test (spare seeds)</th>' +
         "".join(f"<th>{esc(SHORT_V5.get(r, r))}</th>" for r in rules) + "</tr>"]
    for t in tests:
        h.append(f'<tr><td class="l">{esc(t)}</td>')
        for r in rules:
            x = val.get((t, r))
            h.append(f"<td>{float(x['miss_pct']):.2f}%<br><small>dropped {float(x['dropped_pct']):.2f}</small></td>"
                     if x else "<td>-</td>")
        h.append("</tr>")
    h.append("</table></div>")
    return "".join(h)


def pilot_section(out):
    d = os.path.join(out, "pilot")
    final, first = os.path.join(d, "pilot_v5.csv"), os.path.join(d, "pilot_v5_pass1.csv")
    if not os.path.exists(final):
        return ("<p>No pilot table found in <code>results_v5/pilot/</code>. (The pilot runs on spare seeds "
                f"{PILOT_SEEDS_V5[0]}-{PILOT_SEEDS_V5[-1]} with <code>python run_v5.py --pilot</code>.)</p>")
    h = []
    if os.path.exists(first):
        h.append("<h3>Pass 1: ours v5 with and without calibration</h3><p>The decision rule written before the pilot "
                 "kept the calibrated version (the version without calibration was lower in 1 test and higher in 6). "
                 "But the calibrated v5 was clearly worse than v2 + speeds in two tests below capacity (main and "
                 "wrong weights), so, as the rule required, we looked into it: v5 also dropped below capacity, and "
                 "with wrong weights its drops kept the DC's queue short, so the speed meter never saw that the DC "
                 "had only 6 servers. Change: v5 may drop only in overload (offered traffic above 95% of the measured "
                 "capacity), as v4 never drops below capacity.</p>" + _pilot_table(first))
        h.append("<h3>Pass 2 (final): with the overload-only drop</h3>")
    return "".join(h) + _pilot_table(final)


# ============================================================================================ charts
def _dots(st, keys, path, title, xlabel):
    P = plots
    lo = max(0.2, min([st.summary[(k, r)]["miss"] for k in keys for r in PLOTTED + ["oracle"]
                       if (k, r) in st.summary and st.summary[(k, r)]["miss"] > 0] or [1]) * 0.7)
    fig, ax = P.plt.subplots(figsize=(9.6, 0.62 * len(keys) + 1.6))
    others = [r for r in PRACTICAL_V5 if r not in PLOTTED]
    for y, k in enumerate(keys):
        for r in others:
            s = st.summary.get((k, r))
            if s:
                ax.plot(max(s["miss"], lo), y, "|", ms=9, color=P.OTHER, mew=1.2, zorder=1)
        b = st.bound[k]
        if b >= 0.05:
            ax.plot(max(b, lo), y, "|", ms=15, color=P.INK, mew=2.0, zorder=2)
    for i, r in enumerate(PLOTTED):
        off = (i - (len(PLOTTED) - 1) / 2) * 0.12
        xs = [max(st.summary[(k, r)]["miss"], lo) if (k, r) in st.summary else np.nan for k in keys]
        c = COLV5[r]
        hollow = r in HOLLOW_V5
        ax.plot(xs, np.arange(len(keys)) + off, "o", ms=7.5 if r == BASE else 6.5, color=c,
                mfc=P.SURFACE if hollow else c, mec=c if hollow else P.SURFACE, mew=1.6 if hollow else 1.2,
                zorder=4 if r == BASE else 3, label=SHORT_V5[r])
    for y in range(len(keys)):
        ax.axhline(y + 0.5, color=P.GRID, lw=0.8)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels([st.short(k) for k in keys])
    ax.set_ylim(len(keys) - 0.5, -0.5)
    P._logy(ax, lo, 100, axis="x")
    ax.set_xlabel(xlabel)
    ax.set_title(title, pad=44)
    ax.plot([], [], "|", ms=9, color=P.OTHER, mew=1.2, label="other rules")
    ax.plot([], [], "|", ms=12, color=P.INK, mew=2.0, label="capacity bound")
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=4, borderaxespad=0.3, fontsize=8.5)
    return P._save(fig, path)


def chart_overload(st, path):
    keys = [k for k in st.keys if st.family(k) == "overload"]
    return _dots(st, keys, path, "Overload tests: frames that missed the deadline (lower is better)",
                 "missed = late + dropped + discarded (log scale); black tick = the fewest any rule must miss")


def chart_mains(st, path):
    keys = [k for k in ("main", "L:main") if (k, BASE) in st.summary] + \
           [k for k in st.keys if st.tests[k].group in ("real", "heldout", "L_real")]
    return _dots(st, keys, path, "Main scenarios, failures and real-life events (below capacity)",
                 "frames that missed the 300 ms deadline (log scale)")


def chart_vs_v2(st, path, rival="ours_v2_speed"):
    P = plots
    keys = [k for k in st.keys if st.diff(k, rival)]
    if not keys:
        return None
    fig, ax = P.plt.subplots(figsize=(8.8, 0.24 * len(keys) + 1.5))
    span = 1.0
    for y, k in enumerate(keys):
        d = st.diff(k, rival)
        c = P.GOOD if d["verdict"] == "base better" else (P.BAD if d["verdict"] == "base worse" else P.MUTED)
        if d["ci"] == d["ci"] and d["ci"] > 0:
            ax.plot([d["diff"] - d["ci"], d["diff"] + d["ci"]], [y, y], color=c, lw=1.6, alpha=0.7)
        ax.plot(d["diff"], y, "o", ms=5.5, color=c, mec=P.SURFACE, mew=1.2, zorder=3)
        span = max(span, abs(d["diff"]) + (d["ci"] if d["ci"] == d["ci"] else 0))
    ax.axvline(0, color=P.AXIS, lw=1)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels([st.short(k) for k in keys], fontsize=7.5)
    ax.set_ylim(len(keys) - 0.5, -0.5)
    ax.set_xscale("symlog", linthresh=1.0)
    ax.set_xlim(-span * 1.3 - 0.5, span * 1.3 + 0.5)
    ax.xaxis.set_major_formatter(P.FuncFormatter(lambda v, _: f"{v:+g}" if v else "0"))
    ax.grid(axis="x", color=P.GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel(f"{SHORT_V5[rival]} minus ours v5, percentage points (same frames, seed by seed)\n"
                  "right of 0 = v5 misses fewer    left of 0 = v5 misses more    line = 95% CI")
    ax.set_title(f"Every test: ours v5 against {SHORT_V5[rival]}")
    ax.plot([], [], "o", color=P.GOOD, label="v5 clearly lower")
    ax.plot([], [], "o", color=P.MUTED, label="no clear difference")
    ax.plot([], [], "o", color=P.BAD, label="v5 clearly higher")
    ax.legend(loc="upper left")
    return P._save(fig, path)


# ============================================================================================ files
def write_csv(st, out):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "summary_v5.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["test", "test_label", "group", "rule", "rule_label", "seeds", "miss_pct", "miss_ci95", "late_pct",
                    "dropped_pct", "discarded_pct", "mean_ms_answered", "p99_ms_answered", "capacity_bound_pct",
                    "minus_ours_v5_pts", "ci95", "verdict"])
        for k in st.keys:
            for r in st.rules:
                s = st.summary.get((k, r))
                if not s:
                    continue
                d = st.diff(k, r) if r != BASE else None
                w.writerow([k, st.label(k), st.tests[k].group, r, LAB[r], s["n"], round(s["miss"], 3),
                            round(s["ci"], 3), round(s["late"], 3), round(s["dropped"], 3), round(s["discarded"], 3),
                            round(s["mean_ms"], 1), round(s["p99"], 1), round(st.bound[k], 3)] +
                           ([round(d["diff"], 3), round(d["ci"], 3), d["verdict"]] if d else ["", "", ""]))
    with open(os.path.join(out, "ours_v5_vs_each_rule.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tests", "rule", "rule_label", "v5_lower", "no_clear_difference", "v5_higher"])
        for fam in FAMILIES:
            for r in st.rules:
                if r == BASE:
                    continue
                t = st.tally(BASE, r, fam)
                if sum(t.values()):
                    w.writerow([fam, r, LAB[r], t["better"], t["same"], t["worse"]])


# ============================================================================================ page
def build(steps, run_dir, out, meta, extra_checks=()):
    st = V5Study(steps, run_dir)
    write_csv(st, os.path.join(out, "tables_v5"))
    cdir = os.path.join(out, "charts_v5")
    os.makedirs(cdir, exist_ok=True)
    charts = {}
    for name, fn, fname in [("overload", chart_overload, "1_overload.png"), ("mains", chart_mains, "2_mains.png"),
                            ("vs_v2", chart_vs_v2, "3_v5_vs_v2_speeds.png")]:
        try:
            charts[name] = fn(st, os.path.join(cdir, fname))
        except Exception as e:                            # keep the report going
            plots.plt.close("all")
            print(f"    (chart '{name}' skipped: {type(e).__name__}: {e})")
    kc = [x for k in st.keys for x in st.summary.get((k, BASE), {}).get("kcal", [])]
    P = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>CATS v5 study</title>
<style>{report.CSS}</style></head><body><main>
<h1>CATS site selection: ours v5</h1>
<p class="sub">Packet Patrol &middot; CMPS 342 &middot; {len(st.keys)} tests &middot; {meta['seeds']} seed(s) per test
&middot; {len(st.runs):,} simulation runs &middot; started {esc(meta['started'])}</p>"""]
    if st.missing:
        P.append(f'<div class="card"><b>Incomplete:</b> {len(st.missing)} planned runs are missing. Run the same '
                 'command again to finish them.</div>')
    if not st.paired_ok:
        P.append('<div class="card"><b>Warning:</b> some rules saw a different number of frames for the same test and '
                 'seed; the paired comparison is not valid.</div>')
    P.append("""<div class="card key"><b>What ours v5 is</b><ul>
<li>Ours v2 + measured speeds (the final rule of round 3), plus <b>dropping</b> as one more option in the plan.</li>
<li>Each 1% of the traffic goes where it adds the fewest expected late frames: its own chance of being late, plus the
harm to the other frames, plus the backlog it leaves behind.</li>
<li>Dropping a frame costs exactly one miss. So a frame is dropped only when every site would cost more than that,
and only in overload: when the offered traffic is above 95% of the measured capacity (like v4, it never drops below
capacity).</li>
<li>The send-or-drop comparison uses the risk scaled to reality (late / predicted, from the ingress's own answers).</li>
<li>While it drops nothing, v5 sends every frame exactly where v2 + speeds would.</li>
<li>From v4 (teammate): the idea of dropping, counting the frames it dropped when it measures the traffic, and never
using a site that would be late even when empty.</li></ul></div>""")
    P.append("<h2>Main results</h2><ul>" + "".join(f"<li>{x}</li>" for x in headline(st)) + "</ul>")
    P.append("<h2>1. Ours v5 against each rule</h2>" + tally_table(st) + img(charts.get("vs_v2")))
    P.append("<h2>2. Overload tests</h2><p>More traffic than the sites can serve, all the time or for a while. The "
             "sites discard a frame whose deadline has passed (for every rule), except in the last test.</p>" +
             img(charts.get("overload")) + overload_table(st))
    P.append("<h2>3. Below capacity: main scenarios, failures and real-life events</h2>" + img(charts.get("mains")))
    P.append("<h2>4. Every test at a glance</h2><p>Missed deadline (%), average of the seeds. &#9733; = lowest "
             "practical rule in that row (the oracle is a reference, not a competitor).</p>" + matrix(st))
    P.append("<h2>5. Ours v5 minus each close rival, test by test</h2>" + versus_table(st))
    if st.meter:
        P.append("<h2>6. The speed meter</h2>" + meter_table(st))
    P.append("<h2>7. Checks</h2>" + checks_table(st, extra_checks))
    P.append("<h2>8. The rules</h2>" + rules_table(st))
    P.append(f"""<h2>9. Pilot (spare seeds, not part of the results above)</h2>{pilot_section(out)}""")
    cpu = sum(o.get("runtime_s", 0) for o in st.runs.values())
    P.append(f"""<h2>10. Method notes and disclosures</h2><ul>
<li><b>Dropping is an assumption.</b> A dropped frame is never sent and counts as a miss. For live camera frames a late
answer is useless, so not sending a frame that would be late is reasonable; a CATS deployment must allow it.</li>
<li><b>Deadline-aware sites, only in the overload tests:</b> a site discards a frame whose deadline has passed when its
turn comes (or when the site counts its frames for a report), for every rule, as in v4's own test (and as inference
servers with a queue timeout do). The discard count travels in the same 4-byte counter (2 bytes arrivals, 2 bytes
discards), so the telemetry budget is unchanged. The 48 tests below capacity keep the physics of round 3 exactly.</li>
<li><b>Fair rivals:</b> round-robin and round-robin + measured speeds also get a drop version, with the same estimate
of the offered traffic as ours v5, so v5 cannot win just by dropping.</li>
<li><b>v4 was ported from its report's description</b>, not from its code; where the description is silent we made the
choices listed in section 8. Expected delay + drop is the rival that did best against v4 in v4's own report.</li>
<li><b>Oracle:</b> a reference below capacity only. An "oracle + drop" (drop when even the best site is late with
chance &gt; 1/2) was planned, but testing the code showed it misses far more than simple rules in overload, so it
was removed before any run of the study; the capacity bound is the overload reference instead.</li>
<li><b>Found while testing the code (seed 999, never used in the study):</b> v5's first plan dropped 26% of the frames
in the main scenario, because it had no answers to calibrate with yet. Fix: no dropping until 100 answers to planned
frames have come back (until then v5 is exactly v2 + speeds).</li>
<li><b>Out-of-sample:</b> the pilot used only {', '.join(PILOT_TESTS_V5)} on spare seeds, and its decision rule
(which version of v5 to keep) was written before the pilot ran (<code>catsim/v5.py</code>). The large network (all 14 of
its tests), the held-out scenarios and 9 of the 11 Beirut overload tests were never used to design or tune v5.</li>
<li>Ours v5 calibration factor at the end of the runs (ingress A, late / predicted): median
{(f"{np.median(kc):.2f}" if kc else "-")} (the model's raw risk is too high by about 1/factor).</li>
<li>Times (mean, slowest 1%) are over the frames that got an answer.</li></ul>
<h2>11. Files</h2><ul><li>Tables: <code>tables_v5/summary_v5.csv</code>, <code>tables_v5/ours_v5_vs_each_rule.csv</code>
</li><li>Charts: <code>charts_v5/</code></li><li>Every run: <code>runs/</code></li>
<li>{len(st.runs):,} runs, {cpu / 3600:.2f} CPU-hours; Python {esc(meta['python'])}</li></ul></main></body></html>""")
    path = os.path.join(out, "report_v5.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(P))
    return path, st
