"""The final result: one self-contained HTML page (results/report.html) with every chart and table,
plus CSV files. All sentences that state a result are generated from the numbers of this run."""
import base64
import html
import json
import math
import os

import numpy as np

from .analysis import PRACTICAL, Study
from .config import ABLATIONS, GROUPS, LABELS, MAIN, OURS_FAMILY, PILOT_SEEDS, SITE_NAMES
from . import plots

DESCRIBE = {
    "ours": "Version 1. Ages the last report into a range of possible queue sizes (counting the other ingresses "
            "with the 4-byte counter) and sends each frame to the site with the lowest chance of missing the "
            "deadline; near-ties are split at random by spare capacity.",
    "ours_v2": "Version 2. At each round of reports it chooses a SPLIT of all the traffic for the next interval "
               "(same belief ageing and late(n) as v1) that gives the fewest expected late frames, then sends by "
               "taking turns with those shares. Every ingress computes the same split, so no copycat guess is "
               "needed. No site is planned above 95% of its capacity. Without new reports the split slides back "
               "to 2 : 4 : 8.",
    "ours_v2_check": "Version 2 plus a self-check: each ingress compares the risk it predicted with how many of its "
                     "own frames were actually late (from the answers) and scales each site's risk by that ratio.",
    "ours_v2_speed": "Version 2 plus measured speeds. From the reports it already gets, each ingress measures how "
                     "many servers each site really has (frames served = arrivals counter minus the change in the "
                     "queue, counted only after the queue stayed long for 5 s) and uses that in the whole model; if "
                     "the measured speeds cannot carry the traffic, the slowed site gets back just enough capacity. "
                     "The plan also counts the backlog it leaves behind. A slowed site gets a server back as soon as "
                     "it serves more than measured, or after a quiet spell (20 s, doubled after a wrong return). "
                     "No new report fields.",
    "wrr_speed": "Control for ours v2 + measured speeds: weighted round-robin whose weights are the same measured "
                 "speeds (same meter, same top-up). Uses the reports; identical to weighted round-robin until its "
                 "meter measures a change.",
    "expected_delay": "Exactly the same belief as ours v1, but picks the site with the lowest expected (average) "
                      "delay. Isolates the effect of scoring by risk.",
    "dahlin": "Ages the last report as ONE number (arrivals minus departures, from the counter), +1 per own frame, "
              "and picks the lowest late(n) for that number. Deterministic (Dahlin's paper adds a random split).",
    "liyanage": "No reports. Each camera (about 10 frames/s) measures the delay of its own frames; a site is "
                "acceptable if P(late) is at most 15% (Normal and Cantelli); lowest mean + 1.645 x spread; "
                "switches only when a site is 5% better for 5 decisions in a row.",
    "lsq": "Last report plus this ingress's own frames sent since (no ageing), per server; picks the lowest.",
    "timeout_sed": "CATS-draft style: trusts the last report for up to 3 intervals and picks the lowest "
                   "(frames + 1) / capacity + path delay.",
    "power_of_two": "Picks two sites at random and takes the one with fewer frames in the last report.",
    "wpow2_stale": "Picks two sites in proportion to capacity and takes the one with fewer frames per server in "
                   "the last report.",
    "prequal": "No reports. Spends the same bytes per second on probes to random sites; each answer is used at "
               "most twice; without a usable answer it picks at random by capacity.",
    "nearest": "Always the closest site.",
    "cap_random": "A random site, in proportion to capacity (2 : 4 : 8).",
    "wrr": "Takes turns in proportion to capacity (2 : 4 : 8). Needs no reports.",
    "oracle": "Sees the true number of frames, working servers and their speed at every site right now "
              "(impossible in practice) and picks the lowest risk. A reference, not a competitor; it decides one "
              "frame at a time, so it is not a guaranteed lower bound.",
    "ours_no_counting": "Ours v1, but the other ingresses are ignored (no counter).",
    "ours_no_ageing": "Ours v1, but the report is used as if it were still fresh (no ageing).",
    "ours_exp_late": "Ours v1, but late(n) assumes exponential job sizes.",
    "ours_no_ties": "Ours v1, but always the single lowest risk (no random choice among near-ties).",
}
GROUP_OF = {r: g for g, rs in GROUPS.items() for r in rs}
GROUP_NAMES = {"main": "Main", "sweep": "Sweeps (one factor changed)", "stress": "Stress tests",
               "real": "Real-life scenarios", "heldout": "Held-out scenarios (never used to design or tune a rule)"}
VS = {"ours": ["wrr", "lsq", "expected_delay"], "ours_v2": ["wrr", "lsq", "ours"],
      "ours_v2_check": ["wrr", "lsq", "ours_v2"], "ours_v2_speed": ["wrr", "wrr_speed", "ours_v2"]}

