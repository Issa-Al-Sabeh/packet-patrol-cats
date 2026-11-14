# Baseline implementation and verification report

Staleness-aware CATS study, November 2026. This report lists, for every algorithm in the comparison:
- the source (paper or specification);
- what was implemented exactly, and every adaptation;
- the parameters (frozen by the pilot on seeds 101–105 before any final run);
- the telemetry the algorithm uses;
- how it was verified.

**Information rule (enforced in tests).** A rule sees only what its ingress could know: configured capacities and path delays, the telemetry it received, its own sends, and (for some rules) the answers to its own frames. The engine can hand non-oracle rules a context whose true state raises on any access (`guard=True`). Every rule in the study runs under that guard in `tests/test_simulator.py::test_conservation_and_guard`. A deliberately cheating rule is caught by `test_guard_catches_a_cheating_rule`.

**Common telemetry.**
- Each site reports every W seconds to every ingress: frames in the system, time measured, and optionally a 4-byte arrivals counter. That is 62 + 4 bytes per report.
- Medium budget: W = 2 s, so 8 × 66 / 2 = 264 B/s per ingress.
- Probing rules spend exactly that budget on probes. A probe is 124 bytes: request + reply.

## Where things are

| Algorithm | Run name | File / class | Telemetry |
|---|---|---|---|
| A Nearest site | `nearest` | `catsim/rules.py` `Nearest` | none |
| B Capacity-weighted round-robin | `wrr` | `rules.py` `WRR` | none |
| C Dynamic weighted round-robin | `wrr_speed` | `rules.py` `WRRSpeed` (+ `SpeedMeter`) | reports + counter |
| D Weighted power-of-two | `wpow2_stale` | `rules.py` `WPow2Stale` | reports |
| E Dahlin, Basic Load Interpretation | `dahlin_li` | `catsim/baselines.py` `DahlinLI` | reports + counter |
| F LSQ | `lsq` | `rules.py` `LSQ` | reports |
| F2 LSQ-Sample (supplementary) | `lsq_sample` | `baselines.py` `LSQSample` | probes (= budget) |
| G Prequal (HCL) | `prequal_hcl` | `baselines.py` `PrequalHCL` | probes (= budget) |
| H Liyanage et al. 2026 | `liyanage26` | `baselines.py` `Liyanage26` | probes (= budget) + own answers |
| I CATS-draft load sharing | `cats_lb` | `baselines.py` `CatsLB` | reports |
| J Expected delay + drop | `expected_delay_drop` | `rules_v5.py` `ExpectedDelayDrop` | reports + counter |
| K Staleness-Aware CATS (ours v6) | `ours_v6` | `rules_v6.py` `SplitV6` | reports + counter + own answers |
| L Fresh-state oracle | `oracle` | `rules.py` `Oracle` | none (reads true state) |
| Oracle + fresh-state admission | `oracle_adm` | `baselines.py` `OracleAdm` | none (reads true state) |
| Common rejection wrapper | `<rule>+adm` | `baselines.py` `AdmissionWrapper` | reports + counter |

**Parameters.** Any rule can be run with class parameters overridden: `rule@K=V,K2=V2`, for example `prequal_hcl@MAX_AGE=1.0,Q_RIF=0.84`. The frozen values are in `study_results/frozen_params.json`. Every run file name records the exact rule string.

## Issues found in the earlier implementations

- **`prequal` (earlier study).** It ranked probed queues by expected delay (SED). It had no requests-in-flight, no latency signal, no hot-cold rule and no reuse budget, so it was not Prequal's selection rule. **Replaced in this study by `prequal_hcl`.**
- **`dahlin` (earlier study).** It aged one number per site and took the minimum deterministically. Dahlin's method is randomized (load interpretation). **Replaced by `dahlin_li`.**
- **`liyanage` (earlier study).** It switched immediately when the current server became infeasible, which the paper does not define. Its feasibility test also differed from the paper's. **Replaced by `liyanage26`.**
- **`timeout_sed`.** It is not the CATS load-sharing draft. **Added `cats_lb`.**
- The earlier classes are **kept unchanged**, so earlier results stay reproducible.

