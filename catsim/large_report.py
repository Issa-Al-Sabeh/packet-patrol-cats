"""Report of the large-network study (results_large/report_large.html): the same tables and charts as the main
report, for 6 sites and 12 ingresses. Every sentence that states a result is generated from the numbers."""
import csv
import json
import math
import os

import numpy as np

from . import analysis, plots, report
from .analysis import METERED, PRACTICAL, Study, ci95
from .config import LABELS
from .experiments import run_path
from .large import LARGE_MAIN, LARGE_RULES, LARGE_SITE_NAMES, build_large

esc, pct, img, ms = report.esc, report.pct, report.img, report.ms


class LargeStudy(Study):
    """Study for the large network (same analysis as the main study, other scenarios)."""

    def __init__(self, steps, run_dir):
        self.main, sweep_pts, self.events = build_large()
        self.sweeps = {"large": ("Report interval and load", True, sweep_pts)}
        self.stress, self.real, self.heldout = [], self.events, []
        self.runs, self.missing = {}, []
        self.seeds = sorted({sd for _, tasks in steps for _, _, sd in tasks})
        for _, tasks in steps:
            for sc, r, sd in tasks:
                p = run_path(run_dir, sc, r, sd)
                if os.path.exists(p):
                    with open(p) as f:
                        self.runs[(sc.key, r, sd)] = json.load(f)
                else:
                    self.missing.append((sc.key, r, sd))
        self.scen = {sc.key: sc for sc in [self.main] + sweep_pts + self.events}
        self.keys = [k for k in self.scen if any((k, r, sd) in self.runs for r in LARGE_RULES for sd in self.seeds)]
        self.rules = [r for r in LARGE_RULES if any((k, r, sd) in self.runs for k in self.keys for sd in self.seeds)]
        self._summary()
        self._paired()
        self._calibration()
        self._speed_meter()

    def label(self, key):
        return "Main scenario (large network)" if key == "main" else self.scen[key].label


def site_table(st, key="main"):
    rows = [r for r in PRACTICAL + ["oracle"] if (key, r) in st.summary]
    rows.sort(key=lambda r: st.summary[(key, r)]["miss"])
    h = ['<div class="tw"><table><tr><th class="l">Rule</th>' +
         "".join(f"<th>{esc(n)}</th>" for n in LARGE_SITE_NAMES) + "</tr>"]
    for r in rows:
        s = st.summary[(key, r)]
        h.append(f'<tr><td class="l">{esc(LABELS[r])}</td>' + "".join(
            f"<td>{100 * sh:.1f}%<br><small>{'late ' + format(100 * mm, '.1f') + '%' if mm == mm else '-'}</small></td>"
            for sh, mm in zip(s["share"], s["miss_by_site"])) + "</tr>")
    cap = np.array(LARGE_MAIN.servers) / sum(LARGE_MAIN.servers)
    h.append('<tr><td class="l"><small>Share of capacity</small></td>' +
             "".join(f"<td><small>{100 * c:.1f}%</small></td>" for c in cap) + "</tr></table></div>")
    return "".join(h)


def headline(st):
    S, out = st.summary, []
    base = "ours_v2_speed"
    if ("main", base) in S:
        rk = st.ranking("main")
        best, bm = rk[0]
        s = (f"<b>Main scenario (6 sites, 12 ingresses, 85% load, reports every 5 s):</b> {esc(LABELS[base])} "
             f"{pct(S[('main', base)]['miss'], S[('main', base)]['miss_ci'])}; lowest practical rule "
             f"{esc(LABELS[best])} {pct(bm, S[('main', best)]['miss_ci'])}")
        if ("main", "oracle") in S:
            s += f"; oracle (impossible in practice) {pct(S[('main', 'oracle')]['miss'])}"
        out.append(s + ".")
        tied = st.tied_with_best("main")
        if len(tied) > 1:
            out.append("Not clearly different from the lowest practical rule (paired 95% CI): " +
                       esc(report.names(tied)) + ".")
    T = st.tallies.get(base, {})
    bits = [f"vs {esc(LABELS[r])}: lower in {T[r]['better']}, higher in {T[r]['worse']}, no clear difference in "
            f"{T[r]['same']}" for r in LARGE_RULES if r in T and r != base]
    if bits:
        out.append(f"<b>{esc(LABELS[base])} across all {len(st.keys)} tests</b> (paired): " + "; ".join(bits) + ".")
    winners = {}
    for k in st.keys:
        b, _ = st.best_practical(k)
        winners[b] = winners.get(b, 0) + 1
    out.append("Lowest practical rule per test (count of tests): " + ", ".join(
        f"{esc(LABELS[r])} {n}" for r, n in sorted(winners.items(), key=lambda x: -x[1])) + ".")
    m = report.meter_summary(st, base)
    if m:
        out.append(f"<b>Measured speeds ({esc(LABELS[base])}, ingress A):</b> " + m)
    return out