CSS = """
:root{--bg:#f9f9f7;--card:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--line:#e1e0d9;--accent:#2a78d6;
--good:#006300;--bad:#b8452e;--chip:#f0efec}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0d0d0d;--card:#1a1a19;--ink:#f0efec;
--ink2:#c3c2b7;--muted:#898781;--line:#2c2c2a;--accent:#3987e5;--good:#0ca30c;--bad:#e66767;--chip:#262624;
color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0d0d0d;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--line:#2c2c2a;
--accent:#3987e5;--good:#0ca30c;--bad:#e66767;--chip:#262624;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1120px;margin:0 auto;padding-block:28px 64px;padding-left:max(16px,env(safe-area-inset-left,0px));
padding-right:max(16px,env(safe-area-inset-right,0px))}
h1{font-size:28px;line-height:1.2;margin:0 0 6px;text-wrap:balance}
h2{font-size:20px;margin:40px 0 10px;padding-top:12px;border-top:1px solid var(--line);text-wrap:balance}
h3{font-size:16px;margin:22px 0 8px}
p,li{color:var(--ink)} .sub{color:var(--ink2);margin:0 0 18px}
.muted{color:var(--muted)} small{color:var(--ink2)}
ul{padding-left:20px;margin:6px 0 12px} li{margin:3px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}
.key{border-left:4px solid var(--accent)}
.fig{background:#fcfcfb;border:1px solid var(--line);border-radius:10px;padding:10px;margin:12px 0}
.fig img{width:100%;height:auto;display:block}
.tw{overflow-x:auto;margin:10px 0}
table{border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums;width:100%}
th,td{padding:5px 8px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top}
th{color:var(--ink2);font-weight:600;background:var(--card);position:sticky;top:0}
td.l,th.l{text-align:left}
tr.ours td{font-weight:600}
.good{color:var(--good);font-weight:600}.bad{color:var(--bad);font-weight:600}.neutral{color:var(--ink2)}
table.matrix{font-size:11px} table.matrix td{text-align:center;padding:3px 3px;border:1px solid var(--card)}
table.matrix th{font-size:10px;font-weight:600;text-align:center;vertical-align:bottom;padding:4px 2px}
table.matrix th.l,table.matrix td.l{text-align:left}
table.matrix td.lab{min-width:118px;max-width:170px}
td{white-space:nowrap} td.l{white-space:normal}
table.abl td,table.wrap td{white-space:normal} table.abl td.l{min-width:170px}
td.best{font-weight:700}
th.oursh{box-shadow:inset 0 -3px 0 var(--accent)}
code{background:var(--chip);padding:1px 5px;border-radius:4px;font-size:13px}
"""

RAMP = ["#e8f1fc", "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
        "#256abf", "#1c5cab", "#184f95", "#104281"]


def esc(x):
    return html.escape(str(x))


def pct(m, h=None, nd=2):
    if m is None or (isinstance(m, float) and math.isnan(m)):
        return "-"
    s = f"{m:.{nd}f}%"
    if h is not None and not (isinstance(h, float) and math.isnan(h)):
        s += f" <small>&plusmn;{h:.{nd}f}</small>"
    return s


def img(path):
    if not path or not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        b = base64.b64encode(f.read()).decode()
    return f'<div class="fig"><img alt="{esc(os.path.basename(path))}" src="data:image/png;base64,{b}"></div>'


def verdict_html(v):
    cls = {"ours better": "good", "ours worse": "bad"}.get(v, "neutral")
    return f'<span class="{cls}">{esc(v.replace("ours", "ours v1"))}</span>'