## A. Nearest site
- **Source.** The basic network-only steering CATS improves on (RFC 10053, introduction).
- **Implementation.** The lowest configured round trip. Ignores load.
- **Verified.** Known answer in `test_nearest_and_wrr_sequence`.

## B. Capacity-weighted round-robin
- **Source.** Nginx smooth weighted round-robin (commit 27e9498, 2012).
- **Implementation.** Each pick adds every site's weight to its current weight, takes the largest, and subtracts the total. Weights = configured GPUs. No telemetry.
- **Verified.** Weights {5, 1, 1} give `a a b a c a a`, nginx's own example (`test_nearest_and_wrr_sequence`).

## C. Dynamic weighted round-robin
- **Source.** The DWRR family: weights from measured server speed.
- **Implementation.** Smooth WRR whose weights are the GPUs each site is measured to have. The measurement is v6's `SpeedMeter`, from the same reports: served = arrivals − queue growth, measured while the queue stays long. Reports are stale and periodic; nothing is fresher than for the other rules.
- **Verified.** Behaves like WRR when nothing changes (same success in the steady scenarios). Reacts in the failure and slowdown scenarios.

## D. Weighted power-of-two choices
- **Source.** Power of d choices with capacity-weighted sampling for heterogeneous servers.
- **Implementation.** Sample two sites without replacement, in proportion to capacity. Take the lower last-reported load per GPU (q/c). Ties are broken at random.
- **Verified.** Smoke and conservation tests. Its herding on old snapshots is the classic Mitzenmacher (2000) effect.

## E. Dahlin, Basic Load Interpretation (Eq. 4)
- **Source.** M. Dahlin, *Interpreting Stale Load Information*, IEEE TPDS 11(10), 2000, section 4 (Eqs. 2–4).
- **Exact.**
  - Expected arrivals in a phase (λT) fill the least-loaded servers up to a common level.
  - A request goes to server i with probability proportional to its fill, chosen at random so clients don't herd.
  - Departures are ignored, as in the paper (its footnote 7).
- **Adaptations.**
  1. Sites have unequal sizes, so loads are per GPU (L_i / c_i) and the fill is weighted by c_i. With equal sites this is exactly Eq. 4.
  2. λ comes from the reports' arrivals counters (the paper assumes it is known or estimated).
  3. T = W + the mean age of a report on arrival (`PHASE_AGE=True`, chosen in the pilot; `False` uses T = W).
- **Verified.** `test_dahlin_water_filling` checks Eq. 4 on hand-worked cases, Eq. 2 when every server is reached, and the per-GPU version. `test_dahlin_randomizes_by_fill` checks the randomization.

## F. LSQ (Local Shortest Queue)
- **Source.** Vargaftik, Keslassy, Orda, *LSQ: Load Balancing in Large-Scale Heterogeneous Systems with Multiple Dispatchers*, IEEE/ACM ToN 28(3), 2020.
- **Exact.**
  - Each dispatcher keeps its own local, possibly outdated view of every queue. There is no shared table (`test_independent_ingress_state`).
  - The local view = last report + this ingress's own frames sent since. A newer report replaces it.
  - The dispatcher joins the shortest local queue.
- **Adaptations.**
  1. Sites have several GPUs, so the local count is divided by the site's GPUs.
  2. Ties go to the larger site.
  3. Updates come from the periodic CATS reports (push), not LSQ's sampled pulls. Delayed reports are supported (they arrive late and older ones are ignored).
