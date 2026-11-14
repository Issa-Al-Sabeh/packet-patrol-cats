"""Figures of the staleness-aware CATS study (PNG + PDF in study_results/figures/), drawn only from the tables that
study_analysis.py builds from completed runs. Each algorithm keeps one color + one marker in every figure (validated
categorical palette, 8 hues in fixed order; the 3 least central baselines in grays; references in black)."""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import study as st  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAB = os.path.join(HERE, "study_results", "tables")
FIG = os.path.join(HERE, "study_results", "figures")

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
STYLE = {
    "ours_v6": dict(color="#2a78d6", marker="o", lw=2.6, zorder=10),
    "wrr_speed": dict(color="#eb6834", marker="s"),
    "lsq": dict(color="#1baf7a", marker="^"),
    "wrr": dict(color="#eda100", marker="v"),
    "prequal_hcl": dict(color="#e87ba4", marker="D"),
    "liyanage26": dict(color="#008300", marker="P"),
    "cats_lb": dict(color="#6250d6", marker="X"),
    "expected_delay_drop": dict(color="#e34948", marker="*"),
    "dahlin_li": dict(color="#8a8985", marker="h"),
    "wpow2_stale": dict(color="#b5b4ad", marker="<"),
    "nearest": dict(color="#52514e", marker=">"),
    "oracle": dict(color=INK, marker="", ls="--", lw=1.6),
    "oracle_adm": dict(color=INK, marker="", ls=":", lw=1.6),
    "prequal_native": dict(color="#e87ba4", marker="D"),
    "lsq_sample": dict(color="#1baf7a", marker="^", ls=(0, (1, 1.6)), lw=1.8),   # an LSQ variant: same hue, dotted
}
ORDER = ["ours_v6", "wrr_speed", "lsq", "wrr", "prequal_hcl", "liyanage26", "cats_lb", "expected_delay_drop",
         "dahlin_li", "wpow2_stale", "nearest", "oracle"]
ORDER_SUPP = ORDER[:3] + ["lsq_sample"] + ORDER[3:]          # figures that also show the supplementary LSQ-Sample


def _style(alias):
    base = alias[:-4] if alias.endswith("+adm") else alias
    s = dict(STYLE.get(base, dict(color=INK2, marker=".")))
    s.setdefault("lw", 1.5)
    s.setdefault("ls", "-")
    s.setdefault("zorder", 3)
    if alias.endswith("+adm"):
        s["ls"] = (0, (4, 2))
    return s


def _label(alias):
    if alias.endswith("+adm"):
        return st.SHORT.get(alias[:-4], alias[:-4]) + " + wrapper"
    return st.SHORT.get(alias, alias)


def _setup():
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.titlesize": 10, "axes.titleweight": "bold",
                         "legend.frameon": False, "legend.fontsize": 8, "figure.dpi": 150, "savefig.dpi": 200,
                         "axes.spines.top": False, "axes.spines.right": False})


def _grid(ax):
    ax.grid(True, color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)


def _line(ax, x, y, e, alias, hollow=False):
    s = _style(alias)
    mfc = "white" if (hollow or alias.endswith("+adm")) else s["color"]
    ax.errorbar(x, y, yerr=e, color=s["color"], marker=s["marker"] or None, ms=6 if s["marker"] != "*" else 9,
                mfc=mfc, mec=s["color"], lw=s["lw"], ls=s["ls"], capsize=2, elinewidth=0.8, zorder=s["zorder"],
                label=_label(alias))


def _note_overlap(ax, d, metric, x="load", scale=100, draw=True, pos=(0.99, 0.98), va="top"):
    """Say so when DWRR and WRR coincide (no capacity change: the measured speeds equal the configured ones)."""
    a = d[d.alias == "wrr"].sort_values(x)[metric].to_numpy()
    b = d[d.alias == "wrr_speed"].sort_values(x)[metric].to_numpy()
    if len(a) and len(a) == len(b) and np.allclose(a, b, atol=0.05):
        if draw:
            ax.text(pos[0], pos[1], "DWRR overlaps WRR here (no capacity change)", transform=ax.transAxes,
                    ha="right", va=va, fontsize=7.5, color=INK2)
        return True
    return False


