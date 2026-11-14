"""Charts for the report (PNG, matplotlib). Colours follow the rule everywhere:
ours v1 / v2 / v2 + self-check = shades of blue (light, medium, dark), ours v2 + measured speeds = orange,
weighted round-robin = aqua (its measured-speeds control: the same aqua, hollow markers / dashed line),
oracle = dark grey, every other rule = grey. The palette was checked with the dataviz validator: the coloured
series of each chart stay apart for colour-blind readers (adjacent dots, or every pair of lines). Every chart has
a table twin in the report."""
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator  # noqa: E402

from .config import ABLATIONS, LABELS, SITE_NAMES  # noqa: E402
from .analysis import METERED, PRACTICAL, capacity_truth  # noqa: E402

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
COL = {"ours": "#86b6ef", "ours_v2": "#2a78d6", "ours_v2_check": "#104281", "ours_v2_speed": "#eb6834",
       "wrr": "#1baf7a", "wrr_speed": "#1baf7a", "oracle": "#52514e",
       # only in the calibration chart, next to the four versions of ours: greys, told apart by marker
       "expected_delay": "#898781", "dahlin": "#b3b2ab", "liyanage": "#6b6a65", "lsq": "#898781"}
FAMILY = ("ours", "ours_v2", "ours_v2_check", "ours_v2_speed")
HERO = "ours_v2_speed"
HOLLOW = {"wrr_speed"}                    # same hue as weighted round-robin, open marker / dashed line
OTHER = "#c3c2b7"
GOOD, BAD = "#0ca30c", "#d03b3b"          # status colours: only for "ours better / worse" verdicts
HIGHLIGHT = ["ours", "ours_v2", "ours_v2_check", "ours_v2_speed", "wrr", "wrr_speed", "oracle"]
SWEEP_HL = ["ours", "ours_v2", "ours_v2_speed", "wrr", "wrr_speed", "oracle"]
SHORT = {"ours": "Ours v1", "ours_v2": "Ours v2", "ours_v2_check": "Ours v2 + check",
         "ours_v2_speed": "Ours v2 + speeds", "expected_delay": "Expected delay", "dahlin": "Dahlin-style",
         "liyanage": "Liyanage-style",
         "lsq": "LSQ-style", "timeout_sed": "CATS timeout+SED", "power_of_two": "Power of two",
         "wpow2_stale": "Weighted power of two", "prequal": "Prequal-style", "nearest": "Nearest site",
         "cap_random": "Capacity-weighted random", "wrr": "Weighted round-robin",
         "wrr_speed": "Round-robin + speeds", "oracle": "Oracle",
         "ours_no_counting": "no counting", "ours_no_ageing": "no ageing", "ours_exp_late": "exponential late(n)",
         "ours_no_ties": "no random near-ties"}


def _mstyle(r, color):
    """Marker face: hollow for the measured-speeds control, so it differs from round-robin without a new hue."""
    return dict(mfc=SURFACE if r in HOLLOW else color, mec=color if r in HOLLOW else SURFACE,
                mew=1.6 if r in HOLLOW else 1.2)
LOG_TICKS = [0.5, 1, 2, 5, 10, 20, 50, 100]

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 9.5, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left",
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "legend.fontsize": 9, "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
})


def _pct(v, _=None):
    return f"{v:g}%"


def _logy(ax, lo=0.5, hi=100, axis="y"):
    lo = max(min(lo, 0.5), 0.05)
    ticks = [t for t in [0.05, 0.1, 0.2] + LOG_TICKS if lo <= t <= hi]
    if axis == "y":
        ax.set_yscale("log")
        ax.set_ylim(lo, hi * 1.15)
        ax.yaxis.set_major_locator(FixedLocator(ticks))
        ax.yaxis.set_minor_locator(NullLocator())
        ax.yaxis.set_major_formatter(FuncFormatter(_pct))
        ax.grid(axis="y", color=GRID, lw=0.8)
    else:
        ax.set_xscale("log")
        ax.set_xlim(lo, hi * 1.15)
        ax.xaxis.set_major_locator(FixedLocator(ticks))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.xaxis.set_major_formatter(FuncFormatter(_pct))
        ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def _save(fig, path):
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _floor(st, keys, rules):
    vals = [st.summary[(k, r)]["miss"] for k in keys for r in rules if (k, r) in st.summary]
    vals = [v for v in vals if v > 0]
    return min(vals) if vals else 0.5


