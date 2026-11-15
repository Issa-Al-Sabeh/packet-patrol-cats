"""Every setting of the study, in one place.

The MAIN scenario is the Beirut camera example. Every sweep changes ONE thing from it;
every stress test and every real-life scenario adds ONE problem to it. Change numbers here, not elsewhere.
"""
from dataclasses import dataclass, replace, fields

SITE_NAMES = ("Hamra", "Jdeideh", "Regional DC")
MODEL_VERSION = "2026-10-28"          # change this after editing the code of a rule or of the engine


@dataclass(frozen=True)
class Scenario:
    key: str = "main"                 # short id, used in file names
    label: str = "Main scenario (Beirut)"
    group: str = "main"               # main | sweep | stress | real | heldout
    factor: str = ""                  # for sweeps: which factor this point belongs to
    value: str = ""                   # for sweeps: the value shown on the x axis

    # --- sites ---
    servers: tuple = (2, 4, 8)        # GPU servers at Hamra, Jdeideh, Regional DC
    mu: float = 10.0                  # frames one server finishes per second (100 ms each)
    job_shape: str = "gamma"          # gamma | exp | lognormal
    job_scv: float = 0.25             # job-size variability (squared coeff. of variation); 1 = exponential

    # --- network ---
    base_delay_ms: tuple = (8.0, 16.0, 60.0)   # round trip from Ingress A to each site
    delay_spread: float = 0.25        # other ingresses: base x (1 +/- up to 25%), fixed per run
    jitter_ms: float = 0.0            # extra random delay per one-way trip (exponential mean); 0 = none

    # --- traffic ---
    load: float = 0.85                # total traffic / total capacity
    load_jump_to: float = 0.0         # > 0: load switches to this value halfway through the run
    cap_drop: tuple = ()              # (site, servers): that site keeps only this many servers from halfway on

    # --- real-life events (all off by default; added for the second round of the study) ---
    servers_known: tuple = ()         # what the rules are told (wrong weights); () = the true servers
    cap_events: tuple = ()            # ((time s, site, servers), ...): working servers change, unannounced
    load_profile: tuple = ()          # ((time s, load), ...): load changes linearly between these points
    surge: tuple = ()                 # (ingress, factor, t_start, t_end): that ingress sends factor x its frames
    path_event: tuple = ()            # (site, factor, t_start, t_end): that site's path delays x factor
    speed_events: tuple = ()          # ((time s, site, speed), ...): that site's GPUs run at this speed (1 = normal)
    # --- v5 study (all off by default) ---
    site_discard: bool = False        # deadline-aware sites: a frame whose turn comes after its deadline is
                                      # discarded (not served); the report counter then also counts the discards
    ingresses: int = 4
    traffic: str = "unequal"          # unequal: shares proportional to R, R-1, ..., 1 (4 ingresses: 40/30/20/10%)
    deadline_ms: float = 300.0

    # --- load reports ---
    report_interval: float = 5.0      # W: seconds between two reports of a site
    report_bytes: int = 62            # one report (queue, time measured)
    counter_bytes: int = 4            # our extra arrivals counter A
    stagger_reports: bool = False     # True: sites report at different moments
    report_loss: float = 0.0          # chance that one report to one ingress is lost
    report_extra_delay_s: float = 0.0 # late reports: extra delay, uniform between 0 and this value

    # --- staleness study (Nov 2026). All off by default: earlier scenarios keep their names and numbers ---
    delay_matrix_ms: tuple = ()       # explicit round trips (ms), one row per ingress; overrides base_delay_ms
    report_delay_s: float = 0.0       # telemetry delay: every report spends this much longer in transit
    report_noise_sd: float = 0.0      # measurement noise: reported frames = true + Normal(0, sd), rounded, >= 0
    report_mode: str = "periodic"     # periodic | threshold (sampled send-on-delta; see engine.py)
    report_threshold: float = 0.0     # threshold mode: send when |q - last sent q| >= this x configured servers
    report_heartbeat: float = 0.0     # threshold mode: send at least every this many seconds (0 = 4 W)
    share_profile: tuple = ()         # ((time s, (share of each ingress, ...)), ...): ingress shares change
    budget_bps: float = 0.0           # telemetry budget per ingress (bytes/s) for probing rules; 0 = same bytes as
                                      # a rule that receives every report with the counter: S x (62 + 4) / W
    probe_bytes: int = 124            # one probe request + its reply

    # --- v6.1 (Nov 2026). At its default: earlier scenarios keep their names and numbers ---
    echo_bytes: int = 2               # one drop count: ingress -> site on a frame it sends anyway, and the sum of
                                      # those counts, site -> ingress, in each report (only for rules that use it)

    # --- run length ---
    sim_time: float = 0.0             # seconds of traffic; 0 = automatic
    warmup: float = 20.0              # frames created before max(warmup, 2W) are not counted

    def duration(self):
        return self.sim_time if self.sim_time > 0 else max(150.0, 20.0 * self.report_interval)

    def warmup_time(self):
        return max(self.warmup, 2.0 * self.report_interval)

    def physics(self):
        """Everything that changes the simulation (not the names). Used to spot duplicates and to name saved runs.
        Fields added in the second round are left out while they are off, so earlier runs keep their names."""
        skip = {"key", "label", "group", "factor", "value"}
        return tuple((f.name, getattr(self, f.name)) for f in fields(self)
                     if f.name not in skip and not (f.name in ROUND2_FIELDS and getattr(self, f.name) == ())
                     and not (f.name in V5_FIELDS and getattr(self, f.name) == V5_FIELDS[f.name])
                     and not (f.name in STUDY_FIELDS and getattr(self, f.name) == STUDY_FIELDS[f.name])
                     and not (f.name in V61_FIELDS and getattr(self, f.name) == V61_FIELDS[f.name]))


