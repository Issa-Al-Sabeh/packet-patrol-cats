"""The staleness-aware CATS study (Nov 2026): topology, traffic patterns, experiments, pilot and frozen parameters.

Question: does Staleness-Aware CATS (our rule, ours_v6) improve deadline success with several independent ingresses and
old telemetry, at the same telemetry budget as the strongest existing methods?

TIME SCALES (kept from the Packet Patrol study, where they were set from the application, AI inference on camera
frames): one frame = one GPU job of 100 ms on average (gamma, squared coefficient of variation 0.25); round trips 8-60 ms;
deadline 300 ms end to end (strict) or 500 ms (relaxed). The pilot (seeds 101-105) checks that these give a sensible
range: near-perfect success at 60% load for the good rules, heavy losses at 130% for every rule.

TOPOLOGY: 8 service sites ("servers"), each a GPU pool with one FCFS queue: 1, 2, 2, 3, 4, 5, 7 and 8 GPUs (32 in all;
homogeneous variant: 4 each). Small edge sites are near the ingresses, big regional and core sites far (delay_matrix).
4 ingresses by default (1 and 16 in the scalability test), unequal traffic (40/30/20/10% with 4).
TELEMETRY: each site reports (frames in the system, time measured, 4-byte arrivals counter) every W = 2 s to every
ingress (medium budget; low = 10 s, high = 0.5 s); report delay 0 / 50 / 200 / 1000 ms on top of the path delay.
Probing rules get exactly the bytes of a rule that receives every report with the counter.
SITES are deadline-aware: a frame whose deadline passed before its service starts is discarded (expired).
"""
import json
import os
from dataclasses import replace

from .config import Scenario

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS_FILE = os.path.join(HERE, "study_results", "frozen_params.json")
CONFIG_FILE = os.path.join(HERE, "study_config.json")      # every study parameter (editable)
with open(CONFIG_FILE) as _f:
    CFG = json.load(_f)

SEEDS_FINAL = tuple(CFG["seeds_final"])
SEEDS_PILOT = tuple(CFG["seeds_pilot"])
SERVERS_HET = tuple(CFG["servers_heterogeneous"])
SERVERS_HOM = tuple(CFG["servers_homogeneous"])
SITE_NAMES = tuple(CFG["site_names"])
LOADS = tuple(CFG["loads"])
DELAYS = tuple(CFG["telemetry_delays_s"])                  # telemetry delay, seconds
PATTERNS = tuple(CFG["patterns"])
BUDGET_W = dict(CFG["report_interval_s"])
SIM_TIME, WARMUP = float(CFG["sim_time_s"]), float(CFG["warmup_s"])
BURSTS = tuple(CFG["bursts_start_s"])                      # bursty: BURST_LEN s at BURST_X x the base rate
BURST_LEN, BURST_X = float(CFG["burst_len_s"]), float(CFG["burst_factor"])
SHIFT_EVERY = float(CFG["shift_every_s"])                  # shifting: the ingress shares rotate this often
RTT = CFG["rtt_ms"]
DEADLINE_STRICT, DEADLINE_RELAXED = float(CFG["deadline_ms_strict"]), float(CFG["deadline_ms_relaxed"])