def _save(fig, name):
    os.makedirs(FIG, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(FIG, f"{name}.{ext}"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _legend_below(fig, axes, ncol=4):
    h, l = axes[0].get_legend_handles_labels() if isinstance(axes, (list, np.ndarray)) else axes.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=ncol, bbox_to_anchor=(0.5, -0.02), handlelength=2.6)


def fig_success_vs_load(agg):
    d = agg[(agg.pattern == "steady") & (agg.delay_ms == 50) & (agg.R == 4) & (agg.W == 2.0) & (agg.cap == "het")
            & (agg.deadline == 300) & (agg.tag == "")]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for a in ORDER:
        g = d[d.alias == a].sort_values("load")
        if len(g):
            _line(ax, g.load * 100, g.success, g.success_ci95, a)
    _note_overlap(ax, d, "success")
    ax.set_xlabel("Offered load (% of total capacity)")
    ax.set_ylabel("Deadline success (% of all frames)")
    ax.set_xticks([60, 90, 110, 130])
    ax.set_ylim(0, 100)
    ax.axvline(100, color=INK2, lw=0.8, ls=":")
    ax.set_title("Deadline success vs offered load (steady traffic, 50 ms telemetry delay)", loc="left")
    _grid(ax)
    fig.subplots_adjust(bottom=0.30)
    _legend_below(fig, ax)
    _save(fig, "fig01_success_vs_load")


def fig_p99_vs_load(agg):
    d = agg[(agg.pattern == "steady") & (agg.delay_ms == 50) & (agg.R == 4) & (agg.W == 2.0) & (agg.cap == "het")
            & (agg.deadline == 300) & (agg.tag == "")]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for a in ORDER:
        g = d[d.alias == a].sort_values("load")
        if len(g):
            _line(ax, g.load * 100, g.p99_ms, g.p99_ms_ci95, a)
    ax.axhline(300, color=INK2, lw=0.8, ls=":")
    ax.text(0.99, 302, "deadline 300 ms", color=INK2, fontsize=8, va="bottom", ha="right",
            transform=ax.get_yaxis_transform())
    _note_overlap(ax, d, "p99_ms", pos=(0.99, 0.13), va="bottom")
    ax.set_xlabel("Offered load (% of total capacity)")
    ax.set_ylabel("p99 response time of answered frames (ms)")
    ax.set_xticks([60, 90, 110, 130])
    ax.set_title("p99 latency vs offered load (answered frames only; rejected frames have none)", loc="left")
    _grid(ax)
    fig.subplots_adjust(bottom=0.30)
    _legend_below(fig, ax)
    _save(fig, "fig04_p99_vs_load")


def fig_success_vs_delay(agg):
    d = agg[(agg.pattern == "steady") & (agg.R == 4) & (agg.W == 2.0) & (agg.cap == "het") & (agg.deadline == 300)
            & (agg.tag == "")]
    xs = {0: 0, 50: 1, 200: 2, 1000: 3}
    loads = [L for L in st.LOADS if (d[np.isclose(d.load, L)].delay_ms.nunique() == len(xs))]
    if not loads:
        return
    nr = 1 if len(loads) <= 2 else 2
    nc = int(np.ceil(len(loads) / nr))
    fig, axes = plt.subplots(nr, nc, figsize=(4.8 * nc, 3.9 * nr + 1.2), sharey=True, squeeze=False)
    axes = axes.ravel()
    flags = []
    for ax, L in zip(axes, loads):
        dl = d[np.isclose(d.load, L)]
        for a in ORDER:
            g = dl[dl.alias == a].sort_values("delay_ms")
            if len(g):
                _line(ax, [xs[v] for v in g.delay_ms], g.success, g.success_ci95, a)
        flags.append(_note_overlap(ax, dl, "success", x="delay_ms", draw=False))
        ax.set_xticks(list(xs.values()), [f"{k} ms" for k in xs])
        ax.set_title(f"Offered load {int(L * 100)}%", loc="left")
        ax.set_ylim(0, 100)
        _grid(ax)
    for ax in axes[len(loads):]:
        ax.set_visible(False)
    for ax in axes[-nc:]:
        ax.set_xlabel("Telemetry delay (on top of the path delay)")
    for k in range(0, len(axes), nc):
        axes[k].set_ylabel("Deadline success (%)")
    fig.suptitle("Deadline success vs telemetry delay (reports every 2 s, steady traffic)", x=0.01, ha="left",
                 fontweight="bold", fontsize=10)
    if flags and all(flags):
        fig.text(0.01, 0.945 if nr == 2 else 0.9, "DWRR overlaps WRR in every panel (no capacity change)",
                 fontsize=8, color=INK2)
    fig.subplots_adjust(bottom=0.12 if nr == 2 else 0.30, top=0.9 if nr == 2 else 0.82, hspace=0.32)
    _legend_below(fig, list(axes[:len(loads)]), ncol=6)
    _save(fig, "fig02_success_vs_delay")


def fig_success_vs_bytes(tel):
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.6), sharey=True)
    for ax, L in zip(axes, (0.9, 1.3)):
        d = tel[tel.load == L]
        for a in ORDER_SUPP:
            g = d[(d.alias == a) & ~d.budget.str.startswith("threshold")]
            if not len(g):
                continue
            if g.bytes_per_s_per_ingress.max() <= 0:             # uses no telemetry: a reference line
                s = _style(a)
                ax.axhline(g.success.mean(), color=s["color"], lw=1.2, ls=(0, (2, 2)), zorder=1,
                           label=f"{_label(a)} " + ("(reads the true state)" if a == "oracle" else "(no telemetry)"))
                continue
            g = g.sort_values("bytes_per_s_per_ingress")
            _line(ax, g.bytes_per_s_per_ingress, g.success, g.success_ci95, a)
            th = d[(d.alias == a) & d.budget.str.startswith("threshold")]
            if len(th):
                s = _style(a)
                ax.scatter(th.bytes_per_s_per_ingress, th.success, marker=s["marker"] or "o", s=60,
                           facecolors="white", edgecolors=s["color"], linewidths=1.6, zorder=12)
        pn = d[d.alias == "prequal_native"]
        if len(pn):
            ax.scatter(pn.bytes_per_s_per_ingress, pn.success, marker="D", s=50, facecolors="white",
                       edgecolors=STYLE["prequal_hcl"]["color"], linewidths=1.6, zorder=12,
                       label="Prequal at its own 3 probes/query (over budget)")
        ax.set_xscale("log")
        ax.set_xlabel("Realized telemetry (bytes/s per ingress, log scale)")
        ax.set_title(f"Offered load {int(L * 100)}%", loc="left")
        ax.set_ylim(0, 100)
        _grid(ax)
    axes[0].set_ylabel("Deadline success (%)")
    fig.suptitle("Deadline success vs telemetry spent (budgets: reports every 10 s / 2 s / 0.5 s; hollow = "
                 "threshold reports)", x=0.01, ha="left", fontweight="bold", fontsize=10)
    fig.subplots_adjust(bottom=0.34, top=0.86)
    _legend_below(fig, axes, ncol=4)
    _save(fig, "fig03_success_vs_bytes")