# ------------------------------------------------------------------------------ main scenario
def main_dots(st, path, key="main", title="Deadline-miss rate, main scenario (lower is better)"):
    rules = [r for r in PRACTICAL + ["oracle"] if (key, r) in st.summary]
    rules.sort(key=lambda r: st.summary[(key, r)]["miss"])
    lo = _floor(st, [key], rules) * 0.7
    fig, ax = plt.subplots(figsize=(8.6, 0.36 * len(rules) + 1.2))
    for y, r in enumerate(rules):
        s = st.summary[(key, r)]
        m, h = s["miss"], s["miss_ci"]
        c = COL[r] if (r in FAMILY or r == "oracle") else MUTED
        if not math.isnan(h) and h > 0:
            ax.plot([max(m - h, lo), m + h], [y, y], color=c, lw=1.6, alpha=0.6)
        ax.plot(m, y, "o", ms=7, color=c, mec=SURFACE, mew=1.5, zorder=3)
        if r in FAMILY or r == "oracle" or y == 0 or (y == 1 and rules[0] == "oracle"):
            ax.annotate(f"{m:.2f}%", (min(m + (h if h == h else 0), 100), y), xytext=(6, 0),
                        textcoords="offset points", va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(range(len(rules)))
    ax.set_yticklabels([LABELS[r] for r in rules])
    for t, r in zip(ax.get_yticklabels(), rules):
        if r in FAMILY:
            t.set_fontweight("bold")
            t.set_color(INK)
    ax.invert_yaxis()
    _logy(ax, lo, 100, axis="x")
    ax.set_xlabel("frames that missed the 300 ms deadline (log scale); line = 95% confidence interval")
    ax.set_title(title)
    return _save(fig, path)


def paired_forest(st, path, key="main", base="ours"):
    diffs = {r: st.diff(key, r, base=base) for r in PRACTICAL + ["oracle"] if r != base}
    diffs = {r: d for r, d in diffs.items() if d and d["ci"] == d["ci"]}
    rules = sorted(diffs, key=lambda r: diffs[r]["diff"])
    fig, ax = plt.subplots(figsize=(8.6, 0.34 * len(rules) + 1.3))
    span = max(abs(diffs[r]["diff"]) + diffs[r]["ci"] for r in rules)
    for y, r in enumerate(rules):
        d = diffs[r]
        good = d["verdict"] in ("ours better", "base better")
        bad = d["verdict"] in ("ours worse", "base worse")
        c = GOOD if good else (BAD if bad else MUTED)
        ax.plot([d["diff"] - d["ci"], d["diff"] + d["ci"]], [y, y], color=c, lw=1.8, alpha=0.7)
        ax.plot(d["diff"], y, "o", ms=6.5, color=c, mec=SURFACE, mew=1.5, zorder=3)
    ax.axvline(0, color=AXIS, lw=1)
    ax.set_yticks(range(len(rules)))
    ax.set_yticklabels([LABELS[r] for r in rules])
    ax.set_xscale("symlog", linthresh=1.0)
    ax.set_xlim(-span * 1.3 - 0.5, span * 1.3 + 0.5)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+g}" if v else "0"))
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel(f"that rule's miss rate minus {SHORT[base]}'s, percentage points (same frames, seed by seed)\n"
                  f"right of 0 = {SHORT[base]} misses fewer    left of 0 = it misses more    line = 95% CI")
    ax.set_title(f"Paired difference with {SHORT[base]}, main scenario")
    ax.plot([], [], "o", color=GOOD, label=f"{SHORT[base]} clearly better")
    ax.plot([], [], "o", color=MUTED, label="no clear difference")
    ax.plot([], [], "o", color=BAD, label=f"{SHORT[base]} clearly worse")
    ax.legend(loc="lower right", ncol=1)
    return _save(fig, path)


