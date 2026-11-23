"""Section III-E of the paper (Batch C diagnosis, pilot seed 101): what v6.1 / v6.2 believe after a burst and after the
DC's servers return. Reads traces written by trace.py.

    python3 feedback/revision/an_c.py [trace files ...]     (default: every traces/trace_A_*_101.json)

Every 5 s from 45 to 140 s: the ingress's estimate of offered traffic, the truth over the last 5 s, its drop share,
the admitted fraction and each site's utilisation over the last 5 s, the calibration factor k and the meter's servers.
"""
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
files = sys.argv[1:] or sorted(glob.glob(os.path.join(HERE, "traces", "trace_A_*_101.json")))
for f in files:
    d = json.load(open(f)); secs = np.array(d['secs']); real = np.array(d['real']); off = np.array(d['offered'])
    tr = d['rules'][0]                                  # ingress A
    print(os.path.basename(f), 'servers', d['servers'], 'success', round(d['success'] * 100, 1))
    for row in tr:
        t = row['t']
        if t < 45 or t > 140 or int(t) % 5:
            continue
        k = np.searchsorted(secs, int(t))
        lo = max(0, k - 5)
        if k <= lo:
            continue
        true = off[lo:k].mean()
        adm = real[lo:k].sum(1).mean() / true
        util = real[lo:k].mean(0) / (np.array(d['servers']) * 10)
        print(f" t={t:5.0f} est={row['est']:6.1f} true={true:6.1f} r={row['est'] / true:4.2f} drop={row['pd']:.2f} "
              f"admitted={adm:.2f} kcal={row['kcal']:.3f} meter={row['meter']} util(nominal)={np.round(util, 2)}")