def fig_drop_vs_load(agg):
    d = agg[(agg.pattern == "steady") & (agg.delay_ms == 50) & (agg.R == 4) & (agg.W == 2.0) & (agg.cap == "het")
            & (agg.deadline == 300) & (agg.tag == "")]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for a in ["ours_v6", "expected_delay_drop", "oracle_adm"]:
        g = d[d.alias == a].sort_values("load")
        if len(g):
            _line(ax, g.load * 100, g.rejected, g.rejected_ci95, a)
    wr = d[d.alias.str.endswith("+adm")]
    if len(wr):                                   # the wrapper rejects the same share whatever the routing rule
        g = wr.groupby("load").rejected.mean().sort_index()
        ax.plot(g.index * 100, g.values, color=INK2, lw=1.6, ls=(0, (4, 2)), marker="o", mfc="white", mec=INK2,
                label="Common wrapper (same share for every routing rule)")
    xs = np.linspace(60, 130, 50)
    ax.plot(xs, np.maximum(0, 1 - 100 / xs) * 100, color=INK2, lw=1.0, ls=":", label="minimum to fit capacity")
    ax.set_xlabel("Offered load (% of total capacity)")
    ax.set_ylabel("Frames rejected at the ingress (%)")
    ax.set_xticks([60, 90, 110, 130])
    ax.set_title("Rejection rate vs offered load (native admission vs common wrapper)", loc="left")
    _grid(ax)
    fig.subplots_adjust(bottom=0.30)
    _legend_below(fig, ax)
    _save(fig, "fig05_drop_vs_load")