def swing_dots(st, path, key="main"):
    rules = [r for r in PRACTICAL + ["oracle"] if (key, r) in st.summary]
    rules.sort(key=lambda r: st.summary[(key, r)]["swing"])
    fig, ax = plt.subplots(figsize=(8.6, 0.33 * len(rules) + 1.1))
    for y, r in enumerate(rules):
        v = st.summary[(key, r)]["swing"]
        c = COL[r] if (r in FAMILY or r == "oracle") else MUTED
        ax.plot([0, v], [y, y], color=c, lw=1.6, alpha=0.35)
        ax.plot(v, y, "o", ms=6.5, color=c, mec=SURFACE, mew=1.5, zorder=3)
    ax.set_yticks(range(len(rules)))
    ax.set_yticklabels([LABELS[r] for r in rules])
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator([0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("load swing: how much the load each site receives jumps from second to second\n"
                  "(standard deviation of the per-second load, as a share of the site's capacity; lower = steadier)")
    ax.set_title("Stability, main scenario")
    return _save(fig, path)


# ------------------------------------------------------------------------------ sweeps
def sweeps(st, path):
    factors = [(f, t, num, pts) for f, (t, num, pts) in st.sweeps.items()]
    n = len(factors)
    cols = 4
    rows = math.ceil(n / cols)
    keys = [sc.key for _, _, _, pts in factors for sc in pts]
    lo = _floor(st, keys, PRACTICAL + ["oracle"]) * 0.7
    fig, axes = plt.subplots(rows, cols, figsize=(13, 3.3 * rows + 0.6), squeeze=False)
    for ax, (f, title, numeric, pts) in zip(axes.flat, factors):
        xs = list(range(len(pts)))
        labels = [sc.value for sc in pts]
        if f == "report_interval":
            xs = [float(v) for v in labels]
            ax.set_xscale("log")
        elif numeric:
            xs = [float(v) for v in labels]
            if f == "ingresses":
                ax.set_xscale("log", base=2)
        others = [r for r in PRACTICAL if r not in SWEEP_HL]
        for r in others + SWEEP_HL:
            y = [st.summary[(sc.key, r)]["miss"] if (sc.key, r) in st.summary else np.nan for sc in pts]
            hl = r in SWEEP_HL
            c = COL.get(r, OTHER) if hl else OTHER
            hero = r == HERO
            if numeric:
                ax.plot(xs, y, "--" if r in HOLLOW else "-", color=c, lw=2.2 if hero else (1.6 if hl else 0.9),
                        zorder=4 if hero else (3 if hl else 1))
                if hl:
                    ax.plot(xs, y, "o", ms=6 if hero else 5, color=c, zorder=5 if hero else 3, **_mstyle(r, c))
            else:
                k = SWEEP_HL.index(r) if hl else len(SWEEP_HL)
                off = (k - (len(SWEEP_HL) - 1) / 2) * 0.07 if hl else 0
                if hl:
                    ax.plot(np.array(xs) + off, y, "o", ms=6, color=c, zorder=4 if hero else 3, **_mstyle(r, c))
                else:
                    ax.plot(xs, y, "_", ms=9, color=c, mew=1.0, zorder=1)
        main_v = [x for x, sc in zip(xs, pts) if sc.key == "main"]
        for x in main_v:
            ax.axvline(x, color=GRID, lw=6, zorder=0)
        ax.set_xticks(xs)
        ax.set_xticklabels([v.replace(" ", "\n", 1) if len(v) > 9 else v for v in labels], fontsize=8)
        ax.xaxis.set_minor_locator(NullLocator())
        if not numeric:
            ax.set_xlim(-0.5, len(xs) - 0.5)
        _logy(ax, lo, 100)
        ax.set_title(title, fontsize=9.5)
    for ax in axes.flat[n:]:
        ax.axis("off")
    handles = [plt.Line2D([], [], color=COL[r], marker="o", lw=2, ls="--" if r in HOLLOW else "-",
                          label=SHORT[r], **_mstyle(r, COL[r])) for r in SWEEP_HL]
    handles.append(plt.Line2D([], [], color=OTHER, lw=1, label="other rules"))
    fig.legend(handles=handles, loc="upper center", ncol=len(handles), bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("Deadline-miss rate when one factor changes (log scale; the shaded column is the main scenario)",
                 x=0.01, y=1.045, ha="left", fontsize=11, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return _save(fig, path)


# ------------------------------------------------------------------------------ stress tests
def stress(st, path, scs=None, title="Stress tests: the main scenario plus one real-life problem"):
    scs = st.stress if scs is None else scs
    keys = ["main"] + [sc.key for sc in scs if any((sc.key, r) in st.summary for r in HIGHLIGHT)]
    names = ["no problem (main scenario)"] + [sc.label for sc in scs if sc.key in keys]
    lo = _floor(st, keys, HIGHLIGHT) * 0.7
    fig, ax = plt.subplots(figsize=(9.5, 0.7 * len(keys) + 1.4))
    for k_i, r in enumerate(HIGHLIGHT):
        off = (k_i - (len(HIGHLIGHT) - 1) / 2) * 0.1
        xs = [st.summary[(k, r)]["miss"] if (k, r) in st.summary else np.nan for k in keys]
        ax.plot(xs, np.arange(len(keys)) + off, "o", ms=6.5 if r == HERO else 5.5, color=COL[r],
                label=SHORT[r], zorder=4 if r == HERO else 3, **_mstyle(r, COL[r]))
    for y in range(len(keys)):
        ax.axhline(y + 0.5, color=GRID, lw=0.8)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels(names)
    ax.set_ylim(len(keys) - 0.5, -0.5)
    _logy(ax, lo, 100, axis="x")
    ax.set_xlabel("frames that missed the deadline (log scale)")
    ax.set_title(title, pad=44)
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=4, borderaxespad=0.3, fontsize=8.5)
    return _save(fig, path)


# ------------------------------------------------------------------------------ ablations
def ablations(st, path):
    pts = st.sweeps["report_interval"][2]
    xs = [float(sc.value) for sc in pts]
    variants = ["ours"] + [a for a in ABLATIONS if any((sc.key, a) in st.summary for sc in pts)]
    lo = _floor(st, [sc.key for sc in pts], variants) * 0.7
    fig, ax = plt.subplots(figsize=(8.6, 4.3))
    greys = ["#2b2b29", "#6b6a65", "#8f8e88", "#b3b2ab"]
    marks = ["s", "^", "D", "v"]
    for i, r in enumerate(variants):
        y = [st.summary[(sc.key, r)]["miss"] if (sc.key, r) in st.summary else np.nan for sc in pts]
        c = COL["ours"] if r == "ours" else greys[(i - 1) % 4]
        ax.plot(xs, y, "-", color=c, lw=2.2 if r == "ours" else 1.4, zorder=4 if r == "ours" else 2)
        ax.plot(xs, y, "o" if r == "ours" else marks[(i - 1) % 4], ms=6.5, color=c, mec=SURFACE, mew=1.2,
                label="Ours v1 (all parts)" if r == "ours" else f"Ours v1, {SHORT[r]}", zorder=5 if r == "ours" else 3)
    ax.set_xscale("log")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{x:g} s" for x in xs])
    ax.xaxis.set_minor_locator(NullLocator())
    _logy(ax, lo, 100)
    ax.set_xlabel("report interval W")
    ax.set_title("What each part of ours v1 contributes (remove one part at a time)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))
    return _save(fig, path)


# ------------------------------------------------------------------------------ calibration
def calibration(st, path):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.8))
    pts = [sc for sc in st.sweeps["report_interval"][2] if (sc.key, "ours") in st.calib]
    steps = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281",
             "#0d366b"]                       # blue ramp, light to dark (ordinal: short to long report interval)
    idx = np.linspace(0, len(steps) - 1, max(len(pts), 1)).round().astype(int)
    ramp = [steps[i] for i in idx]

    def draw(ax, key, rule, color, label, marker="o"):
        c = st.calib.get((key, rule))
        if not c:
            return
        rows = [b for b in c["rows"] if b["frames"] >= 200 and b["predicted"] > 0]
        if not rows:
            return
        p = np.array([b["predicted"] for b in rows]) * 100
        a = np.array([max(b["actual"], 1e-4) for b in rows]) * 100
        lo_ = np.array([max(b["actual_lo"], 1e-4) for b in rows]) * 100
        hi_ = np.array([b["actual_hi"] for b in rows]) * 100
        ax.vlines(p, lo_, hi_, color=color, lw=1.2, alpha=0.5)
        ax.plot(p, a, "-", color=color, lw=1.6, alpha=0.9)
        ax.plot(p, a, marker, ms=6, color=color, mec=SURFACE, mew=1.2, label=label)

    for ax in (a1, a2):
        ax.plot([0.05, 100], [0.05, 100], color=AXIS, lw=1.2, zorder=0)
        ax.text(60, 40, "perfect", rotation=38, color=MUTED, fontsize=8, ha="right")
        _logy(ax, 0.1, 100, axis="x")
        _logy(ax, 0.1, 100, axis="y")
        ax.set_xlabel("predicted chance of being late")
        ax.set_ylabel("share that was actually late")
    for sc, c in zip(pts, ramp):
        draw(a1, sc.key, "ours", c, f"report every {sc.value} s")
    a1.set_title("Ours v1: is the predicted risk right?")
    a1.legend(loc="upper left")
    for r, mk in (("ours", "o"), ("ours_v2", "s"), ("ours_v2_check", "D"), ("ours_v2_speed", "X"),
                  ("expected_delay", "^"), ("dahlin", "v"), ("liyanage", "P")):
        draw(a2, "main", r, COL[r], SHORT[r] + (" (same belief)" if r == "expected_delay" else ""), mk)
    a2.set_title("Main scenario: every rule that predicts a risk")
    a2.legend(loc="lower right")
    fig.tight_layout()
    return _save(fig, path)


# ------------------------------------------------------------------------------ time series
def timeseries(st, path, rules=("ours", "ours_v2", "ours_v2_speed", "lsq", "wrr", "oracle")):
    data = [(r, st.runs.get(("main", r, 1), {}).get("series")) for r in rules]
    data = [(r, s) for r, s in data if s]
    if not data:
        return None
    greys = ["#a3a29b", "#6b6a65", "#2b2b29"]
    cols = 3
    rows = math.ceil(len(data) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(13, 3.0 * rows + 0.5), squeeze=False, sharey=True)
    ymax = max(max(max(row[1:]) for row in s) for _, s in data)
    for ax, (r, s) in zip(axes.flat, data):
        a = np.array(s)
        t = a[:, 0] - a[0, 0]
        for j in range(a.shape[1] - 1):
            ax.plot(t, a[:, j + 1], color=greys[j], lw=1.3, label=SITE_NAMES[j])
        ax.set_yscale("symlog", linthresh=10)
        ax.set_ylim(0, max(ymax * 1.3, 12))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        miss = st.summary.get(("main", r), {}).get("miss", float("nan"))
        ax.set_title(f"{LABELS[r]}\nmissed deadline over all seeds: {miss:.2f}%", fontsize=9.5)
        ax.set_xlabel("seconds")
    for ax in axes.flat[len(data):]:
        ax.axis("off")
    axes.flat[0].set_ylabel("frames at the site")
    axes.flat[0].legend(loc="upper left", fontsize=8)
    fig.suptitle("Frames waiting or in service at each site over 30 seconds (main scenario, seed 1)",
                 x=0.01, ha="left", fontsize=11, fontweight="bold", color=INK)
    fig.tight_layout()
    return _save(fig, path)


# ------------------------------------------------------------------------------ checks
def late_check(detail, path):
    if not detail:
        return None
    shapes = list(dict.fromkeys(d["shape"] for d in detail))
    cs = sorted({d["c"] for d in detail})
    fig, axes = plt.subplots(len(shapes), len(cs), figsize=(12, 2.7 * len(shapes) + 0.6), squeeze=False)
    for i, sh in enumerate(shapes):
        for j, c in enumerate(cs):
            ax = axes[i][j]
            rows = sorted([d for d in detail if d["shape"] == sh and d["c"] == c], key=lambda d: d["n"])
            n = [d["n"] for d in rows]
            ax.plot(n, [d["model"] for d in rows], "-", color=COL["ours_v2"], lw=2, label="late(n) formula")
            ax.plot(n, [d["simulated"] for d in rows], "o", ms=4.5, color=INK2, mec=SURFACE, mew=1,
                    label="simulation")
            ax.set_ylim(-0.03, 1.03)
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))
            ax.grid(color=GRID, lw=0.8)
            ax.set_axisbelow(True)
            ax.set_title(f"{sh}, {c} servers", fontsize=9)
            if i == len(shapes) - 1:
                ax.set_xlabel("n = frames already at the site")
            if j == 0:
                ax.set_ylabel("chance of being late")
    axes[0][0].legend(loc="lower right", fontsize=8)
    fig.suptitle("Check: late(n) formula vs simulation (time left 250 ms, 85% load)", x=0.01, ha="left",
                 fontsize=11, fontweight="bold", color=INK)
    fig.tight_layout()
    return _save(fig, path)


