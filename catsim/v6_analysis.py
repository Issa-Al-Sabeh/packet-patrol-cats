"""Analysis of the v6 study (fresh seeds 201-210): paired comparisons, gaps to the best rule, ablations.
Writes results_v6/tables/*.csv and results_v6/analysis_v6.json (used by the report page)."""
import csv
import json
import os
from collections import defaultdict

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRACTICAL = ["ours_v6", "ours_v5", "ours_v2_speed", "v4", "wrr", "wrr_speed", "wrr_drop", "wrr_speed_drop", "lsq"]
RIVALS = ["ours_v5", "ours_v2_speed", "v4", "wrr", "wrr_speed", "wrr_drop", "wrr_speed_drop", "lsq",
          "expected_delay_drop", "v4_nodrop", "oracle"]
ABL = ["ours_v6_nobal", "ours_v6_noburst", "ours_v6_nocal"]
FAMS = ["beirut", "large", "overload"]


def paired(a, b):
    d = np.array(a) - np.array(b)
    h = stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d))
    return float(d.mean()), float(h)


def main():
    rows = list(csv.DictReader(open(os.path.join(HERE, "results_v6", "tables", "summary_v6.csv"))))
    seeds = defaultdict(dict)
    meta = {}
    for r in rows:
        seeds[r["test"]][r["rule"]] = [float(x) for x in r["seeds"].split()]
        meta[r["test"]] = (r["label"], r["group"], r["family"])
    tests = list(seeds)
    out = {"tests": [], "h2h": {}, "gaps": {}, "ablation": {}, "fam_titles": {
        "beirut": "Beirut, 36 tests", "large": "Large network, 12 tests", "overload": "Overload, 13 tests"}}
    # per test
    for t in tests:
        lab, grp, fam = meta[t]
        m = {r: float(np.mean(v)) for r, v in seeds[t].items()}
        out["tests"].append({"id": t, "label": lab, "group": grp, "family": fam, "miss": {r: round(v, 3) for r, v in m.items()},
                             "dropped_v6": None})
    # head to head per family
    for rv in RIVALS + ABL:
        res = {f: [0, 0, 0] for f in FAMS}
        for t in tests:
            if rv not in seeds[t] or "ours_v6" not in seeds[t]:
                continue
            d, h = paired(seeds[t]["ours_v6"], seeds[t][rv])
            fam = meta[t][2]
            res[fam][0 if d + h < 0 else (2 if d - h > 0 else 1)] += 1
        out["h2h"][rv] = res
    # gaps to the best practical rule (tests where all practical rules ran)
    for r in PRACTICAL:
        gaps = []
        worst = (0.0, "")
        for t in tests:
            if not all(p in seeds[t] for p in PRACTICAL):
                continue
            best = min(np.mean(seeds[t][p]) for p in PRACTICAL)
            g = float(np.mean(seeds[t][r]) - best)
            gaps.append(g)
            if g > worst[0]:
                worst = (g, meta[t][0])
        gaps = np.array(gaps)
        out["gaps"][r] = {"avg": round(float(gaps.mean()), 3), "worst": round(worst[0], 3), "worst_test": worst[1],
                          "near": int((gaps <= 0.5).sum()), "n": int(len(gaps)),
                          "best": int((gaps <= 1e-9).sum())}
    # ablations: switching one change off, change in miss (pts), pooled over tests per family
    for a in ABL:
        res = {}
        for f in FAMS:
            ds = []
            for t in tests:
                if meta[t][2] == f and a in seeds[t]:
                    ds += list(np.array(seeds[t][a]) - np.array(seeds[t]["ours_v6"]))
            ds = np.array(ds)
            h = stats.t.ppf(0.975, len(ds) - 1) * ds.std(ddof=1) / np.sqrt(len(ds))
            res[f] = [round(float(ds.mean()), 3), round(float(h), 3)]
        out["ablation"][a] = res
    json.dump(out, open(os.path.join(HERE, "results_v6", "analysis_v6.json"), "w"), indent=1)
    names = {"ours_v5": "v5", "ours_v2_speed": "v2+speeds", "v4": "v4", "wrr": "RR", "wrr_speed": "RR+speeds",
             "wrr_drop": "RR+drop", "wrr_speed_drop": "RR+speeds+drop", "lsq": "LSQ", "expected_delay_drop": "ED+drop",
             "v4_nodrop": "v4 no drop", "oracle": "Fresh-state greedy", "ours_v6_nobal": "v6 w/o A", "ours_v6_noburst": "v6 w/o B",
             "ours_v6_nocal": "v6 w/o C", "ours_v6": "v6"}
    print("v6 vs each rule (lower / same / higher), Beirut | Large | Overload")
    for rv, res in out["h2h"].items():
        print(f"  {names[rv]:16s} " + " | ".join("/".join(map(str, res[f])) for f in FAMS))
    print("\nGap to the best practical rule")
    for r in sorted(PRACTICAL, key=lambda r: out["gaps"][r]["avg"]):
        g = out["gaps"][r]
        print(f"  {names[r]:16s} avg {g['avg']:5.2f}  worst {g['worst']:6.2f} ({g['worst_test']})  near-best {g['near']}/{g['n']}")
    print("\nAblations (miss without the change - with it), pts: Beirut | Large | Overload")
    for a, res in out["ablation"].items():
        print(f"  {names[a]:16s} " + " | ".join(f"{res[f][0]:+.2f} +-{res[f][1]:.2f}" for f in FAMS))


if __name__ == "__main__":
    main()