- **Why a second LSQ.** In the paper, each dispatcher refreshes its view on its own (LSQ-Sample: it samples d random queues at arrivals; LSQ-Update: a server sends its queue to one random dispatcher), so dispatchers rarely hold the same picture. With the shared CATS reports, all four ingresses get the same numbers at the same moment and can pile onto the same site. `lsq_sample` (below) tests the paper's own update style at the same byte budget.
- **LED** (Zhou, Shroff, Wierman 2020) is a theoretical framework for local-estimation policies such as LSQ: conditions for throughput and heavy-traffic delay optimality. It is discussed, not implemented as a separate algorithm.
- **Verified.** Known answer in `test_lsq_local_view`.

## F2. LSQ-Sample (supplementary)
- **Source.** The same paper, section V-A (LSQ-Sample(d)); its evaluation uses d = 2.
- **Exact.**
  - The same local view and choice as `lsq` (last value + own frames since; shortest per server).
  - The view is refreshed by the dispatcher's own uniform random samples, independently of the other dispatchers. No shared report stream.
- **Adaptations.**
  1. **The sampling rate follows the byte budget** (a token bucket, as for Prequal): about 2 samples per second per ingress at the medium budget, against d = 2 per arrival in the paper.
  2. A sample is a probe (124 bytes, request + reply). It reaches the site after the one-way delay, and its answer serves later frames.
- **No parameter to tune** (the budget sets the rate).
- **Verified.** `test_lsq_sample_independent_sampling_within_budget`: no report bytes; probe bytes within 5% of the budget; two ingresses hold different measurement times (with shared reports they are equal); a sample replaces the local value and clears the own frames it already counts; an older sample is ignored.

## G. Prequal (HCL)
- **Source.** Wydrowski, Kleinberg, Rumble, Archer, *Load is not what you should balance: Introducing Prequal*, NSDI 2024, section 4; testbed defaults from section 5.
- **Exact.**
  - Asynchronous probing to sites sampled uniformly without replacement. Replies carry requests-in-flight (RIF) and a server-side latency estimate. The engine computes that estimate at the site: the median time at the site of frames finished in the last 2 s that found a RIF closest to the current one.
  - Probe pool:
    - the oldest probe is dropped when the pool is full;
    - probes past MAX_AGE are removed;
    - a probe is removed after b_reuse uses, with b_reuse = max(1, (1+δ)/((1−m/n)·r_probe − r_remove)) and random rounding;
    - r_remove removals per query alternate between the oldest and the worst probe.
  - HCL rule:
    - a probe is hot if its RIF is above the Q_RIF quantile of recent probe RIFs;
    - if every probe is hot, take the lowest RIF; otherwise the cold probe with the lowest latency;
    - the local RIF is incremented after use;
    - fall back when fewer than 2 probes remain.
- **Adaptations.**
  1. **The probe rate follows the telemetry budget**, by default exactly the bytes of a report-based rule with the counter. r_probe per query is therefore about 0.03, far below Prequal's own 3–5. The supplementary run `prequal_native` uses 3 probes per query (about 100× the budget) to show the method in its intended regime.
  2. RIF is divided by the site's GPUs (sites differ in size).
  3. The latency used by HCL = server-side estimate + known round trip, because the deadline is end to end.
  4. Pool size m = max(2, n/2) = 4, since the paper's 16 needs n ≫ m.
  5. r_remove = r_probe/3 (the testbed ratio of 1:3), so the b_reuse formula stays defined.
  6. The fallback is random in proportion to capacity (uniform in the paper; identical for equal sites).
  - Not modelled: error aversion and sinkholing (omitted by the authors too), idle probing.
- **Frozen.** MAX_AGE = 1 s, Q_RIF = 0.84 (the testbed default). These won the pilot among {1, 4} s × {0.75, 0.84}.
- **Verified.** Hot/cold selection on hand-built pools in `test_prequal_hcl_selection`. The budget is matched within 5% in `test_probe_budget_matches_reports`.