def fig_scalability(sca):
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.4), sharey=True)
    xs = {1: 0, 4: 1, 16: 2}
    for ax, L in zip(axes, (0.9, 1.3)):
        for a in ORDER_SUPP:
            g = sca[(sca.alias == a) & (sca.load == L)].sort_values("R")
            if len(g):
                _line(ax, [xs[int(v)] for v in g.R], g.success, g.success_ci95, a)
        ax.set_xticks(list(xs.values()), [str(k) for k in xs])
        ax.set_xlabel("Independent ingress dispatchers")
        ax.set_title(f"Offered load {int(L * 100)}%", loc="left")
        ax.set_ylim(0, 100)
        _grid(ax)
    axes[0].set_ylabel("Deadline success (%)")
    fig.suptitle("Deadline success vs number of ingresses (same total traffic)", x=0.01, ha="left",
                 fontweight="bold", fontsize=10)
    fig.subplots_adjust(bottom=0.30, top=0.86)
    _legend_below(fig, axes, ncol=6)
    _save(fig, "fig06_success_vs_ingresses")


SERIES_RULES = ["ours_v6", "wrr_speed", "lsq", "wrr", "prequal_hcl", "expected_delay_drop", "oracle"]


def _mean_series(series, scen, alias):
    runs = [v for k, v in series.items() if k.startswith(f"{scen}|{alias}|")]
    if not runs:
        return None, None
    n = min(len(r["frames"]) for r in runs)
    fr = np.sum([r["frames"][:n] for r in runs], axis=0).astype(float)
    sc = np.sum([r["success"][:n] for r in runs], axis=0).astype(float)
    t = runs[0]["t0"] + np.arange(n) + 0.5
    k = 3                                          # 3-s window: ratio of summed successes to summed frames, so the
    ker = np.ones(k)                               # first and last seconds are not pulled towards zero
    sc_s = np.convolve(sc, ker, mode="same")
    fr_s = np.convolve(fr, ker, mode="same")
    sm = np.where(fr_s > 0, sc_s / np.maximum(fr_s, 1) * 100, np.nan)
    return t, sm


