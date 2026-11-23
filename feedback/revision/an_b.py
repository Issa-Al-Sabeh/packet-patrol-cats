"""Section V-B of the paper: planned vs realised site rates (Batch B, seed 301). Reads traces written by trace.py.

    python3 feedback/revision/an_b.py

For each ingress and site: (the ingress's planned share x its estimate of the total), averaged over the run, divided
by the frames per second the site really received from all ingresses together. 1.00 = the plans add up.
"""
import csv
import glob
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
B = {(r['scenario'], r['rule'], r['seed']): float(r['success'])
     for r in csv.DictReader(open(os.path.join(ROOT, "feedback", "final", "batch_B.csv")))}
for f in sorted(glob.glob(os.path.join(HERE, "traces", "trace_B_*_301.json"))):
    d = json.load(open(f)); secs = np.array(d['secs']); real = np.array(d['real'])
    realized = real.mean(0)                     # frames/s each site received from all ingresses
    stored = B.get((d['key'], d['rule'], '301'))
    rows = []
    for tr in d['rules']:
        P = np.array([r['p'] for r in tr if r['t'] >= secs[0] and r['p'] is not None])
        E = np.array([r['est'] for r in tr if r['t'] >= secs[0] and r['p'] is not None])
        rows.append((P * E[:, None]).mean(0) / realized)
    rows = np.array(rows)
    print(f"{d['key']:34s} {d['rule']:9s} success {d['success'] * 100:5.1f} (stored {stored:5.1f})  "
          f"planned/realised, all ingresses and sites: {rows.min():.2f}-{rows.max():.2f}; median {np.median(rows):.2f}")