ROUND2_FIELDS = {"servers_known", "cap_events", "load_profile", "surge", "path_event",   # round 2
                 "speed_events"}                                                          # round 3
V5_FIELDS = {"site_discard": False}       # v5 study: left out of run names while at this default
STUDY_FIELDS = {"delay_matrix_ms": (), "report_delay_s": 0.0, "report_noise_sd": 0.0, "report_mode": "periodic",
                "report_threshold": 0.0, "report_heartbeat": 0.0, "share_profile": (), "budget_bps": 0.0,
                "probe_bytes": 124}       # staleness study: left out of run names while at these defaults
V61_FIELDS = {"echo_bytes": 2}            # v6.1: left out of run names while at this default

MAIN = Scenario()

# mixed jobs: (share of frames, size relative to the 100 ms average), each type with variability 0.25
JOB_MIX = ((0.8, 0.75), (0.2, 2.0))
JOB_MIX_WITHIN = 0.25
MIX_SCV = (1 + JOB_MIX_WITHIN) * sum(w * r * r for w, r in JOB_MIX) - 1     # overall variability (0.5625)

# ---------------------------------------------------------------- sweeps (one factor at a time)
JOB_SHAPES = {
    "regular (v=0.25)": dict(job_shape="gamma", job_scv=0.25),
    "exponential (v=1)": dict(job_shape="exp", job_scv=1.0),
    "heavy-tailed (v=2)": dict(job_shape="lognormal", job_scv=2.0),
}