def cell_color(v, lo=0.3, hi=100.0):
    if v is None or math.isnan(v):
        return "transparent", "inherit"
    x = (math.log10(max(v, lo)) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
    i = int(round(min(max(x, 0), 1) * (len(RAMP) - 1)))
    return RAMP[i], ("#ffffff" if i >= 7 else "#0b0b0b")


def names(rules):
    return ", ".join(LABELS[r] for r in rules)


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def word(verdict):
    if verdict in ("ours better", "base better"):
        return "lower"
    if verdict in ("ours worse", "base worse"):
        return "higher"
    return "no clear difference"


SHORT_FACTOR = {"report_interval": ("Reports every ", " s"), "load": ("Load ", "%"), "deadline": ("Deadline ", " ms"),
                "job_shape": ("Jobs: ", ""), "ingresses": ("", " ingresses"), "traffic": ("Traffic ", ""),
                "sites": ("Sites ", ""), "report_timing": ("Reports ", "")}


def short_label(st, key):
    sc = st.scen[key]
    if sc.group == "sweep" and sc.factor in SHORT_FACTOR:
        a, b = SHORT_FACTOR[sc.factor]
        return f"{a}{sc.value}{b}"
    if sc.group in ("real", "heldout"):
        return sc.label.replace("Held out - ", "").split(":")[0]
    return st.label(key)


def ms(v):
    return f"{v / 1000:,.0f} s" if v >= 10000 else f"{v:,.0f} ms"


def secs(v):
    """p99 in a matrix cell: 0.35 / 4.2 / 46 (seconds)."""
    s = v / 1000
    return f"{s:.2f}" if s < 1 else (f"{s:.1f}" if s < 10 else f"{s:,.0f}")


# ====================================================================================== text
def headline(st, checks):
    """Bullets that state the main results, generated from the numbers."""
    out = []
    S = st.summary
    fam = [r for r in OURS_FAMILY if ("main", r) in S]
    if fam:
        rk = st.ranking("main")
        order = [r for r, _ in rk]
        best, bm = rk[0]
        def rank(r):                                   # equal averages share a rank
            return 1 + sum(1 for _, m in rk if m < S[("main", r)]["miss"] - 1e-9)
        parts = [f"{esc(LABELS[r])} {pct(S[('main', r)]['miss'], S[('main', r)]['miss_ci'])} "
                 f"(rank {rank(r)} of {len(rk)})" for r in fam]
        s = (f"<b>Main scenario (Beirut, reports every {MAIN.report_interval:g} s, {MAIN.load:.0%} load), frames late:"
             f"</b> " + "; ".join(parts) + ".")
        if best not in fam:
            s += f" Lowest practical rule: {esc(LABELS[best])}, {pct(S[('main', best)]['miss'], S[('main', best)]['miss_ci'])}."
        if ("main", "oracle") in S:
            s += f" Oracle (impossible in practice): {pct(S[('main', 'oracle')]['miss'])}."
        out.append(s)
        tied = st.tied_with_best("main")
        if len(tied) > 1:
            out.append("Not clearly different from the lowest practical rule in the main scenario (paired 95% CI): "
                       + esc(names(tied)) + ".")
    if len(st.keys) > 1:
        for base in fam:
            T = st.tallies.get(base, {})
            bits = []
            for r in VS.get(base, ["wrr", "lsq"]):
                t = T.get(r)
                if t:
                    bits.append(f"vs {esc(LABELS[r])}: lower in {plural(t['better'], 'test')}, higher in "
                                f"{t['worse']}, no clear difference in {t['same']}")
            if bits:
                out.append(f"<b>{esc(LABELS[base])} across all {len(st.keys)} tests</b> (paired): "
                           + "; ".join(bits) + ".")
        winners = {}
        for k in st.keys:
            b, _ = st.best_practical(k)
            winners[b] = winners.get(b, 0) + 1
        wtxt = ", ".join(f"{esc(LABELS[r])} {n}" for r, n in sorted(winners.items(), key=lambda x: -x[1]))
        out.append(f"Lowest practical rule per test (count of tests): {wtxt}.")
        for scs, name in ((st.real, "Real-life scenarios"), (st.heldout, "Held-out scenarios")):
            rl = [sc.key for sc in scs if sc.key in st.keys]
            if rl:
                bits = []
                for k in rl:
                    b, bm = st.best_practical(k)
                    tied = [r for r in st.tied_with_best(k) if r != b and r in fam]
                    extra = f"; not clearly different: {esc(names(tied))}" if tied else ""
                    bits.append(f"{esc(short_label(st, k))}: {esc(LABELS[b])} ({bm:.2f}%{extra})")
                out.append(f"<b>{name}, lowest practical rule:</b> " + "; ".join(bits) + ".")
        for base in [r for r in ("ours", "ours_v2", "ours_v2_speed") if r in fam]:
            bits = []
            for sc in st.sweeps["report_interval"][2]:
                d = st.diff(sc.key, "wrr", base=base)
                if d:
                    bits.append(f"{esc(sc.value)} s: {word(d['verdict'])} ({-d['diff']:+.2f} pts)")
            if bits:
                out.append(f"<b>{esc(LABELS[base])} vs weighted round-robin as reports get fresher</b> (its miss rate "
                           f"minus round-robin's, paired): " + "; ".join(bits) + ".")
    if ("main", "ours_no_counting") in S and ("main", "ours") in S:
        parts = []
        for a in ABLATIONS:
            d = st.paired.get(("main", a))
            if d:
                parts.append(f"{esc(LABELS[a].replace('Ours v1 ', ''))}: {S[('main', a)]['miss']:.2f}% "
                             f"({d['diff']:+.2f} pts, {d['verdict'].replace('ours', 'full rule')})")
        out.append("<b>Ablations of ours v1 (main scenario; full rule "
                   f"{S[('main', 'ours')]['miss']:.2f}%):</b> " + "; ".join(parts) + ".")
    cal = []
    for sc in st.sweeps["report_interval"][2]:
        c = st.calib.get((sc.key, "ours"))
        if c:
            cal.append(f"{esc(sc.value)} s: predicted {100 * c['mean_pred']:.2f}%, actual {100 * c['mean_actual']:.2f}%")
    if cal:
        s = ("<b>Is the predicted risk right?</b> Ours v1, average predicted risk of the chosen site vs the share of "
             "frames actually late: " + "; ".join(cal) + ".")
        more = []
        for r in ("ours_v2", "ours_v2_check", "ours_v2_speed"):
            c = st.calib.get(("main", r))
            if c:
                more.append(f"{esc(LABELS[r])} {100 * c['mean_pred']:.2f}% predicted vs {100 * c['mean_actual']:.2f}% late")
        if more:
            s += " Main scenario: " + "; ".join(more) + "."
        out.append(s)
    m = meter_summary(st, "ours_v2_speed")
    if m:
        out.append("<b>Measured speeds (" + esc(LABELS["ours_v2_speed"]) + ", what ingress A measured):</b> " + m)
    if checks:
        c1 = [r for r in checks if r["check"].startswith("1.")]
        c2 = [r for r in checks if r["check"].startswith("2.")]
        c3 = [r for r in checks if r["check"].startswith("3.")]
        bits = []
        if c1:
            ok = sum(r["verdict"] == "OK" for r in c1)
            bits.append(f"simulator vs Erlang C formulas: {ok} of {len(c1)} OK")
        if c2:
            def mx(sub):
                v = [r["error"] for r in c2 if sub in r["case"]]
                return max(v) if v else float("nan")
            bits.append(f"late(n) largest error: exponential jobs {mx('exponential'):.1f} pts (exact formula), "
                        f"regular jobs {mx('regular'):.1f} pts, heavy-tailed {mx('heavy'):.1f} pts (approximations)")
        if c3:
            ex = [r for r in c3 if "exponential" in r["case"]]
            rg = [r for r in c3 if "regular" in r["case"]]
            if ex and rg:
                bits.append(f"belief ageing: exponential jobs TV distance at most {max(r['error'] for r in ex):.3f} "
                            f"(exact); regular jobs up to {max(r['error'] for r in rg):.3f}, predicted risk "
                            f"{rg[-1]['model']:.1f}% vs seen {rg[-1]['simulated']:.1f}% for a "
                            f"{rg[-1]['case'].split('report ')[-1]} report")
        out.append("<b>Built-in checks:</b> " + "; ".join(bits) + ".")
    return out


def meter_summary(st, rule):
    """One sentence on what the speed meter did: false changes where nothing changed, reaction where it did."""
    rows = {k: m for (k, r), m in st.meter.items() if r == rule}
    if not rows:
        return ""
    calm = [m for m in rows.values() if not m["truth"]]
    bits = []
    if calm:
        bits.append(f"in the {len(calm)} tests where every site works as configured it changed its estimate in "
                    f"{sum(m['runs_changed'] for m in calm)} of {sum(m['runs'] for m in calm)} runs")
    for k, m in rows.items():
        if m["truth"]:
            dl = m.get("delay_median", float("nan"))
            bits.append(f"{esc(short_label(st, k))}: reacted in {m.get('detected', 0)} of {m['runs']} runs"
                        + (f", median {dl:.0f} s after the change" if dl == dl else ""))
    return "; ".join(bits) + "."


def meter_table(st):
    from .analysis import METERED
    rules = [r for r in METERED if any(rr == r for _, rr in st.meter)]
    if not rules:
        return ""
    h = ['<div class="tw"><table class="wrap"><tr><th class="l" rowspan="2">Test</th>'
         '<th class="l" rowspan="2">What really changed</th>' +
         "".join(f'<th colspan="3">{esc(LABELS[r])}</th>' for r in rules) + "</tr><tr>" +
         "".join("<th>Runs with a change</th><th>Changes per run</th><th>Reacted to the real change "
                 "(median delay)</th>" for _ in rules) + "</tr>"]
    calm = [k for k in st.keys if not any(st.meter.get((k, r), {}).get("truth") for r in rules)]
    for k in [k for k in st.keys if k not in calm]:
        t = next(st.meter[(k, r)]["truth"] for r in rules if (k, r) in st.meter)
        s, t0, steps = t
        sc = st.scen[k]
        if sc.servers_known and tuple(sc.servers_known) != tuple(sc.servers):
            what = f"{SITE_NAMES[s]}: told {sc.servers_known[s]} servers, really {sc.servers[s]} (all the time)"
        else:
            what = (f"{SITE_NAMES[s]}: " + " &rarr; ".join(f"{v:g}" for _, v in steps[:-1]) +
                    f" servers (first change at {t0:g} s)")
        h.append(f'<tr><td class="l">{esc(short_label(st, k))}</td><td class="l"><small>{what}</small></td>')
        for r in rules:
            m = st.meter.get((k, r))
            if not m:
                h.append("<td>-</td><td>-</td><td>-</td>")
                continue
            dl = m.get("delay_median", float("nan"))
            h.append(f"<td>{m['runs_changed']} of {m['runs']}</td><td>{m['changes']:.1f}</td>"
                     f"<td>{m.get('detected', 0)} of {m['runs']}" + (f" ({dl:.0f} s)" if dl == dl else "") + "</td>")
        h.append("</tr>")
    if calm:
        h.append(f'<tr><td class="l"><b>All {len(calm)} other tests</b></td><td class="l"><small>nothing (every '
                 'site works as configured)</small></td>')
        for r in rules:
            ms_ = [st.meter[(k, r)] for k in calm if (k, r) in st.meter]
            h.append(f"<td>{sum(m['runs_changed'] for m in ms_)} of {sum(m['runs'] for m in ms_)}</td>"
                     f"<td>{np.mean([m['changes'] for m in ms_]):.2f}</td><td>-</td>" if ms_ else
                     "<td>-</td><td>-</td><td>-</td>")
        h.append("</tr>")
    h.append("</table></div><p class='muted'>What the meter of ingress A measured (every ingress measures for "
             "itself from the same reports). Servers are whole-server equivalents: Jdeideh at 70% speed = 2.8. "
             "Delay = from the real change to the first change of the estimate for that site.</p>")
    return "".join(h)


# ====================================================================================== tables
def verdict_vs(d, base):
    if not d:
        return "-"
    v = d["verdict"]
    name = plots.SHORT[base]
    if v in ("ours better", "base better"):
        return f'<span class="good">{esc(name)} lower</span>'
    if v in ("ours worse", "base worse"):
        return f'<span class="bad">{esc(name)} higher</span>'
    return f'<span class="neutral">{esc(v)}</span>'


def main_table(st, key="main"):
    base = "ours_v2_speed" if (key, "ours_v2_speed") in st.summary else "ours"
    rows = [r for r in PRACTICAL + ["oracle"] if (key, r) in st.summary]
    rows.sort(key=lambda r: st.summary[(key, r)]["miss"])
    h = ['<div class="tw"><table><tr><th class="l">Rule</th><th class="l">Group</th><th>Missed deadline</th>'
         '<th>Mean time</th><th>Slowest 1% (p99)</th><th>Load swing</th><th>Bytes/s</th>'
         f'<th>That rule minus {esc(plots.SHORT[base])} (pts)</th><th class="l">Paired verdict</th></tr>']
    for r in rows:
        s = st.summary[(key, r)]
        d = st.diff(key, r, base=base) if r != base else None
        dd = f"{d['diff']:+.2f} <small>&plusmn;{d['ci']:.2f}</small>" if d else "-"
        h.append(f'<tr class="{"ours" if r in OURS_FAMILY else ""}"><td class="l">{esc(LABELS[r])}</td>'
                 f'<td class="l"><small>{esc(GROUP_OF.get(r, ""))}</small></td><td>{pct(s["miss"], s["miss_ci"])}</td>'
                 f'<td>{ms(s["mean_ms"])}</td><td>{ms(s["p99_ms"])}</td><td>{s["swing"]:.3f}</td>'
                 f'<td>{s["bytes"]:.0f}</td><td>{dd}</td><td class="l">{verdict_vs(d, base)}</td></tr>')
    h.append("</table></div>")
    return "".join(h)


def site_table(st, key="main"):
    rows = [r for r in PRACTICAL + ["oracle"] if (key, r) in st.summary]
    rows.sort(key=lambda r: st.summary[(key, r)]["miss"])
    h = ['<div class="tw"><table><tr><th class="l">Rule</th>' +
         "".join(f"<th>{esc(n)}: share of frames</th><th>{esc(n)}: missed</th>" for n in SITE_NAMES) + "</tr>"]
    for r in rows:
        s = st.summary[(key, r)]
        h.append(f'<tr class="{"ours" if r in OURS_FAMILY else ""}"><td class="l">{esc(LABELS[r])}</td>')
        for sh, mm in zip(s["share"], s["miss_by_site"]):
            h.append(f"<td>{100 * sh:.1f}%</td><td>{pct(100 * mm, nd=1) if mm == mm else '-'}</td>")
        h.append("</tr>")
    cap = np.array(MAIN.servers) / sum(MAIN.servers)
    h.append('<tr><td class="l"><small>Share of capacity</small></td>' +
             "".join(f"<td><small>{100 * c:.1f}%</small></td><td></td>" for c in cap) + "</tr></table></div>")
    return "".join(h)


def matrix(st, metric="miss"):
    """Every test x every rule. metric 'miss' (% late, plus the room to win) or 'p99' (slowest 1%, seconds)."""
    rules = [r for r in PRACTICAL + ["oracle"] if any((k, r) in st.summary for k in st.keys)]
    room = metric == "miss"
    h = ['<div class="tw"><table class="matrix"><tr><th class="l">Test</th>']
    h += [f'<th class="{"oursh" if r in OURS_FAMILY else ""}">{esc(plots.SHORT[r])}</th>' for r in rules]
    if room:
        h.append('<th>Room to win (pts)</th>')
    h.append("</tr>")
    group = None
    for k in st.keys:
        g = GROUP_NAMES[st.scen[k].group]
        if g != group:
            group = g
            h.append(f'<tr><td class="l" colspan="{len(rules) + 1 + room}"><b>{esc(g)}</b></td></tr>')
        if metric == "miss":
            best = st.best_practical(k)[0]
        else:
            cand = [(r, st.summary[(k, r)]["p99_ms"]) for r in PRACTICAL if (k, r) in st.summary]
            best = min(cand, key=lambda x: x[1])[0] if cand else None
        h.append(f'<tr><td class="l lab">{esc(short_label(st, k))}</td>')
        for r in rules:
            s = st.summary.get((k, r))
            if not s:
                h.append("<td>-</td>")
                continue
            if metric == "miss":
                bg, fg = cell_color(s["miss"])
                ci = s["miss_ci"]
                title = (f'{LABELS[r]}: {s["miss"]:.2f}% (95% CI +/- {ci:.2f})' if ci == ci
                         else f'{LABELS[r]}: {s["miss"]:.2f}%')
                v = f"{s['miss']:.1f}" if s["miss"] >= 1 else f"{s['miss']:.2f}"
            else:
                bg, fg = cell_color(s["p99_ms"], lo=200.0, hi=100000.0)
                title = f'{LABELS[r]}: slowest 1% of frames took {ms(s["p99_ms"])} or more'
                v = secs(s["p99_ms"])
            if r == best:
                v = "&#9733;&nbsp;" + v
            h.append(f'<td class="{"best" if r == best else ""}" style="background:{bg};color:{fg}" '
                     f'title="{esc(title)}">{v}</td>')
        if room:
            rw = st.room_to_win(k)
            h.append(f"<td>{rw:+.1f}</td>" if rw == rw else "<td>-</td>")
        h.append("</tr>")
    h.append("</table></div>")
    return "".join(h)


def tally_table(st):
    bases = [b for b in OURS_FAMILY if b in st.tallies]
    if not bases:
        return ""
    others = [r for r in st.rules if r not in ABLATIONS]
    h = ['<div class="tw"><table><tr><th class="l" rowspan="2">Compared with</th>' +
         "".join(f'<th colspan="3">{esc(LABELS[b])}</th>' for b in bases) + "</tr><tr>" +
         "".join("<th>lower</th><th>no clear diff.</th><th>higher</th>" for _ in bases) + "</tr>"]
    for r in others:
        cells = []
        for b in bases:
            t = st.tallies[b].get(r)
            cells.append(f'<td class="good">{t["better"]}</td><td>{t["same"]}</td><td class="bad">{t["worse"]}</td>'
                         if t else "<td></td><td>-</td><td></td>")
        h.append(f'<tr><td class="l">{esc(LABELS[r])}</td>{"".join(cells)}</tr>')
    h.append("</table></div><p class='muted'>Counts of tests where that version of ours had a clearly lower, not "
             "clearly different, or clearly higher miss rate than the rule in the row (paired 95% CI).</p>")
    return "".join(h)


def ablation_table(st):
    pts = st.sweeps["report_interval"][2]
    variants = ["ours"] + [a for a in ABLATIONS if any((sc.key, a) in st.summary for sc in pts)]
    if len(variants) == 1:
        return ""
    h = ['<div class="tw"><table class="abl"><tr><th class="l">Variant</th>' +
         "".join(f"<th>W = {esc(sc.value)} s</th>" for sc in pts if (sc.key, "ours") in st.summary) + "</tr>"]
    for r in variants:
        h.append(f'<tr class="{"ours" if r == "ours" else ""}"><td class="l">{esc(LABELS[r])}</td>')
        for sc in pts:
            if (sc.key, "ours") not in st.summary:
                continue
            s = st.summary.get((sc.key, r))
            if not s:
                h.append("<td>-</td>")
                continue
            d = st.paired.get((sc.key, r))
            extra = f"<br><small>{d['diff']:+.2f} pts, {esc(d['verdict'].replace('ours', 'full rule'))}</small>" if d else ""
            h.append(f"<td>{pct(s['miss'], s['miss_ci'])}{extra}</td>")
        h.append("</tr>")
    h.append("</table></div>")
    return "".join(h)


def calib_table(st):
    rows = []
    for sc in st.sweeps["report_interval"][2]:
        for r in ["ours", "ours_v2", "ours_v2_check", "ours_v2_speed", "expected_delay", "dahlin", "liyanage"]:
            c = st.calib.get((sc.key, r))
            if c and (r == "ours" or sc.key == "main"):
                rows.append((sc.value, r, c))
    if not rows:
        return ""
    h = ['<div class="tw"><table><tr><th class="l">Report interval</th><th class="l">Rule</th>'
         '<th>Average predicted risk</th><th>Share actually late</th><th>Predicted / actual</th></tr>']
    for w, r, c in rows:
        ratio = c["mean_pred"] / c["mean_actual"] if c["mean_actual"] > 0 else float("nan")
        h.append(f'<tr><td class="l">{esc(w)} s</td><td class="l">{esc(LABELS[r])}</td>'
                 f'<td>{100 * c["mean_pred"]:.2f}%</td><td>{100 * c["mean_actual"]:.2f}%</td><td>{ratio:.2f}x</td></tr>')
    h.append("</table></div>")
    c = st.calib.get(("main", "ours"))
    if c:
        h.append('<h3>Ours v1, main scenario: predicted risk vs reality, bin by bin</h3><div class="tw"><table>'
                 '<tr><th class="l">Predicted risk bin</th><th>Frames</th><th>Average predicted</th>'
                 '<th>Actually late (95% CI)</th></tr>')
        for b in c["rows"]:
            h.append(f'<tr><td class="l">{100 * b["bin_lo"]:g}% to {100 * b["bin_hi"]:g}%</td><td>{b["frames"]:,}</td>'
                     f'<td>{100 * b["predicted"]:.2f}%</td><td>{100 * b["actual"]:.2f}% '
                     f'<small>({100 * b["actual_lo"]:.2f} to {100 * b["actual_hi"]:.2f})</small></td></tr>')
        h.append("</table></div>")
    return "".join(h)


def checks_table(checks):
    if not checks:
        return ""
    h = ['<div class="tw"><table><tr><th class="l">Check</th><th class="l">Case</th><th class="l">What</th>'
         '<th>Formula</th><th>Simulated</th><th>Error</th><th class="l">Verdict</th></tr>']
    for r in checks:
        v = r["verdict"]
        cls = "good" if v == "OK" else ("neutral" if v == "APPROX" else "bad")
        sim = f"{r['simulated']:g}" + (f" <small>&plusmn;{r['ci95']:g}</small>" if r["ci95"] == r["ci95"] else "")
        h.append(f'<tr><td class="l">{esc(r["check"])}</td><td class="l">{esc(r["case"])}</td>'
                 f'<td class="l"><small>{esc(r["quantity"])}</small></td><td>{r["model"]:g}</td><td>{sim}</td>'
                 f'<td>{r["error"]:g}</td><td class="l"><span class="{cls}">{esc(v)}</span></td></tr>')
    h.append("</table></div>")
    return "".join(h)


def scenario_table(st, scs):
    """Main scenario + the given tests: % late (and the slowest 1%) for the highlighted rules."""
    keys = ["main"] + [sc.key for sc in scs if any((sc.key, r) in st.summary for r in plots.HIGHLIGHT)]
    if len(keys) == 1:
        return ""
    cols = [r for r in plots.HIGHLIGHT if any((k, r) in st.summary for k in keys)]
    h = ['<div class="tw"><table><tr><th class="l">Test</th>' +
         "".join(f"<th>{esc(plots.SHORT[r])}</th>" for r in cols) +
         '<th class="l">Lowest practical rule</th><th>Room to win (pts)</th></tr>']
    for k in keys:
        b, bm = st.best_practical(k)
        h.append(f'<tr><td class="l">{esc(st.label(k))}</td>')
        for r in cols:
            s = st.summary.get((k, r))
            ci = f"<br><small>&plusmn;{s['miss_ci']:.2f}</small>" if s and s["miss_ci"] == s["miss_ci"] else ""
            h.append(f"<td>{s['miss']:.2f}%{ci}<br><small>p99 {ms(s['p99_ms'])}</small></td>" if s else "<td>-</td>")
        rw = st.room_to_win(k)
        h.append(f'<td class="l">{esc(LABELS[b])} ({bm:.2f}%)</td><td>{rw:+.1f}</td></tr>' if rw == rw else
                 f'<td class="l">{esc(LABELS[b])} ({bm:.2f}%)</td><td>-</td></tr>')
    h.append("</table></div>")
    return "".join(h)


def rules_table(st):
    h = ['<div class="tw"><table><tr><th class="l">Group</th><th class="l">Rule</th><th class="l">How it picks a site</th></tr>']
    for g, rs in list(GROUPS.items()) + [("Ablations of ours v1", ABLATIONS)]:
        for r in rs:
            if r in st.rules:
                h.append(f'<tr><td class="l"><small>{esc(g)}</small></td><td class="l">{esc(LABELS[r])}</td>'
                         f'<td class="l">{esc(DESCRIBE[r])}</td></tr>')
    h.append("</table></div>")
    return "".join(h)


# ====================================================================================== page
def build(steps, run_dir, out, checks_file, meta):
    st = Study(steps, run_dir)
    quick = meta.get("mode") == "quick"
    checks, detail = [], []
    if os.path.exists(checks_file):
        with open(checks_file) as f:
            cj = json.load(f)
        checks, detail = cj["rows"], cj["late_detail"]
    tag = "_quick" if quick else ""
    os.makedirs(out, exist_ok=True)
    tables = os.path.join(out, "tables" + tag)
    os.makedirs(tables, exist_ok=True)
    st.write_csv(tables)
    import csv
    with open(os.path.join(tables, "checks.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["check", "case", "quantity", "formula", "simulated", "ci95", "error", "verdict"])
        for r in checks:
            w.writerow([r["check"], r["case"], r["quantity"], r["model"], r["simulated"], r["ci95"], r["error"], r["verdict"]])
    charts = plots.make_all(st, detail, os.path.join(out, "charts" + tag), quick=quick)

    n_runs = len(st.runs)
    cpu = sum(o.get("runtime_s", 0) for o in st.runs.values())
    m = MAIN
    P = []
    P.append(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>CATS Simulation Results</title>
<style>{CSS}</style></head><body><main>
<h1>CATS site selection: simulation results</h1>
<p class="sub">Packet Patrol &middot; CMPS 342 &middot; {'QUICK run (main scenario only, a first look)' if quick else 'full study'}
&middot; {meta['seeds']} seed(s) per test &middot; {n_runs:,} simulation runs &middot; started {esc(meta['started'])}</p>""")
    if st.missing:
        P.append(f'<div class="card"><b>Incomplete:</b> {len(st.missing)} planned runs are missing. Run the same '
                 f'command again to finish them.</div>')
    if not st.paired_ok:
        P.append('<div class="card"><b>Warning:</b> some rules saw a different number of frames for the same '
                 'scenario and seed; the paired comparison is not valid.</div>')

    P.append("""<div class="card key"><b>How to read this page</b><ul>
<li><b>Missed deadline</b> = share of frames whose answer came back after the deadline. Lower is better.</li>
<li><b>Slowest 1% (p99)</b> = 99% of frames came back faster than this.</li>
<li><b>&plusmn;</b> = 95% confidence interval over the seeds (independent repetitions).</li>
<li><b>Paired:</b> for the same seed every rule saw exactly the same frames, job sizes, delays and lost
reports. "Lower / higher" means the 95% interval of the seed-by-seed difference is entirely on one side of 0.</li>
<li><b>Practical rules</b> = everything except the oracle, which sees the true queues (impossible in practice).</li>
<li><b>Room to win</b> = weighted round-robin's miss rate minus the oracle's: how much any rule that uses
reports could gain in that test.</li>
<li><b>Ours</b> comes in four versions: v1 (best site per frame), v2 (a split per report interval), v2 + self-check,
and v2 + measured speeds (round 3). <b>Round-robin + measured speeds</b> is its fair control: the same measured
speeds, without our model.</li>
</ul></div>""")

    P.append('<h2>Main results</h2><ul>' + "".join(f"<li>{x}</li>" for x in headline(st, checks)) + "</ul>")
    sites = ", ".join(f"{n} ({c} servers, {d:g} ms)" for n, c, d in zip(SITE_NAMES, m.servers, m.base_delay_ms))
    P.append(f"""<h2>1. Main scenario (Beirut)</h2>
<ul><li>3 sites: {esc(sites)} round trip from Ingress A; the other ingresses are up to
{m.delay_spread:.0%} nearer or farther.</li>
<li>Each server finishes {m.mu:g} frames/s on average (100 ms); job sizes vary (Gamma, variability {m.job_scv:g}).</li>
<li>{m.ingresses} ingresses send {m.load:.0%} of total capacity, split 40 / 30 / 20 / 10%. Deadline {m.deadline_ms:g} ms.</li>
<li>Each site reports its frames (and the 4-byte arrivals counter) every {m.report_interval:g} s.
Each run: {m.duration():g} s of traffic, the first {m.warmup_time():g} s not counted.</li></ul>""")
    P.append(img(charts.get("main")) + main_table(st))
    P.append("<h3>Which differences are real?</h3>" + img(charts.get("paired_v2_speed")) + img(charts.get("paired_v2"))
             + img(charts.get("paired")))
    P.append("<h3>Where the misses happen</h3>" + site_table(st))
    P.append("<h3>Stability and what the queues look like</h3>" + img(charts.get("swing")) + img(charts.get("series")))

    if not quick:
        P.append("<h2>2. All tests at a glance</h2><p>Missed deadline (%) for every test and rule, average of the "
                 "seeds (hover a cell for the 95% interval). Darker = more misses. &#9733; = lowest practical rule in "
                 "that row (the oracle is not counted).</p>" + matrix(st, "miss"))
        P.append("<h3>The slowest 1% of frames (seconds)</h3><p>99% of frames came back faster than this. "
                 "&#9733; = lowest practical rule in that row.</p>" + matrix(st, "p99"))
        P.append("<h3>Each version of ours against each rule, over all tests (paired 95% CI)</h3>" + tally_table(st))
        P.append("<h2>3. Sweeps: change one factor at a time</h2>" + img(charts.get("sweeps")) +
                 img(charts.get("bytes")) + "<p class='muted'>Exact numbers are in the tables of section 2.</p>")
        P.append("<h2>4. Stress tests</h2>" + img(charts.get("stress")) + scenario_table(st, st.stress))
        P.append("<h2>5. Real-life scenarios</h2><p>The main scenario plus one thing that happens in real "
                 "deployments. None of these events is announced to the rules.</p>" + img(charts.get("real")) +
                 scenario_table(st, st.real))
        if [sc for sc in st.heldout if sc.key in st.keys]:
            P.append("<h3>Held-out scenarios</h3><p>Two more real-life events, defined before any run of round 3 and "
                     "never used to design or tune any rule (they were not in the pilot). They check that ours v2 + "
                     "measured speeds is not tuned to the scenarios it was designed on. Both keep the total load "
                     "during the event near the other failure scenarios (91 to 93% of what is really working).</p>"
                     + img(charts.get("heldout")) + scenario_table(st, st.heldout))
        if st.meter:
            P.append("<h3>What the measured speeds saw</h3><p>For every test where a site's real capacity changes: "
                     "the real servers of that site and the estimate of the speed meter of ingress A (first seed). "
                     "Then, over all seeds, how often each meter changed its estimate, and how fast it reacted.</p>"
                     + img(charts.get("speeds")) + meter_table(st))
        P.append("<h2>6. Ablations: what each part of ours v1 contributes</h2>" + img(charts.get("ablations"))
                 + ablation_table(st))
    else:
        P.append("<h2>Ablations of ours v1 (main scenario)</h2>" + ablation_table(st))
    P.append("<h2>7. Is the predicted risk right? (calibration)</h2>"
             "<p>Every version of ours predicts, for each frame, the chance it will be late at the chosen site. If "
             "the prediction is right, the points sit on the diagonal.</p>" + img(charts.get("calibration"))
             + calib_table(st))
    P.append("<h2>8. Built-in checks</h2><ul><li><b>1.</b> The simulator against textbook M/M/c (Erlang C) "
             "formulas.</li><li><b>2.</b> Our late(n) formula against a separate simulation.</li><li><b>3.</b> Our "
             "belief ageing against a separate simulation (TV distance: 0 = identical, 1 = completely different)."
             "</li></ul>" + checks_table(checks) + img(charts.get("late_check")))
    P.append("<h2>9. The rules</h2>" + rules_table(st))
    P.append(f"""<h2>10. Method notes and limits</h2><ul>
<li>Discrete-event simulation in Python (a custom event loop, not SimPy, for speed). Frames arrive at random
(Poisson); each site serves first come, first served.</li>
<li>Every rule uses only what its ingress could know: path delays and site sizes, the reports it received, its
own sends (Liyanage-style and ours v2 + self-check: also the delays of its own frames). Only the oracle sees the
truth.</li>
<li>Same telemetry budget: report rules receive the same reports; Prequal-style spends the same bytes per second on
probes. Bytes/s counts the 62-byte report, plus the 4-byte counter for rules that use it.</li>
<li>Adaptations, chosen to be fair to each rule: LSQ-style compares frames per server (the sites differ in size);
Prequal-style uses each probe answer at most twice (as Prequal does, to avoid herding); Liyanage-style runs one
controller per camera, about 10 frames/s each (one controller for a whole ingress cannot split its traffic).</li>
<li>Second round, added after the first results: ours v2 and v2 + self-check, the seven real-life scenarios, the
slowest-1% table, the room to win and the report-traffic chart. Their settings were fixed before any result on the
seeds of this report was seen. The pilot (<code>--pilot</code>) used only the spare seeds
{esc(', '.join(str(s) for s in PILOT_SEEDS))}; after it, ONE rule was added to v2: no site is planned above 95% of
its capacity (in the pilot, at peak load the plan deliberately overloaded one site and left a growing backlog).</li>
<li>Third round, added after the second results: ours v2 + measured speeds, its control round-robin + measured
speeds, and two held-out scenarios. Ours v2 + measured speeds was designed to fix a weakness found in round 2 on
the seeds of this report (v2 kept feeding a site that was secretly slower than configured), so the real-life
scenarios it was designed for are not independent evidence; the held-out scenarios are, and so is the control.
The held-out scenarios were defined before any run of round 3 and were not in the pilot. The pilot used only the
spare seeds; it ran three times, and the speed meter was changed twice in between (all three tables are in
<code>pilot/</code>): (1) after false measurements with reports every 0.2 s, a site is measured only after its queue
stayed long for 5 s, and a slowed site gets a server back after a quiet spell only if its queue stayed short,
waiting twice as long after a wrong return; (2) after the shared-GPU scenario got much worse (a low measurement
pushed the healthy sites over 95%), a slowed site gets back just enough capacity when the measured speeds cannot
carry the traffic, a site that serves more than measured is raised at once, and the quiet spell became 20 s. The
settings were then fixed before any run on the seeds of this report. After the full run, one bug was found in the
logs and fixed: when a site served more than its configured size, the meter recorded a "change" to the value it
already had (and restarted its evidence). It happened in 3 of the 720 runs of the two metered rules; redoing those
3 runs gave the same miss rates and slowest-1% times (only the false log entries disappeared), and 27 other runs
redone with the fix came out identical.</li>
<li>Also added after the approved plan: the stress test where Hamra loses a server without announcing it, and
report intervals of 0.2 and 0.5 s.</li>
<li>Not modelled: failures of ingresses, batching on the GPUs, frames that know their own job size, a site that
stops completely. The oracle sees true queues, servers and GPU speed, but not path congestion. In "slow GPUs",
frames already being processed when the speed changes keep their time.</li>
<li>The speed meter counts whole servers at the configured speed per server, so a slowdown of every GPU (slow GPUs)
is seen as fewer servers of normal speed: the model then expects shorter jobs than there really are.</li>
<li>The belief ageing of every version of ours is exact only for exponential job sizes; for other shapes it is an
approximation (see check 3).</li>
<li>Every run lasts at least 20 report intervals: with reports every 10 s or 30 s a run is 200 s or 600 s long and
the first 20 s or 60 s are not counted. Those runs see more frames than the others, so even the rules that use no
reports (weighted round-robin, for example) give slightly different numbers there.</li></ul>""")
    files = sorted(os.listdir(tables))
    P.append("<h2>11. Files and run details</h2><ul>"
             f"<li>Tables (CSV): <code>{esc(os.path.basename(tables))}/</code> {esc(', '.join(files))}</li>"
             f"<li>Charts (PNG): <code>charts{tag}/</code></li>"
             f"<li>Every single run: <code>runs/</code> (one JSON file per scenario, rule and seed)</li>"
             f"<li>{n_runs:,} runs, {cpu / 3600:.2f} CPU-hours of simulation in total (sum over all runs); "
             f"report built with Python {esc(meta['python'])} on {esc(meta['machine'])}</li></ul></main></body></html>")
    path = os.path.join(out, f"report{tag}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(P))
    return path