def delay_matrix(R):
    """Round trips (ms) from each ingress to the 8 sites: its own edge site 8 ms, the other edges 18-22 ms; its
    nearer regional site 25 ms, the other 35 ms; its nearer core site 50 ms, the other 60 ms."""
    rows = []
    for i in range(R):
        row = [RTT["own_edge"] if j == i % 4 else RTT["other_edge_base"] + RTT["other_edge_step"] * ((i + j) % 3)
               for j in range(4)]
        row += [RTT["near_regional"] if j == i % 2 else RTT["far_regional"] for j in range(2)]
        row += [RTT["near_core"] if j == (i // 2) % 2 else RTT["far_core"] for j in range(2)]
        rows.append(tuple(row))
    return tuple(rows)


BASE = Scenario(key="study", label="Staleness study base", group="study", servers=SERVERS_HET,
                mu=float(CFG["service_rate_per_gpu"]), job_shape=CFG["job_shape"], job_scv=float(CFG["job_scv"]),
                delay_matrix_ms=delay_matrix(int(CFG["ingresses_default"])), ingresses=int(CFG["ingresses_default"]),
                traffic=CFG["traffic_split"], deadline_ms=DEADLINE_STRICT, report_interval=BUDGET_W["medium"],
                site_discard=bool(CFG["deadline_aware_sites"]), sim_time=SIM_TIME, warmup=WARMUP, load=0.9,
                report_bytes=int(CFG["report_bytes"]), counter_bytes=int(CFG["counter_bytes"]),
                probe_bytes=int(CFG["probe_bytes"]))


def unequal_shares(R):
    w = [float(R - i) for i in range(R)]
    t = sum(w)
    return tuple(x / t for x in w)


def with_pattern(sc, pattern):
    if pattern == "steady":
        return sc
    if pattern == "bursty":                    # the average over the measured window stays at sc.load
        span = sc.sim_time - sc.warmup
        frac = len(BURSTS) * BURST_LEN / span
        b = sc.load / (1.0 + frac * (BURST_X - 1.0))
        pts = [(0.0, b)]
        for t0 in BURSTS:
            pts += [(t0, b), (t0 + 1e-3, b * BURST_X), (t0 + BURST_LEN, b * BURST_X), (t0 + BURST_LEN + 1e-3, b)]
        pts.append((sc.sim_time, b))
        return replace(sc, load_profile=tuple(pts))
    if pattern == "shifting":                  # same total, but which ingress sends most rotates
        base = list(unequal_shares(sc.ingresses))
        phases, t, k = [], 0.0, 0
        while t < sc.sim_time:
            rot = base[-k % len(base):] + base[:-k % len(base)] if k else base
            phases.append((t, tuple(rot)))
            t += SHIFT_EVERY
            k += 1
        return replace(sc, share_profile=tuple(phases))
    raise ValueError(pattern)


def make(load=0.9, delay=0.05, pattern="steady", W=None, R=None, servers=SERVERS_HET, deadline=None, extra=None,
         tag=""):
    W = BUDGET_W["medium"] if W is None else W
    R = int(CFG["ingresses_default"]) if R is None else R
    deadline = DEADLINE_STRICT if deadline is None else deadline
    sc = replace(BASE, load=load, report_delay_s=delay, report_interval=W, ingresses=R,
                 delay_matrix_ms=delay_matrix(R), servers=servers, deadline_ms=deadline)
    sc = with_pattern(sc, pattern)
    if extra:
        sc = replace(sc, **extra)
    cap = "hom" if servers == SERVERS_HOM else "het"
    key = f"L{int(round(load * 100))}_d{int(round(delay * 1000))}_{pattern}_W{W:g}_R{R}_{cap}_D{int(deadline)}"
    if tag:
        key += "_" + tag
    meta = dict(load=load, delay_ms=int(round(delay * 1000)), pattern=pattern, W=W, R=R, cap=cap,
                deadline=int(deadline), tag=tag)
    return replace(sc, key=key, label=key, group="study", factor=json.dumps(meta, sort_keys=True))


def meta_of(sc):
    return json.loads(sc.factor)


# ---------------------------------------------------------------------------------------------------- rules
MAIN_RULES = ["nearest", "wrr", "wrr_speed", "wpow2_stale", "dahlin_li", "lsq", "prequal_hcl", "liyanage26",
              "cats_lb", "expected_delay_drop", "ours_v6", "oracle"]
LABELS = {
    "nearest": "A Nearest site", "wrr": "B Capacity WRR", "wrr_speed": "C Dynamic WRR (measured speeds)",
    "wpow2_stale": "D Weighted power-of-two", "dahlin_li": "E Dahlin (Basic LI)", "lsq": "F LSQ (shared periodic reports)",
    "lsq_sample": "F2 LSQ-Sample (own random samples, supplementary)",
    "prequal_hcl": "G Prequal (HCL)", "liyanage26": "H Liyanage et al. 2026", "cats_lb": "I CATS-draft load sharing",
    "expected_delay_drop": "J Expected delay + drop", "ours_v6": "K Staleness-Aware CATS (ours v6)",
    "oracle": "L Fresh-state greedy selection", "oracle_adm": "Fresh-state greedy + fresh-state admission",
    "oracle+adm": "L+ Fresh-state greedy + common wrapper",
    "ours_v6_nobal": "v6 without A (balance)", "ours_v6_noburst": "v6 without B (burst re-plan)",
    "ours_v6_nocal": "v6 without C (corrected risk)", "ours_v6_noage": "v6 without staleness (no ageing)",
    "ours_v6_nodrop": "v6 without admission (no drop)", "prequal_native": "Prequal, native 3 probes/query",
}
SHORT = {"nearest": "Nearest", "wrr": "WRR", "wrr_speed": "DWRR", "wpow2_stale": "W-Po2", "dahlin_li": "Dahlin LI",
         "lsq": "LSQ", "prequal_hcl": "Prequal", "liyanage26": "Liyanage", "cats_lb": "CATS-LB",
         "expected_delay_drop": "ED+drop", "ours_v6": "SA-CATS (v6)", "oracle": "Fresh greedy", "oracle_adm": "Fresh greedy + τ-drop",
         "prequal_native": "Prequal native", "lsq_sample": "LSQ-Sample"}
ADM_RULES = ["nearest", "wrr", "wrr_speed", "wpow2_stale", "dahlin_li", "lsq", "prequal_hcl", "liyanage26",
             "cats_lb", "oracle"]                          # the common rejection wrapper is applied to these
NATIVE_DROPPERS = ["expected_delay_drop", "ours_v6", "oracle_adm"]
SUPP_RULES = ["lsq_sample"]                         # supplementary rival (paper-faithful LSQ updates)
ABLATIONS = ["ours_v6_nobal", "ours_v6_noburst", "ours_v6_nocal", "ours_v6_noage", "ours_v6_nodrop"]
REPORT_RULES = ["wrr_speed", "wpow2_stale", "dahlin_li", "lsq", "cats_lb", "expected_delay_drop", "ours_v6"]

# ---------------------------------------------------------------------------------------------------- pilot
PILOT_CANDIDATES = {          # every tunable baseline gets at most 4 settings; the paper's default comes first
    "prequal_hcl": ["MAX_AGE=1.0,Q_RIF=0.84", "MAX_AGE=1.0,Q_RIF=0.75", "MAX_AGE=4.0,Q_RIF=0.84",
                    "MAX_AGE=4.0,Q_RIF=0.75"],
    "liyanage26": ["WINDOW_N=20", "WINDOW_N=20,PROBE=False", "WINDOW_N=10", "WINDOW_N=40"],
    "cats_lb": ["THETA=0.25,TABLE=100", "THETA=0.25,TABLE=100,HOLD=6.0,HYST=0.2",
                "THETA=0.25,TABLE=100,SLA_QUEUE=False", "THETA=0.25,TABLE=100,HOLD=2.0,SMOOTH=0.3"],
    "dahlin_li": ["PHASE_AGE=True", "PHASE_AGE=False"],
    "oracle_adm": ["TAU=0.8", "TAU=0.5", "TAU=0.95"],
}
PILOT_THRESHOLDS = (0.5, 1.0, 2.0)     # threshold telemetry: send-on-delta in frames per configured server


def pilot_scenarios():
    return [make(0.9, 0.05, "steady"), make(1.3, 0.05, "steady"), make(0.9, 0.05, "bursty"),
            make(0.9, 1.0, "steady")]


def load_frozen():
    if not os.path.exists(PARAMS_FILE):
        return {}
    with open(PARAMS_FILE) as f:
        return json.load(f)


def resolved(alias, frozen=None):
    """The rule string actually run for an alias: frozen parameters from the pilot, wrapper suffix kept."""
    frozen = load_frozen() if frozen is None else frozen
    base, adm = (alias[:-4], "+adm") if alias.endswith("+adm") else (alias, "")
    if base == "prequal_native":
        p = frozen.get("prequal_hcl", "")
        base = "prequal_hcl@" + (p + "," if p else "") + "R_PROBE=3.0"
        return base + adm
    p = frozen.get(base, "")
    return (f"{base}@{p}" if p else base) + adm


# ---------------------------------------------------------------------------------------------------- experiments
_F, _S = CFG["failure_event"], CFG["slowdown_event"]
FAIL = dict(cap_events=((_F["start_s"], _F["site"], _F["gpus_left"]),
                        (_F["end_s"], _F["site"], SERVERS_HET[_F["site"]])))
SLOW = dict(speed_events=tuple([(_S["start_s"], s, _S["speed"]) for s in _S["sites"]]
                               + [(_S["end_s"], s, 1.0) for s in _S["sites"]]))
_C = CFG["congestion_event"]
CONG = dict(path_event=(_C["site"], _C["factor"], _C["start_s"], _C["end_s"]))
EVENT_TIMES = {"fail": (_F["start_s"], _F["end_s"]), "slow": (_S["start_s"], _S["end_s"]),
               "congest": (_C["start_s"], _C["end_s"])}


def experiments(frozen=None):
    """Ordered list of (experiment id, description, [(scenario, alias), ...]). Order = run priority."""
    frozen = load_frozen() if frozen is None else frozen
    thr = frozen.get("_threshold", 1.0)
    E = []

    def grid(loads, delays, patterns, rules=MAIN_RULES, **kw):
        return [(make(L, d, p, **kw), r) for L in loads for d in delays for p in patterns for r in rules]

    E.append(("grid_core_load", "Main grid: steady, 50 ms telemetry delay, every load", grid(LOADS, (0.05,), ("steady",))))
    E.append(("grid_core_delay", "Main grid: steady, loads 90/110%, every telemetry delay",
              grid((0.9, 1.1), (0.0, 0.2, 1.0), ("steady",))))
    E.append(("grid_core_pattern", "Main grid: bursty and shifting, loads 90/110%, 50 ms",
              grid((0.9, 1.1), (0.05,), ("bursty", "shifting"))))
    E.append(("exp7_admission", "Admission fairness: common rejection wrapper, steady, 50 ms",
              [(make(L, 0.05, "steady"), r + "+adm") for L in LOADS for r in ADM_RULES]
              + [(make(L, 0.05, "steady"), "oracle_adm") for L in LOADS]))
    E.append(("exp8_ablation", "Ablation of v6, steady and bursty, 50 ms",
              grid(LOADS, (0.05,), ("steady", "bursty"), rules=ABLATIONS)))
    E.append(("exp5_scalability", "1 and 16 ingresses, steady, 50 ms",
              [(make(L, 0.05, "steady", R=R), r) for R in (1, 16) for L in (0.9, 1.3) for r in MAIN_RULES]))
    E.append(("exp6_failures", "Core-2 loses half its GPUs 40-70 s; regional sites at half speed 35-70 s",
              [(make(0.9, 0.05, "steady", extra=FAIL, tag="fail"), r) for r in MAIN_RULES]
              + [(make(0.9, 0.05, "steady", extra=SLOW, tag="slow"), r) for r in MAIN_RULES]))
    budget = [(make(L, 0.05, "steady", W=W), r) for W in (BUDGET_W["low"], BUDGET_W["high"]) for L in (0.9, 1.3)
              for r in MAIN_RULES]
    budget += [(make(L, 0.05, "steady"), "prequal_native") for L in (0.9, 1.3)]
    th = dict(report_mode="threshold", report_threshold=thr)
    budget += [(make(L, 0.05, "steady", W=0.5, extra=th, tag="thr"), r) for L in (0.9, 1.3) for r in REPORT_RULES]
    E.append(("exp3_budget", "Low/high budget (W = 10 s / 0.5 s), Prequal at its native rate, threshold telemetry",
              budget))
    E.append(("cap_hom", "Homogeneous sites (4 GPUs each), steady, 50 ms",
              [(make(L, 0.05, "steady", servers=SERVERS_HOM), r) for L in (0.9, 1.3) for r in MAIN_RULES]))
    E.append(("deadline_relaxed", "Relaxed deadline 500 ms, steady, 50 ms",
              [(make(L, 0.05, "steady", deadline=DEADLINE_RELAXED), r) for L in (0.9, 1.3) for r in MAIN_RULES]))
    done = {(sc.key, r) for _, _, lst in E for sc, r in lst}
    rest = [(sc, r) for sc, r in grid(LOADS, DELAYS, PATTERNS) if (sc.key, r) not in done]
    E.append(("grid_rest", "Main grid: every remaining (load, delay, pattern) point", rest))
    E.append(("exp6_congestion", "Network delay change: paths to Core-2 take twice as long 40-70 s (supplementary)",
              [(make(0.9, 0.05, "steady", extra=CONG, tag="congest"), r) for r in MAIN_RULES]))
    sup = [sc for sc in {sc.key: sc for sc, _ in grid(LOADS, DELAYS, PATTERNS)}.values()]
    sup += [make(L, 0.05, "steady", W=W) for W in (BUDGET_W["low"], BUDGET_W["high"]) for L in (0.9, 1.3)]
    sup += [make(L, 0.05, "steady", R=R) for R in (1, 16) for L in (0.9, 1.3)]
    sup += [make(L, 0.05, "steady", servers=SERVERS_HOM) for L in (0.9, 1.3)]
    sup += [make(L, 0.05, "steady", deadline=DEADLINE_RELAXED) for L in (0.9, 1.3)]
    sup += [make(0.9, 0.05, "steady", extra=x, tag=t) for x, t in ((FAIL, "fail"), (SLOW, "slow"), (CONG, "congest"))]
    E.append(("supp_lsq_sample", "LSQ-Sample (independent sampling at the same budget) on every main-grid point and "
              "the budget, scalability, capacity, deadline and event scenarios (supplementary)",
              [(sc, r) for sc in sup for r in SUPP_RULES]))
    tf = CFG["telemetry_faults"]
    faults = ((dict(report_loss=float(tf["report_loss"])), "loss"), (dict(report_noise_sd=float(tf["report_noise_sd"])),
                                                                      "noise"))
    E.append(("exp_telemetry_faults", f"Report loss {tf['report_loss']:.0%} or measurement noise (sd "
              f"{tf['report_noise_sd']:g} frames), steady, 50 ms, loads 90/130% (supplementary)",
              [(make(L, 0.05, "steady", extra=x, tag=t), r) for x, t in faults for L in (0.9, 1.3) for r in MAIN_RULES]))
    have = {(sc.key, r) for _, _, lst in E for sc, r in lst}
    E.append(("grid_oracle_wrapped", "Reference: fresh-state greedy selection + the common rejection wrapper on every main-grid "
              "point (supplementary)",
              [(sc, r) for sc, r in grid(LOADS, DELAYS, PATTERNS, rules=["oracle+adm"]) if (sc.key, r) not in have]))
    return E
