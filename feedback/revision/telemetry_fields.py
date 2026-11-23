"""Telemetry recomputed with a report defined field by field, headers included (added after the freeze, 23 Nov 2026).

    python3 feedback/revision/telemetry_fields.py      -> feedback/revision/telemetry.md, feedback/revision/telemetry.csv

Why no new runs are needed
- The frozen simulator charges a fixed 62 B per report (catsim/config.py, report_bytes), plus 4 B for the arrivals
  counter A and 2 B for the drop sum D. No rule of Batches A, B or D uses the report size to decide anything: it is
  only counted (catsim/engine.py, one_report). Only the probing baselines of the earlier study read it.
- Every report of a run has the same size, so the bytes of a run scale exactly: new = old x new size / old size.
  The 2-byte drop count an ingress writes on a frame it sends anyway (echo bytes) is unchanged.
- catsim/config.py is frozen (FREEZE_v6.1.md) and the report size is part of every run's name, so it is not changed;
  the stored results are rescaled instead.

The report, field by field (one service, one report per site per W seconds to every ingress)
"""
import csv
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
import catsim.rules            # noqa: E402,F401  (registers the rules)
import catsim.rules_v62        # noqa: E402,F401
from catsim.baselines import resolve_rule   # noqa: E402

# (field, bytes, which rules, why)
FIELDS = [
    ("IPv6 header", 40, "all report rules", "fixed IPv6 header (RFC 8200); link-layer headers vary per hop and are not counted"),
    ("UDP header", 8, "all report rules", "RFC 768"),
    ("Service ID", 2, "all report rules", "which service the report is for (one service here; room for 65,535)"),
    ("Frames at the site q_s", 2, "all report rules", "unsigned; a run has at most 40,875 frames, below 65,535"),
    ("Time measured t_s", 8, "all report rules", "64-bit NTP timestamp format (RFC 5905)"),
    ("Arrivals since last report A_s", 4, "rules with the counter", "as frozen"),
    ("Sum of drop counts D_s", 2, "v6.1, v6.2, admission rivals", "as frozen"),
]
BASE_NEW = sum(b for _, b, who, _ in FIELDS if who == "all report rules")       # 60
COUNTER = 4
ECHO = 2
BASE_OLD = 62

NETS = {"beirut": ("Beirut", 3, 5.0), "eight": ("8 sites", 8, 2.0), "new": ("New", 5, 3.0)}
SHOW = [("ours_v62", "v6.2"), ("ours_v61", "v6.1"), ("ours_v6", "v6"), ("wrr+adm61@U=0.9,EWMA=1", "Tuned rival"),
        ("wrr+adm61", "Frozen rival"), ("wrr", "Round-robin")]


def sizes(rule):
    cls = resolve_rule(rule)
    if not cls.uses_reports:
        return 0, 0
    extra = (COUNTER if cls.uses_counter else 0) + (ECHO if getattr(cls, "uses_drop_echo", False) else 0)
    return BASE_OLD + extra, BASE_NEW + extra


