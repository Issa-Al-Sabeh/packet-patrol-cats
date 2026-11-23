"""Section IV of the paper (Simulator): the built-in Erlang C check (catsim/checks.py, check 1), full length.

    python3 feedback/revision/erlang.py      -> prints the check, writes feedback/revision/results/erlang.json

One site, Poisson arrivals, exponential jobs, 85% load, c = 2, 4, 8 servers: simulated mean time and P(time > 300 ms)
against the M/M/c formulas, five seeds of 3,000 s each.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
import catsim.rules                          # noqa: E402,F401  (registers rules)
from catsim.checks import check_engine      # noqa: E402

rows = check_engine(quick=False)
os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
json.dump(rows, open(os.path.join(HERE, "results", "erlang.json"), "w"), indent=1)