def bytes_tradeoff(st, path):
    """% late against report traffic, from the report-interval sweep: what fresher reports cost."""
    pts = [sc for sc in st.sweeps["report_interval"][2] if (sc.key, "ours") in st.summary]
    rules = [r for r in ("ours", "ours_v2", "ours_v2_check", "ours_v2_speed", "lsq")
             if any((sc.key, r) in st.summary for sc in pts)]
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    allv = []
    for r in rules:
        xs = [st.summary[(sc.key, r)]["bytes"] for sc in pts if (sc.key, r) in st.summary]
        ys = [st.summary[(sc.key, r)]["miss"] for sc in pts if (sc.key, r) in st.summary]
        allv += ys
        ax.plot(xs, ys, "-" + ("o" if r in FAMILY else "s"), color=COL[r], lw=2.2 if r in FAMILY else 1.4, ms=6,
                mec=SURFACE, mew=1.2, label=LABELS[r], zorder=4 if r in FAMILY else 3)
    refs = [("wrr", "Weighted round-robin (no reports)"), ("oracle", "Oracle (impossible in practice)")]
    for r, name in refs:
        v = st.summary.get(("main", r))
        if v:
            allv.append(v["miss"])
            ax.axhline(v["miss"], color=COL[r], lw=1.2, alpha=0.9, zorder=2)
            ax.plot([], [], color=COL[r], lw=1.2, label=f"{name}: {v['miss']:.2f}%")
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ref_rule = "ours_v2" if "ours_v2" in rules else rules[0]
    top = ax.secondary_xaxis("top")
    top.set_xticks([st.summary[(sc.key, ref_rule)]["bytes"] for sc in pts if (sc.key, ref_rule) in st.summary])
    top.set_xticklabels([f"{sc.value} s" for sc in pts if (sc.key, ref_rule) in st.summary], fontsize=8)
    top.xaxis.set_minor_locator(NullLocator())
    top.set_xlabel("report interval", fontsize=8.5, color=INK2)
    _logy(ax, max(min(allv) * 0.7, 0.05) if allv else 0.5, 100)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_xlabel("report traffic, bytes per second (all ingresses, log scale)")
    ax.set_title("Fresher reports cost bytes: frames late against report traffic", pad=12)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8.5)
    return _save(fig, path)