def write_csv(st, out):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "summary_large.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "scenario_label", "rule", "rule_label", "seeds", "miss_pct", "miss_ci95", "mean_ms",
                    "p99_ms", "bytes_per_s"] + [f"share_{n}" for n in LARGE_SITE_NAMES] +
                   ["minus_ours_v2_speed_pts", "ci95", "verdict"])
        for k in st.keys:
            for r in st.rules:
                s = st.summary.get((k, r))
                if not s:
                    continue
                d = st.diff(k, r, base="ours_v2_speed") if r != "ours_v2_speed" else None
                w.writerow([k, st.label(k), r, LABELS[r], s["seeds"], round(s["miss"], 3), round(s["miss_ci"], 3),
                            round(s["mean_ms"], 1), round(s["p99_ms"], 1), round(s["bytes"], 1)] +
                           [round(x, 4) for x in s["share"]] +
                           ([round(d["diff"], 3), round(d["ci"], 3), d["verdict"]] if d else ["", "", ""]))


def build(steps, run_dir, out, meta):
    # the shared report and chart code names the 3 sites of the main study: use the 6 sites here
    report.SITE_NAMES = plots.SITE_NAMES = analysis.SITE_NAMES = LARGE_SITE_NAMES
    st = LargeStudy(steps, run_dir)
    write_csv(st, os.path.join(out, "tables_large"))
    cdir = os.path.join(out, "charts_large")
    os.makedirs(cdir, exist_ok=True)
    charts = {}
    for name, fn, fname in [
            ("main", plots.main_dots, "1_main.png"),
            ("paired", lambda s_, p_: plots.paired_forest(s_, p_, base="ours_v2_speed"), "2_paired_v2_speeds.png"),
            ("sweep", lambda s_, p_: plots.stress(s_, p_, scs=s_.sweeps["large"][2],
                                                  title="Report interval and load (large network)"), "3_sweeps.png"),
            ("events", lambda s_, p_: plots.stress(s_, p_, scs=s_.events, title="Failures and real-life events "
                                                   "(large network)"), "4_events.png"),
            ("speeds", plots.speed_tracking, "5_measured_speeds.png")]:
        try:
            charts[name] = fn(st, os.path.join(cdir, fname))
        except Exception as e:                        # keep the report going
            plots.plt.close("all")
            print(f"    (chart '{name}' skipped: {type(e).__name__}: {e})")
    m = LARGE_MAIN
    sites = ", ".join(f"{n} ({c} servers, {d:g} ms)" for n, c, d in zip(LARGE_SITE_NAMES, m.servers, m.base_delay_ms))
    P = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>CATS Large Network</title>
<style>{report.CSS}</style></head><body><main>
<h1>CATS site selection: the large network</h1>
<p class="sub">Packet Patrol &middot; CMPS 342 &middot; 6 sites, 12 ingresses &middot; {meta['seeds']} seed(s) per test
&middot; {len(st.runs):,} simulation runs &middot; started {esc(meta['started'])}</p>"""]
    if st.missing:
        P.append(f'<div class="card"><b>Incomplete:</b> {len(st.missing)} planned runs are missing. Run the same '
                 f'command again to finish them.</div>')
    if not st.paired_ok:
        P.append('<div class="card"><b>Warning:</b> some rules saw a different number of frames for the same test and '
                 'seed; the paired comparison is not valid.</div>')
    P.append("""<div class="card key"><b>What this is</b><ul>
