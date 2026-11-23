"""Every number added in the paper revision of 23 Nov 2026, in one command (about 1-2 minutes on one core).

    python3 feedback/revision/run_all.py

Writes the printed output of each step to feedback/revision/results/*.txt (the committed copies are the ones the
paper quotes) and the traces to feedback/revision/traces/ (not committed; re-created here).
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
PY = sys.executable

BATCH_B = ["O_130", "B_130_stagger", "O_130_W1", "L130_d50_steady_W0.5_R4_het_D300", "N_130", "O_surge"]
STEPS = [
    ("telemetry", [["telemetry_fields.py"]]),
    ("breakdown", [["breakdown.py"]]),
    ("batchC_traces", [["trace.py", "A", "O_burst", "ours_v61", "101"],
                       ["trace.py", "A", "O_burst", "ours_v62", "101"],
                       ["trace.py", "A", "O_dc_half", "ours_v62", "101"],
                       ["an_c.py"]]),
    ("batchB_planned_vs_realised", [["trace.py", "B", sc, rule, "301"] for sc in BATCH_B for rule in ("ours_v62", "ours_v6")]
                                   + [["an_b.py"]]),
    ("erlang", [["erlang.py"]]),
]

os.makedirs(RES, exist_ok=True)
for name, cmds in STEPS:
    out = []
    for c in cmds:
        print("$ python3 feedback/revision/" + " ".join(c), flush=True)
        p = subprocess.run([PY, os.path.join(HERE, c[0])] + c[1:], capture_output=True, text=True)
        if p.returncode != 0:
            sys.exit(p.stdout + p.stderr)
        out.append("$ python3 feedback/revision/" + " ".join(c) + "\n" + p.stdout)
    open(os.path.join(RES, name + ".txt"), "w").write("\n".join(out))
print("done: feedback/revision/results/")