def main():
    rows_out = []
    agg = defaultdict(lambda: [0.0, 0.0, 0.0, 0])          # (batch, net, rule) -> old total, new total, echo, n
    for batch in "ABD":
        path = os.path.join(ROOT, "feedback", "final", f"batch_{batch}.csv")
        for r in csv.DictReader(open(path)):
            old_one, new_one = sizes(r["rule"])
            rep = float(r["report_bytes_per_s_per_ingress"])
            echo = float(r["echo_bytes_per_s_per_ingress"])
            total = float(r["bytes_per_s_per_ingress"])
            assert abs(rep + echo - total) < 1e-6, (batch, r["scenario"], r["rule"], r["seed"])
            rep_new = rep * new_one / old_one if old_one else 0.0
            rows_out.append(dict(batch=batch, net=r["net"], scenario=r["scenario"], rule=r["rule"], seed=r["seed"],
                                 report_bytes_old=old_one, report_bytes_new=new_one,
                                 bytes_per_s_per_ingress_old=round(total, 4),
                                 bytes_per_s_per_ingress_new=round(rep_new + echo, 4)))
            a = agg[(batch, r["net"], r["rule"])]
            a[0] += total
            a[1] += rep_new + echo
            a[2] += echo
            a[3] += 1

    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "telemetry.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0]))
        w.writeheader()
        w.writerows(rows_out)

    L = ["# Telemetry with the report defined field by field, headers included",
         "",
         "- Added after the freeze (23 Nov 2026). Written by `feedback/revision/telemetry_fields.py` from "
         "`feedback/final/batch_{A,B,D}.csv`. No run was redone: the report size is only counted, never used by a "
         "rule of Batches A, B or D, so every success number is unchanged.",
         "- The frozen accounting (62 B per report + 4 + 2) stays in `feedback/final.md`, Table 8.",
         "",
         "## The report",
         "",
         "| Field | Bytes | Sent by | Why this size |",
         "|---|---|---|---|"]
    for name, b, who, why in FIELDS:
        L.append(f"| {name} | {b} | {who} | {why} |")
    L += [f"| **One report** | **{BASE_NEW + COUNTER + ECHO}** (v6.1, v6.2, admission rivals); "
          f"**{BASE_NEW + COUNTER}** (v6) | | frozen accounting: {BASE_OLD + COUNTER + ECHO} and {BASE_OLD + COUNTER} |",
          f"| Own drop count (ingress to site) | {ECHO} | v6.1, v6.2, admission rivals | written on a frame sent "
          f"anyway, at most every W/4: no header of its own |",
          "",
          "## Bytes per second per ingress",
          "",
          "Formula: S x (one report) / W. Measured: mean over all runs of Batch A (20 seeds), reports plus drop counts.",
          "",
          "| Network (S, W) | Formula, v6.2 | " + " | ".join(n for _, n in SHOW) + " | v6.2 vs v6 |",
          "|---|---|" + "---|" * (len(SHOW) + 1)]
    for key, (name, S, W) in NETS.items():
        cells = []
        for rule, _ in SHOW:
            a = agg.get(("A", key, rule))
            cells.append("-" if not a else f"{a[1] / a[3]:.1f}")
        a62, a6 = agg[("A", key, "ours_v62")], agg[("A", key, "ours_v6")]
        rel = (a62[1] / a62[3]) / (a6[1] / a6[3]) - 1
        L.append(f"| {name} ({S}, {W:g} s) | {S * (BASE_NEW + COUNTER + ECHO) / W:.1f} | " + " | ".join(cells)
                 + f" | +{100 * rel:.1f}% |")
    L += ["",
          "Same table with the frozen accounting (62 B + 4 + 2), for comparison:",
          "",
          "| Network | Formula, v6.2 | " + " | ".join(n for _, n in SHOW) + " | v6.2 vs v6 |",
          "|---|---|" + "---|" * (len(SHOW) + 1)]
    for key, (name, S, W) in NETS.items():
        cells = []
        for rule, _ in SHOW:
            a = agg.get(("A", key, rule))
            cells.append("-" if not a else f"{a[0] / a[3]:.1f}")
        a62, a6 = agg[("A", key, "ours_v62")], agg[("A", key, "ours_v6")]
        rel = (a62[0] / a62[3]) / (a6[0] / a6[3]) - 1
        L.append(f"| {name} | {S * (BASE_OLD + COUNTER + ECHO) / W:.1f} | " + " | ".join(cells) + f" | +{100 * rel:.1f}% |")

    # why measured is below the formula: report rounds in a run, and the drop counts
    L += ["",
          "## Why the measured value is below the formula",
          "",
          "- A report's bytes are counted when it is sent, lost or not (`catsim/engine.py`), so losses do not lower it.",
          "- A run of T seconds holds fewer than T / W rounds of reports (on Beirut, 29 rounds in 150 s, not 30).",
          "- The drop counts the ingresses write on their frames add a little (Batch A, v6.2):"]
    for key, (name, S, W) in NETS.items():
        a = agg[("A", key, "ours_v62")]
        L.append(f"  - {name}: reports {(a[1] - a[2]) / a[3]:.2f} + drop counts {a[2] / a[3]:.2f} = {a[1] / a[3]:.2f} B/s")
    L += ["", "Every other batch: `telemetry.csv` (one row per run, old and new bytes/s)."]
    open(os.path.join(out_dir, "telemetry.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