<li>The same study as the main report, on a bigger network, to check that its results hold at a larger scale.</li>
<li>Every rule is used <b>exactly as frozen in round 3</b>: same code, same settings. Nothing here was used to design
or tune a rule, so all of these tests are out-of-sample.</li>
<li>Missed deadline = share of frames late (lower is better); &plusmn; = 95% confidence interval over the seeds;
paired = same frames for every rule, compared seed by seed.</li></ul></div>""")
    P.append("<h2>Main results</h2><ul>" + "".join(f"<li>{x}</li>" for x in headline(st)) + "</ul>")
    P.append(f"""<h2>1. Main scenario</h2><ul>
<li>6 sites: {esc(sites)} round trip from Ingress A; the other 11 ingresses are up to {m.delay_spread:.0%} nearer or
farther (different ingresses are close to different sites).</li>
<li>30 servers in total; each finishes {m.mu:g} frames/s (100 ms average, Gamma, variability {m.job_scv:g}).</li>
<li>{m.ingresses} ingresses send {m.load:.0%} of total capacity, unequal shares (12 : 11 : ... : 1).
Deadline {m.deadline_ms:g} ms. Reports every {m.report_interval:g} s (frames + 4-byte counter).</li>
<li>Each run: {m.duration():g} s of traffic, the first {m.warmup_time():g} s not counted.</li></ul>""")
    P.append(img(charts.get("main")) + report.main_table(st) + img(charts.get("paired")))
    P.append("<h3>Where the frames go (main scenario)</h3>" + site_table(st))
    P.append("<h2>2. All tests at a glance</h2><p>Missed deadline (%), average of the seeds. &#9733; = lowest practical "
             "rule in that row.</p>" + report.matrix(st, "miss") +
             "<h3>The slowest 1% of frames (seconds)</h3>" + report.matrix(st, "p99") +
             "<h3>Each version of ours against each rule (paired 95% CI)</h3>" + report.tally_table(st))
    P.append("<h2>3. Report interval and load</h2>" + img(charts.get("sweep")) +
             report.scenario_table(st, st.sweeps["large"][2]))
    P.append("<h2>4. Failures and real-life events</h2><p>None of these events is announced to the rules. Each keeps "
             "the total load during the event near 90% of what really works.</p>" + img(charts.get("events")) +
             report.scenario_table(st, st.events))
    if st.meter:
        P.append("<h2>5. What the measured speeds saw</h2>" + img(charts.get("speeds")) + report.meter_table(st))
    P.append("""<h2>6. Method notes</h2><ul>
<li>Same simulator, rules and analysis as the main study (see its report). Only the network differs.</li>
<li>Rules included: the four versions of ours, round-robin and its measured-speeds control, LSQ-style, CATS timeout +
SED, Prequal-style, Liyanage-style, capacity-weighted random and the oracle. Power of two, weighted power of two,
Dahlin-style, nearest site and expected delay are left out: they were far behind in every test of the main study.</li>
<li>The oracle sees true queues, servers and GPU speed, but not lost reports' effects on the others.</li>
<li>Not modelled: failures of ingresses, batching on the GPUs, a site that stops completely.</li></ul>""")
    cpu = sum(o.get("runtime_s", 0) for o in st.runs.values())
    P.append(f"<h2>7. Files</h2><ul><li>Tables: <code>tables_large/summary_large.csv</code></li>"
             f"<li>Charts: <code>charts_large/</code></li><li>Every run: <code>runs_large/</code></li>"
             f"<li>{len(st.runs):,} runs, {cpu / 3600:.2f} CPU-hours; Python {esc(meta['python'])}</li></ul>"
             "</main></body></html>")
    path = os.path.join(out, "report_large.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(P))
    return path
