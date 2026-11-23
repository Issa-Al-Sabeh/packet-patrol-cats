"""Table VI of the paper: every frame of Batch A by outcome (on time / dropped at the ingress / discarded at a site / late).

    python3 feedback/revision/breakdown.py [feedback/final/batch_A.csv]

Reads the stored runs only (no simulation). Groups of scenarios as in feedback/final.md; 20 seeds (301-320);
v6.2 - tuned rival is paired by seed, with a 95% Student-t interval (19 degrees of freedom).
"""
import collections
import csv
import math
import os
import sys

import numpy as np
from scipy import stats

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "feedback", "final", "batch_A.csv")
R = list(csv.DictReader(open(path)))
G = {
    'Capacity differs (4)': ['server_fail_recover', 'O_dc_half', 'wrong_weights', 'N_fail'],
    'Bursts and a surge (6)': ['O_burst', 'O_surge', 'L90_d50_bursty_W2_R4_het_D300', 'L110_d50_bursty_W2_R4_het_D300',
                               'L130_d50_bursty_W2_R4_het_D300', 'N_burst'],
    'Steady >=95% (9)': ['load=95', 'O_110', 'O_130', 'O_150', 'L110_d50_steady_W2_R4_het_D300',
                         'L130_d50_steady_W2_R4_het_D300', 'N_95', 'N_115', 'N_130'],
    'Steady 85-90% (3)': ['main', 'L90_d50_steady_W2_R4_het_D300', 'N_85'],
}
G['All (22)'] = sum(G.values(), [])
rules = {'v6.2': 'ours_v62', 'v6.1': 'ours_v61', 'Tuned': 'wrr+adm61@U=0.9,EWMA=1', 'Frozen': 'wrr+adm61', 'RR': 'wrr'}
bad = 0
D = collections.defaultdict(dict)
for r in R:
    f = int(r['frames']); s = int(r['n_success']); l = int(r['n_late']); e = int(r['n_expired']); j = int(r['n_rejected'])
    if s + l + e + j != f:
        bad += 1
    D[(r['scenario'], r['rule'])][int(r['seed'])] = np.array([s, j, e, l]) / f * 100
print('rows not adding up:', bad)
seeds = range(301, 321)
for g, scs in G.items():
    print(g)
    per = {}
    for name, rule in rules.items():
        arr = np.array([np.mean([D[(sc, rule)][sd] for sc in scs], axis=0) for sd in seeds])  # seeds x 4
        per[name] = arr
        m = arr.mean(0)
        print(f"  {name:7s} on-time {m[0]:5.1f}  dropped {m[1]:5.1f}  discarded {m[2]:5.1f}  late {m[3]:5.1f}  "
              f"late+disc {m[2] + m[3]:5.1f}")
    d = per['v6.2'] - per['Tuned']
    h = stats.t.ppf(0.975, 19) * d.std(0, ddof=1) / math.sqrt(20)
    print('  v6.2-Tuned', ' '.join(f"{a:+.1f}±{b:.1f}" for a, b in zip(d.mean(0), h)))
    for name in ('v6.2', 'Tuned'):
        a = per[name].mean(0); adm = 100 - a[1]
        print(f"  {name} admitted {adm:.1f}%, of which missed {(a[2] + a[3]) / adm * 100:.1f}%")