SWEEPS = {
    # 0.2 and 0.5 s were added after the plan was approved, to find where our rule overtakes round-robin
    "report_interval": ("Report interval W (s)", True,
                        [(str(v), dict(report_interval=float(v))) for v in (0.2, 0.5, 1, 2, 5, 10, 30)]),
    "load": ("Load (%)", True, [(str(v), dict(load=v / 100)) for v in (50, 70, 85, 95)]),
    "deadline": ("Deadline (ms)", True, [(str(v), dict(deadline_ms=float(v))) for v in (200, 300, 500)]),
    "job_shape": ("Job-size shape", False, list(JOB_SHAPES.items())),
    "ingresses": ("Number of ingresses", True, [(str(v), dict(ingresses=v)) for v in (2, 4, 8, 16)]),
    "traffic": ("Traffic split between ingresses", False,
                [("unequal", dict(traffic="unequal")), ("equal", dict(traffic="equal"))]),
    "sites": ("Site sizes", False,
              [("unequal 2/4/8", dict(servers=(2, 4, 8))), ("equal 4/4/4", dict(servers=(4, 4, 4)))]),
    "report_timing": ("Report timing", False,
                      [("in sync", dict(stagger_reports=False)), ("staggered", dict(stagger_reports=True))]),
}

STRESS = [
    ("jitter_5", "Delay jitter, +5 ms average per trip", dict(jitter_ms=5.0)),
    ("jitter_20", "Delay jitter, +20 ms average per trip", dict(jitter_ms=20.0)),
    ("loss_10", "10% of reports lost", dict(report_loss=0.10)),
    ("loss_30", "30% of reports lost", dict(report_loss=0.30)),
    ("late_reports", "Reports arrive up to 2 s late", dict(report_extra_delay_s=2.0)),
    ("load_jump", "Load jumps from 60% to 95% halfway", dict(load=0.60, load_jump_to=0.95)),
    # added after the plan was approved: the reason CATS needs reports at all is that site capacity changes
    ("cap_drop", "Hamra loses 1 of its 2 servers halfway (not announced)", dict(cap_drop=(0, 1))),
]

# ---------------------------------------------------------------- real-life scenarios (second round)
# Each one = the main scenario plus one thing that happens in real deployments. None is announced to the rules.
REAL_LIFE = [
    ("server_fail_recover", "Server failure: Hamra loses 1 of its 2 servers at 50 s, gets it back at 100 s",
     dict(cap_events=((50.0, 0, 1), (100.0, 0, 2)))),
    ("shared_gpus", "Shared GPUs: another app takes 2 of Jdeideh's 4 GPUs, 20 s on, 20 s off",
     dict(cap_events=((40.0, 1, 2), (60.0, 1, 4), (80.0, 1, 2), (100.0, 1, 4), (120.0, 1, 2), (140.0, 1, 4)))),
    ("wrong_weights", "Wrong weights: rules are told the DC has 8 servers, only 6 work",
     dict(servers=(2, 4, 6), servers_known=(2, 4, 8))),
    ("rush_hour", "Rush hour: load 60% to 95% and back over 5 minutes",
     dict(sim_time=300.0, load=0.60,
          load_profile=((0.0, 0.60), (60.0, 0.60), (120.0, 0.95), (180.0, 0.95), (240.0, 0.60), (300.0, 0.60)))),
    ("ingress_surge", "Incident: Ingress D doubles its frames from 50 s to 100 s",
     dict(surge=(3, 2.0, 50.0, 100.0))),
    ("mixed_jobs", "Mixed jobs: 80% short (75 ms), 20% long (200 ms)",
     dict(job_shape="mix", job_scv=MIX_SCV)),
    ("path_congestion", "Congestion: the DC's path delays double from 60 s to 90 s",
     dict(path_event=(2, 2.0, 60.0, 90.0))),
]

# ---------------------------------------------------------------- held-out scenarios (third round)
# Defined before any run of round 3 and NEVER used to design or tune a rule (not in the pilot either): they check
# that ours v2 + measured speeds is not tuned to the scenarios it was designed on.
HELD_OUT = [
    ("dc_fail_recover", "Held out - DC failure: the DC loses 1 of its 8 servers at 50 s, gets it back at 110 s",
     dict(cap_events=((50.0, 2, 7), (110.0, 2, 8)))),
    ("slow_gpus", "Held out - Slow GPUs: Jdeideh's GPUs run at 70% speed from 40 s to 110 s",
     dict(speed_events=((40.0, 1, 0.7), (110.0, 1, 1.0)))),
]