def _short_scenario(sc):
    if sc.key == "cap_drop":
        return "Stress: server lost halfway"
    lab = sc.label.replace("Held out - ", "")
    return lab.split(":")[0] if ":" in lab else lab


def speed_tracking(st, path):
    """What the speed meter of ingress A measured (first seed), against the real servers of the site that changed."""
    keys = [k for k in st.keys if capacity_truth(st.scen[k]) and any((k, r) in st.summary for r in METERED)]
    if not keys:
        return None
    seed = st.seeds[0]
    cols = 3
    rows = math.ceil(len(keys) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(13, 2.7 * rows + 0.9), squeeze=False)
    for ax, k in zip(axes.flat, keys):
        sc = st.scen[k]
        s, _, truth = capacity_truth(sc)
        told = (sc.servers_known or sc.servers)[s]
        T = sc.duration()
        ax.step([p[0] for p in truth], [p[1] for p in truth], where="post", color=INK2, lw=3.2, alpha=0.3,
                label="real servers (x speed)")
        for r in METERED:
            log = st.runs.get((k, r, seed), {}).get("diag", {}).get("speed_changes")
            if log is None:
                continue
            pts = [(0.0, told)] + [(c[0], c[2]) for c in log if c[1] == s]
            xs = [p[0] for p in pts] + [T]
            ys = [p[1] for p in pts] + [pts[-1][1]]
            ax.step(xs, ys, where="post", color=COL[r], lw=1.9, ls=(0, (3, 3)) if r in HOLLOW else "-",
                    label=f"measured by {SHORT[r]}", zorder=4 if r in HOLLOW else 3)   # dashes on top: both show
        ax.axvspan(0, sc.warmup_time(), color=GRID, alpha=0.5, lw=0, zorder=0)
        ax.set_xlim(0, T)
        ax.set_ylim(0, told + 0.7)
        ax.set_yticks(range(0, told + 1, 1 if told <= 4 else 2))
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.set_title(f"{_short_scenario(sc)}: {SITE_NAMES[s]}", fontsize=9.5)
        ax.set_xlabel("seconds")
    for ax in axes.flat[len(keys):]:
        ax.axis("off")
    axes.flat[0].set_ylabel("servers")
    h, lab = axes.flat[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=len(lab), bbox_to_anchor=(0.5, 1.0))
    fig.suptitle(f"What the measured speeds saw (ingress A, seed {seed}; grey band = warm-up, not counted)",
                 x=0.01, y=1.05, ha="left", fontsize=11, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return _save(fig, path)


def make_all(st, detail, out_dir, quick=False):
    """Draw every chart; a chart that cannot be drawn (e.g. its runs are missing) is skipped with a note."""
    os.makedirs(out_dir, exist_ok=True)
    jobs = [("main", main_dots, st, "1_main_scenario.png"),
            ("paired", paired_forest, st, "2_main_paired_difference_v1.png"),
            ("paired_v2", lambda s_, p_: paired_forest(s_, p_, base="ours_v2"), st, "2b_main_paired_difference_v2.png"),
            ("paired_v2_speed", lambda s_, p_: paired_forest(s_, p_, base="ours_v2_speed"), st,
             "2c_main_paired_difference_v2_speeds.png"),
            ("swing", swing_dots, st, "3_main_stability.png"),
            ("series", timeseries, st, "4_main_queues_over_time.png")]
    if not quick:
        jobs += [("sweeps", sweeps, st, "5_sweeps.png"), ("bytes", bytes_tradeoff, st, "5b_report_traffic.png"),
                 ("stress", stress, st, "6_stress_tests.png"),
                 ("real", lambda s_, p_: stress(s_, p_, scs=s_.real, title="Real-life scenarios: the main scenario "
                                               "plus one thing that happens in real deployments"),
                  st, "6b_real_life.png"),
                 ("heldout", lambda s_, p_: stress(s_, p_, scs=s_.heldout, title="Held-out scenarios: never used to "
                                                  "design or tune any rule"), st, "6c_held_out.png"),
                 ("speeds", speed_tracking, st, "6d_measured_speeds.png"),
                 ("ablations", ablations, st, "7_ablations.png")]
    jobs += [("calibration", calibration, st, "8_calibration.png"),
             ("late_check", late_check, detail, "9_check_late_n.png")]
    p = {}
    for name, fn, data, fname in jobs:
        try:
            p[name] = fn(data, os.path.join(out_dir, fname))
        except Exception as e:                      # keep the report going
            plt.close("all")
            print(f"    (chart '{name}' skipped: {type(e).__name__}: {e})")
    return {k: v for k, v in p.items() if v}