def fig_timeseries(series, panels, name, title):
    fig, axes = plt.subplots(1, len(panels), figsize=(4.9 * len(panels), 4.3), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, (scen, sub, spans) in zip(axes, panels):
        for t0, t1 in spans:
            ax.axvspan(t0, t1, color="#f0efec", zorder=0)
        for a in SERIES_RULES:
            t, y = _mean_series(series, scen, a)
            if t is None:
                continue
            s = _style(a)
            ax.plot(t, y, color=s["color"], lw=s["lw"] if a == "ours_v6" else 1.4, ls=s["ls"], label=_label(a),
                    zorder=s["zorder"])
        ax.set_title(sub, loc="left")
        ax.set_xlabel("Time (s)")
        ax.set_ylim(0, 102)
        _grid(ax)
    axes[0].set_ylabel("Deadline success per second (%)")
    fig.suptitle(title + " — 3-s average, mean of 10 seeds", x=0.01, ha="left", fontweight="bold", fontsize=10)
    fig.subplots_adjust(bottom=0.24, top=0.86)
    _legend_below(fig, axes, ncol=len(SERIES_RULES))
    _save(fig, name)


def fig_ablation(ab):
    if ab.empty:
        return
    pats = [p for p in ("steady", "bursty") if p in set(ab.pattern)]
    fig, axes = plt.subplots(1, len(pats), figsize=(4.9 * len(pats), 4.3), sharey=True)
    axes = np.atleast_1d(axes)
    abl = list(dict.fromkeys(ab.alias))
    colors = ["#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
    w = 0.8 / max(1, len(abl))
    for ax, pat in zip(axes, pats):
        d = ab[ab.pattern == pat]
        loads = sorted(set(d.load))
        for k, a in enumerate(abl):
            g = d[d.alias == a].set_index("load").reindex(loads)
            x = np.arange(len(loads)) + (k - (len(abl) - 1) / 2) * w
            ax.bar(x, g.v6_minus_ablation_pp, width=w * 0.92, color=colors[k % len(colors)],
                   yerr=g.ci95, capsize=2, error_kw=dict(elinewidth=0.8, ecolor=INK2), label=st.LABELS[a], zorder=3)
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_xticks(range(len(loads)), [f"{int(L * 100)}%" for L in loads])
        ax.set_xlabel("Offered load")
        ax.set_title(f"{pat.capitalize()} traffic", loc="left")
        _grid(ax)
    axes[0].set_ylabel("v6 minus ablation (percentage points)\n> 0: the mechanism helps")
    fig.suptitle("Ablation of Staleness-Aware CATS (v6): success lost when one mechanism is switched off", x=0.01,
                 ha="left", fontweight="bold", fontsize=10)
    fig.subplots_adjust(bottom=0.25, top=0.86)
    _legend_below(fig, axes, ncol=3)
    _save(fig, "fig09_ablation")


def fig_oracle_gap(main_tab):
    d = main_tab[main_tab.regime != "all"]
    if d.empty:
        return
    algs = [a for a in ORDER_SUPP if a not in ("oracle", "oracle_adm", "oracle+adm") and a in set(d.alias)]
    refs = [("oracle_gap_pp", "vs the fresh-state oracle (routing only)")]
    if "gap_vs_oracle_wrapped_pp" in d and d.gap_vs_oracle_wrapped_pp.notna().any():
        refs.append(("gap_vs_oracle_wrapped_pp", "vs the oracle + the common wrapper (supplementary)"))
    fig, axes = plt.subplots(1, len(refs), figsize=(6.0 * len(refs) + 1.4, 5.0), sharey=True)
    axes = np.atleast_1d(axes)
    y = np.arange(len(algs))
    for ax, (col, sub) in zip(axes, refs):
        for k, (reg, c) in enumerate((("below capacity (60%, 90%)", "#2a78d6"), ("overload (110%, 130%)", "#eb6834"))):
            g = d[d.regime == reg].set_index("alias").reindex(algs)
            ax.barh(y + (k - 0.5) * 0.38, g[col], height=0.36, color=c, label=reg, zorder=3)
        ax.axvline(0, color=INK2, lw=0.8)
        ax.set_title(sub, loc="left")
        ax.set_xlabel("Reference success minus algorithm success (pp)")
        _grid(ax)
    axes[0].set_yticks(y, [_label(a) for a in algs])
    axes[0].invert_yaxis()
    h, lb = axes[0].get_legend_handles_labels()
    fig.legend(h, lb, loc="lower center", ncol=2, frameon=False)
    fig.suptitle("Average gap to the fresh-state oracle over the main grid (< 0: above the reference)",
                 x=0.01, ha="left", fontweight="bold", fontsize=10)
    fig.subplots_adjust(top=0.86, bottom=0.2, wspace=0.08)
    _save(fig, "fig10_oracle_gap")


def main():
    _setup()
    agg = pd.read_csv(os.path.join(TAB, "agg_by_scenario.csv"), keep_default_na=False, na_values=[""])
    agg["tag"] = agg["tag"].fillna("")
    main_tab = pd.read_csv(os.path.join(TAB, "main_comparison.csv"))
    tel = pd.read_csv(os.path.join(TAB, "telemetry_efficiency.csv"))
    sca = pd.read_csv(os.path.join(TAB, "scalability.csv"))
    ab = pd.read_csv(os.path.join(TAB, "ablation.csv")) if os.path.getsize(os.path.join(TAB, "ablation.csv")) > 5 \
        else pd.DataFrame()
    with open(os.path.join(TAB, "_series.json")) as f:
        series = json.load(f)
    fig_success_vs_load(agg)
    fig_success_vs_delay(agg)
    fig_success_vs_bytes(tel)
    fig_p99_vs_load(agg)
    fig_drop_vs_load(agg)
    fig_scalability(sca)
    b = st.make(0.9, 0.05, "bursty").key
    b11 = st.make(1.1, 0.05, "bursty").key
    bursts = [(t, t + st.BURST_LEN) for t in st.BURSTS]
    fig_timeseries(series, [(b, "Bursty traffic, load 90%", bursts), (b11, "Bursty traffic, load 110%", bursts)],
                   "fig07_adaptation_bursts", "Adaptation to traffic bursts (shaded: 5 s at twice the base rate)")
    fk = st.make(0.9, 0.05, "steady", extra=st.FAIL, tag="fail").key
    sk = st.make(0.9, 0.05, "steady", extra=st.SLOW, tag="slow").key
    ck = st.make(0.9, 0.05, "steady", extra=st.CONG, tag="congest").key
    panels = [(fk, "Core-2 loses half its GPUs (40-70 s)", [st.EVENT_TIMES["fail"]]),
              (sk, "Regional sites at half speed (35-70 s)", [st.EVENT_TIMES["slow"]])]
    if any(k.startswith(ck + "|") for k in series):
        panels.append((ck, "Paths to Core-2 twice as slow (40-70 s)", [st.EVENT_TIMES["congest"]]))
    fig_timeseries(series, panels, "fig08_failure_recovery",
                   "Server failure, slowdown and path-delay change at load 90% (shaded: the event)")
    fig_ablation(ab)
    fig_oracle_gap(main_tab)
    print(f"figures -> {FIG}")