# ---------------------------------------------------------------- rules
RULES = ["ours", "ours_v2", "ours_v2_check", "ours_v2_speed", "expected_delay", "dahlin", "liyanage", "lsq",
         "timeout_sed", "power_of_two", "wpow2_stale", "prequal", "nearest", "cap_random", "wrr", "wrr_speed",
         "oracle"]
OURS_FAMILY = ["ours", "ours_v2", "ours_v2_check", "ours_v2_speed"]
PILOT_RULES = ["ours_v2", "ours_v2_check", "ours_v2_speed", "wrr", "wrr_speed", "oracle"]
PILOT_SEEDS = (101, 102, 103, 104, 105)     # never used in the report
# round 3: the pilot also covers the settings where measuring speeds is hardest (never the held-out scenarios)
PILOT_EXTRA = ["report_interval=0.2", "report_interval=30", "job_shape=heavy-tailed (v=2)", "load=95",
               "loss_30", "cap_drop"]
ABLATIONS = ["ours_no_counting", "ours_no_ageing", "ours_exp_late", "ours_no_ties"]

LABELS = {
    "ours": "Ours v1 (deadline risk, per frame)",
    "ours_v2": "Ours v2 (risk-based split)",
    "ours_v2_check": "Ours v2 + self-check",
    "ours_v2_speed": "Ours v2 + measured speeds",
    "expected_delay": "Expected delay (same belief)",
    "dahlin": "Dahlin-style (one aged number)",
    "liyanage": "Liyanage-style 2026 (measured delays)",
    "lsq": "LSQ-style local count",
    "timeout_sed": "CATS timeout + SED",
    "power_of_two": "Power of two (old reports)",
    "wpow2_stale": "Weighted power of two (stale snapshot)",
    "prequal": "Prequal-style probing (same bytes)",
    "nearest": "Nearest site",
    "cap_random": "Capacity-weighted random",
    "wrr": "Weighted round-robin",
    "wrr_speed": "Round-robin + measured speeds",
    "oracle": "Fresh-state greedy (true queues)",
    "ours_no_counting": "Ours v1 without counting the others",
    "ours_no_ageing": "Ours v1 without ageing the report",
    "ours_exp_late": "Ours v1 with exponential late(n)",
    "ours_no_ties": "Ours v1 without random near-ties",
}

GROUPS = {
    "Ours": ["ours", "ours_v2", "ours_v2_check", "ours_v2_speed"],
    "Same information, different scoring": ["expected_delay"],
    "Closest recent work": ["liyanage"],
    "Classic rules on old reports": ["dahlin", "lsq", "timeout_sed", "power_of_two", "wpow2_stale", "prequal"],
    "Basic controls": ["nearest", "cap_random", "wrr"],
    "Control for the measured speeds": ["wrr_speed"],
    "Reference": ["oracle"],
}


def build_real_life(main=MAIN):
    return [replace(main, key=k, label=lab, group="real", **chg) for k, lab, chg in REAL_LIFE]


def build_held_out(main=MAIN):
    return [replace(main, key=k, label=lab, group="heldout", **chg) for k, lab, chg in HELD_OUT]


def build_scenarios():
    """All scenario points of the study (without the real-life ones). Sweep points identical to MAIN are reused."""
    main = MAIN
    sweeps = {}
    for factor, (title, numeric, points) in SWEEPS.items():
        pts = []
        for value, change in points:
            sc = replace(main, key=f"{factor}={value}", label=f"{title}: {value}", group="sweep",
                         factor=factor, value=value, **change)
            if sc.physics() == main.physics():
                sc = replace(main, factor=factor, value=value)   # same run as main
            pts.append(sc)
        sweeps[factor] = (title, numeric, pts)
    stress = [replace(main, key=k, label=lab, group="stress", **chg) for k, lab, chg in STRESS]
    return main, sweeps, stress
