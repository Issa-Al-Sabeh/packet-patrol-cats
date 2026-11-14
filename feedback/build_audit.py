"""Builds feedback/audit.md from audit_src.md: every [[file a-b]] becomes a verbatim quote of the frozen file, and
every class and line reference in the note is checked against the frozen code.

    python3 build_audit.py --frozen /path/to/v6-frozen
"""
import argparse
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CLASSES = {  # (file, class or def name): first line, last line -- as cited in the baseline table and section 10
    ("rules.py", "class Nearest"): (64, 68), ("rules.py", "class WRR"): (79, 91),
    ("rules.py", "class WRRSpeed"): (740, 785), ("rules.py", "class WPow2Stale"): (132, 142),
    ("baselines.py", "class DahlinLI"): (289, 337), ("rules.py", "class LSQ"): (145, 170),
    ("baselines.py", "class LSQSample"): (440, 471), ("baselines.py", "class PrequalHCL"): (31, 154),
    ("baselines.py", "class Liyanage26"): (158, 261), ("baselines.py", "class CatsLB"): (355, 422),
    ("rules_v5.py", "class ExpectedDelayDrop"): (442, 460), ("rules_v6.py", "class SplitV6"): (32, 257),
    ("rules.py", "class Oracle"): (965, 987), ("baselines.py", "class OracleAdm"): (426, 436),
    ("baselines.py", "class AdmissionWrapper"): (475, 553), ("rules_v5.py", "class SplitDrop"): (50, 223),
    ("rules.py", "class SplitSpeed"): (642, 737), ("rules_v5.py", "class TeammateV4"): (233, 314),
    ("rules_v5.py", "class WRRDrop"): (323, 386), ("rules_v5.py", "class WRRSpeedDrop"): (389, 439),
    ("rules_v5.py", "class OwnDrops"): (17, 40), ("rules_v5.py", "def _offered"): (43, 46),
    ("rules.py", "class SpeedMeter"): (520, 626), ("rules.py", "def usable_capacity"): (629, 639),
    ("queueing.py", "class Ager"): (118, 153), ("queueing.py", "def fluid"): (200, 223),
}
ANCHORS = {  # (file, line): text that must be on that line
    ("rules_v6.py", 73): "r = A / self.W / (1.0 - self.own_log.share(g - self.W, g))",
    ("rules_v6.py", 76): "self.RISE_Z * math.sqrt",
    ("rules_v6.py", 79): "self.EWMA * r + (1 - self.EWMA) * self.rate_off[s]",
    ("rules_v6.py", 87): "def _window_rate",
    ("rules_v6.py", 127): "self.useless = ",
    ("rules_v6.py", 132): "kappa = rho / (1.0 - rho)",
    ("rules_v6.py", 137): "overload = total >",
    ("rules_v6.py", 138): "may_drop = ",
    ("rules_v6.py", 143): "age = 0.0 if self.no_age",
    ("rules_v6.py", 154): "sel_c.append(lv * np.minimum(1.0, ks * r) + back)",
    ("rules_v6.py", 203): "A: balance unless the plan clearly wins",
    ("rules_v5.py", 442): "class ExpectedDelayDrop(BeliefRule)",
    ("rules.py", 580): "served_w = A - X - (q - q0)",
    ("rules.py", 667): "late = self.ctx.late_for(self.i, s, c)",
    ("rules.py", 669): "n_safe = ",
    ("rules.py", 751): "self.meter = SpeedMeter(",
    ("baselines.py", 194): "ctx.ingress_rate[i]",
    ("baselines.py", 514): "_offered(self.own_log",
    ("baselines.py", 519): "room = self.U * float(self.cap.sum())",
    ("engine.py", 53): "TRUE_STATE = ",
    ("engine.py", 186): "late = [[late_table(",
    ("engine.py", 431): "elif ev == REPORT_GEN",
    ("engine.py", 467): "rules[a].on_report_x(",
    ("engine.py", 470): "rules[a].on_reply(",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen", required=True)
    a = ap.parse_args()
    src = {}

    def lines(name):
        if name not in src:
            with open(os.path.join(a.frozen, "catsim", name)) as f:
                src[name] = f.read().split("\n")
        return src[name]

    n_checks = 0
    for (name, head), (lo, hi) in CLASSES.items():
        L = lines(name)
        assert L[lo - 1].startswith(head), (name, head, lo, L[lo - 1])
        nxt = next(k for k in range(lo, len(L)) if L[k] and not L[k][0].isspace() and not L[k].startswith(")"))
        last = max(k for k in range(lo - 1, nxt) if L[k].strip()) + 1
        assert last == hi, (name, head, hi, last)
        n_checks += 1
    for (name, ln), text in ANCHORS.items():
        assert text in lines(name)[ln - 1], (name, ln, lines(name)[ln - 1])
        n_checks += 1

    with open(os.path.join(HERE, "audit_src.md")) as f:
        doc = f.read()
    quotes = 0

    def quote(m):
        nonlocal quotes
        name, lo, hi = m.group(1), int(m.group(2)), int(m.group(3))
        L = lines(name)
        assert 1 <= lo <= hi <= len(L), (name, lo, hi)
        body = L[lo - 1:hi]
        assert body[0].strip() and body[-1].strip(), (name, lo, hi)
        indent = min(len(x) - len(x.lstrip()) for x in body if x.strip())
        body = [x[indent:] for x in body]
        quotes += 1
        rng = f"line {lo}" if lo == hi else f"lines {lo}–{hi}"
        return f"`catsim/{name}`, {rng}:\n\n```python\n" + "\n".join(body) + "\n```"

    out = re.sub(r"\[\[(\S+\.py) (\d+)-(\d+)\]\]", quote, doc)
    assert not re.search(r"\[\[\S+\.py \d", out)
    for name, lo, hi in re.findall(r"`(\w+\.py)` (\d+)(?:–(\d+))?", out):       # every inline line reference exists
        L = lines(name)
        assert int(hi or lo) <= len(L) and L[int(lo) - 1].strip(), (name, lo, hi)
        n_checks += 1
    with open(os.path.join(HERE, "audit.md"), "w") as f:
        f.write(out)
    print(f"audit.md written: {quotes} quotes, {n_checks} line references checked, {len(out.splitlines())} lines")


if __name__ == "__main__":
    main()