## H. Liyanage et al. 2026
- **Source.** Liyanage, Abdullah, Zhantileuov, Schuster, *Risk-Aware and Stable Edge Server Selection Under Network Latency SLOs*, arXiv 2604.21483 (Algorithms 1–2).
- **Exact.**
  - Per server: mean and sample standard deviation of the last W observations.
  - p_Norm = 1 − Φ((τ−μ)/σ) and p_Cant = 1/(1+((τ−μ)/σ)²).
  - Feasible set: p_Norm < ε and p_Cant < ε. Challenger = argmin over the feasible set of μ + kσ.
  - Switch only if score_cur − score_j ≥ Δ·score_cur for N consecutive decisions. The counter resets on a failed test, when the challenger is the current server, or when the feasible set is empty (the client then stays).
  - Paper defaults: ε = 0.15, k = 1.645, Δ = 0.05, N = 5. Decisions are per frame.
- **Adaptations.**
  1. τ = the frame deadline. The observation = end-to-end latency (compute queueing dominates in CATS).
  2. A client = one camera at 10 frames/s; an ingress runs several clients, which start spread by capacity. One client per ingress would send a quarter of all traffic to one site.
  3. The paper observes every server's latency at each step. Here clients observe their own frames, and the ingress spends the telemetry budget on probes to random sites. A probe gives one observation of that site (server-side latency + round trip) to every client of the ingress.
  4. Servers with no observation use a prior: round trip + one service time.
  5. W is not given in the paper.
- **Frozen.** W = 40 samples, with probes. These won the pilot among {20 (probes), 20 (passive only), 10, 40}. Passive-only reached 10% success: clients chase the optimistic prior of sites they never observe.
- **Verified.** `test_liyanage_formulas_and_hysteresis` checks the Cantelli formula and that a switch happens only on the N-th consecutive pass.

## I. CATS-draft load sharing
- **Source.** draft-fu-cats-flow-lb-03 (ZTE, February 2026), sections 4–7. **This is an individual Internet-Draft, not a standard.** RFC 10053 specifies no selection algorithm (section 4.3).
- **From the draft.**
  - Per service, the forwarding alternatives that meet the SLA, each with a load-sharing weight from instance metrics and path characteristics.
  - The table is regenerated only when metric changes cross a threshold, with optional hysteresis against oscillation.
  - UCMP-to-ECMP expansion into entries in proportion to the weights. The forwarder hashes the flow id onto an entry.
- **Our choices (the draft leaves all of these unspecified).**
  - Metric = reported frames per GPU.
  - SLA filter = round trip + one service time + visible wait ≤ deadline.
  - Weight = c_s / (1 + q_s / c_s).
  - Threshold THETA on any site's metric change.
  - Hysteresis = HOLD seconds between regenerations and/or a minimum L1 move HYST; optional smoothing toward the new weights (SMOOTH).
  - 100 entries (largest-remainder rounding). The hash is Knuth's multiplicative hash of the frame id.
  - Each frame is its own request/flow, so affinity has no effect.
- **Frozen.** THETA = 0.25, TABLE = 100, HOLD = 2 s, SMOOTH = 0.3. Without anti-oscillation smoothing the pilot gave 14% success; with it, 63%.
- **Verified.** The expansion reproduces the draft's example table (weights 20/30/30/20% → 2, 3, 3, 2 entries). Threshold behaviour in `test_cats_table_and_threshold`.

