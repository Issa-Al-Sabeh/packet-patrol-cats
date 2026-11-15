"""Figure for the LSQ diagnostic: the fullest and the emptiest site over 20 seconds, three settings (python3 plot_lsq.py).
Colours: slots 1 and 2 of the validated categorical palette (checked with the dataviz validator, light surface)."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
z = np.load(os.path.join(HERE, "lsq_traj.npz"))
t = z["t"]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
HI, LO = "#2a78d6", "#eb6834"
import csv
with open(os.path.join(HERE, "lsq.csv")) as f:
    rows = list(csv.DictReader(f))


def ok(rule, W):
    return np.mean([float(r["success"]) for r in rows if r["rule"] == rule and float(r["W"]) == W])


PANELS = [("lsq|0.5", f"Shared reports every 0.5 s (the baseline as built): {ok('lsq', 0.5):.0f}% on time"),
          ("lsq_poll_phase|0.5", "Same information every 0.5 s, each ingress at its own moment: "
                                 f"{ok('lsq_poll_phase', 0.5):.0f}% on time"),
          ("lsq|10", f"Shared reports every 10 s: {ok('lsq', 10.0):.0f}% on time")]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK})
fig, axes = plt.subplots(3, 1, figsize=(8.4, 7.4), sharex=True, sharey=True, facecolor=SURFACE)
top = max(float(z[k].max()) for k, _ in PANELS)
for ax, (key, title) in zip(axes, PANELS):
    q = z[key]                                   # frames in the system per GPU, one row per site
    hi, lo = q.max(axis=0), q.min(axis=0)
    ax.set_facecolor(SURFACE)
    ax.plot(t, hi, color=HI, lw=2, label="Fullest site", solid_capstyle="round")
    ax.plot(t, lo, color=LO, lw=2, label="Emptiest site", solid_capstyle="round")
    ax.axhline(1.0, color=INK2, lw=1, ls=(0, (2, 3)), label="Every GPU busy, nothing waiting")
    ax.set_title(title, loc="left", fontsize=10.5, color=INK, pad=6)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    ax.set_ylim(0, top * 1.05)
    ax.set_xlim(t[0], t[-1])
    ax.set_xticks(np.arange(40, 61, 5))
h, lab = axes[0].get_legend_handles_labels()
fig.legend(h, lab, loc="upper left", ncol=3, frameon=False, fontsize=9, handlelength=1.8, bbox_to_anchor=(0.055, 0.895))
axes[1].set_ylabel("Frames at the site, per GPU")
axes[-1].set_xlabel("Time in the run (s)")
fig.suptitle("LSQ on shared reports: the sites take turns being flooded only when every ingress\n"
             "gets the same picture at the same moment (8 sites, 4 ingresses, 90% load; run of seed 201,\n"
             "on-time shares are means of 5 seeds)",
             x=0.065, ha="left", fontsize=11.5, color=INK, y=0.99)
fig.subplots_adjust(left=0.075, right=0.975, top=0.815, bottom=0.07, hspace=0.32)
fig.savefig(os.path.join(HERE, "lsq_queues.png"), dpi=160, facecolor=SURFACE)
print("lsq_queues.png written; per-GPU queue: max", round(top, 1))