## J. Expected delay + drop
- **Source.** The strongest rival of the earlier study (v4's own report).
- **Implementation.** The belief of ours v1 (report aged by a birth-death model, the others' traffic estimated from the counter). Picks the site with the lowest expected response time. Drops the frame when even that is over the deadline. **Reused unchanged.**

## K. Staleness-Aware CATS (ours v6)
- **Implementation.** **Reused exactly** (`SplitV6`, GAIN = 0.25 frozen in the v6 study). Each report is aged to now (staleness awareness).
  - Below overload, it shares by measured capacity unless its risk plan predicts at least 25% fewer late frames.
  - In overload, each 1% of traffic goes to the cheapest site or to drop. Drop costs exactly one miss.
  - It re-plans between reports on clear jumps.
  - Smooth WRR on the shares.
- **Regression.** `test_regression_v6_reproduces_saved_study` reproduces the earlier study's seed value 2.8937% on the main Beirut scenario exactly. The earlier O_130 value 34.0843% was also reproduced.
- **Ablations (switches on existing mechanisms only).**
  - `nobal`, `noburst`, `nocal` (changes A/B/C of v6).
  - `noage`: every report used as if fresh, i.e. no staleness awareness.
  - `nodrop`: the drop option is never available, i.e. no admission control.
  - v6 has no hysteresis and no adaptive telemetry, so those ablations do not apply.

## L. Fresh-state oracle and oracle + admission
- **Oracle.** Reads the true frames in the system, the working GPUs and their speed. Sends each frame where its true chance of being late is lowest. It is greedy per frame and ignores frames already in flight to a site, so it is **not an upper bound** (it is below round-robin at 90% load).
- **Oracle + admission.** Also drops when that lowest chance is ≥ τ. τ = 0.5 won the pilot among {0.5, 0.8, 0.95}. Both are references, not practical rules.
- **Where they are used.**
  - The oracle runs in every scenario.
  - In overload the routing-only oracle is a weak reference: it cannot drop, so rules that drop can beat it.
  - So the main table also reports the gap to the **oracle behind the common rejection wrapper** (`oracle+adm`), run on every main-grid point (`grid_oracle_wrapped`).
  - `oracle_adm` (τ = 0.5) is weaker than the wrapped oracle in overload: it admits every frame whose best true chance of being late is below 50%. τ = 0.5 was the lowest pilot candidate, so the candidate set was probably too narrow. It was not re-tuned after the final runs; it stays a secondary reference in the admission table only.

## Common rejection wrapper (admission fairness)
- **Rule.** The same admission rule in front of any routing rule. It drops just enough frames to keep the admitted traffic at 95% of the configured capacity, spread evenly by a deterministic credit. Offered traffic = counted arrivals / (1 − own drop share), exactly as in ours v5/v6 and in round-robin + drop.
- **Isolation.** The inner rule routes every admitted frame as it would alone, and never sees dropped frames.
- **Telemetry.** The wrapper needs the reports with the counter. For inner rules that use no reports (WRR, nearest, Prequal, Liyanage), those bytes are added and reported in the realized bytes per second.
- **Verified.**
  - Below capacity, wrapped and unwrapped rules make identical routing decisions frame by frame (`test_admission_wrapper_does_not_change_routing_below_capacity`).
  - At 130% load it rejects about 1 − 0.95/1.3 ≈ 27% (`test_admission_wrapper_drops_in_overload`).

## Engine verification (`tests/test_simulator.py`, 51 tests, all passing)
- **Determinism.** Same seed, same results.
- **Common traces.** All rules see identical frames, job sizes, ingresses and path delays.
- **Request conservation.** Every counted frame ends exactly once as success, late, expired or rejected. This is checked inside every run, and the engine raises otherwise.
- **Deadline classes.** Recomputed independently from per-frame records.
- **Queues.** FCFS order; never more frames in service than GPUs.
- **M/M/c.** Mean time against Erlang C within 3%.
- **Telemetry delay.** 1 s of report delay raises the mean age of the telemetry used by 1 s. The 95th-percentile age ≤ W + delay + longest one-way trip.
- **Bytes.** Report bytes equal rounds × sites × ingresses × (62 [+ 4]) / T exactly. Probe bytes match the budget within 5%.
- **Threshold reporting.** Sends fewer reports; a threshold of 0 equals periodic exactly; losses keep common randomness.
- **Measurement noise.** Changes only the reports (own random stream).
- **Network delay change.** While a path event lasts, every frame to that site arrives exactly (factor − 1) × one-way delay later; outside it, no change (`test_network_delay_change_event`).
- **Shifting traffic.** Moves the main ingress. Bursty traffic keeps the average offered load (0.9 ± 0.04).
