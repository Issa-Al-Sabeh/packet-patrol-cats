# Positioning: what is known, what we add, and the contribution statement

- Packet Patrol, CMPS 342. Written 21 Nov 2026, after the final run (`feedback/final.md`).
- Purpose: answer the professor's point that the contribution was weak, by stating exactly what is new and what is not.
- ✓ = checked against its source page on the date shown. † = not yet checked against the source; check before the paper or drop it.

## 1. The four references that were unchecked

| Reference | Checked details | Status |
|---|---|---|
| M. Mitzenmacher, "The power of two choices in randomized load balancing," IEEE TPDS, vol. 12, no. 10, pp. 1094–1104, Oct. 2001, doi 10.1109/71.963420 | volume, issue, pages, year, DOI | ✓ 21 Nov 2026 |
| M. Dahlin, "Interpreting stale load information," IEEE TPDS, vol. 11, no. 10, pp. 1033–1047, Oct. 2000 | volume, issue, pages, year (an earlier version appeared at ICDCS 1999) | ✓ 21 Nov 2026 (the "section 4" pointer in `BASELINES.md` is not checked) |
| B. Wydrowski, R. Kleinberg, S. M. Rumble, A. Archer, "Load is not what you should balance: Introducing Prequal," USENIX NSDI 2024, Santa Clara, CA, Apr. 2024 | authors, title, venue; asynchronous, reusable probes; power of d choices; signals = requests in flight and latency | ✓ 21 Nov 2026 |
| nginx smooth weighted round-robin: M. Dounin, "Upstream: smooth weighted round-robin balancing," nginx changeset 4621:c90801720a0c, 14 May 2012 (merged to stable-1.2 on 4 Jun 2012) | author, date, the {5,1,1} → a a b a c a a example | ✓ 21 Nov 2026 |

New reference that the paper must add:
- M. Mitzenmacher, "How useful is old information?" IEEE TPDS, vol. 11, no. 1, pp. 6–20, Jan. 2000, doi 10.1109/71.824633. ✓ 21 Nov 2026.
  - It shows that sending to the least-loaded server on old, shared ("bulletin board") information causes **herd behaviour**, and that a little randomness (two random choices) avoids it.
  - So our LSQ result is a **confirmation of a known effect** in the CATS setting, not a new finding. The paper must cite it there.

## 2. What is known, and what we add

| Our finding | Known before? | What we add |
|---|---|---|
| Synchronised shared reports make "join the least-loaded" rules herd (LSQ 49% → 85% on time when each ingress is refreshed at its own moment) | **Yes.** Herd behaviour on stale shared load information: Mitzenmacher 2000 ✓; Dahlin 2000 ✓. | Shows it happens with the CATS reporting model (every ingress gets the same metric update at the same moment), and that it is the reports, not LSQ, that cause it. Relevant to RFC 10054's requirement that steering not oscillate (R10). |
| Admission (dropping at the door) decides deadline success under overload more than routing does | **Partly.** Overload control by admission is established: Breakwater (OSDI 2020) ✓, DAGOR (SoCC 2018) †, SEDA †. Edge-based distributed admission: Kelly, Key and Zachary 2000 †; PCN at network ingresses †. | Measured in CATS site selection with a deadline: with the same round-robin routing, adding well-set admission lifts mean success from 51.8% to 76.0%; our full rule reaches 78.1%, and in steady load at or above 95% the round-robin rival is level (−0.4 ± 0.2). CATS documents list dropping requests as a symptom (draft-ietf-cats-usecases-requirements ✓) but specify no admission algorithm; draft-luan-cats-catpts-01 ✓ only says a controller "may … reject the request". |
| With shared reports, "arrivals ÷ (1 − own drop share)" misestimates offered traffic when ingresses drop different shares; a shared drop counter fixes it | **The correction itself is classical** (offered = carried ÷ admitted fraction). We found no CATS document or paper that addresses several ingresses dropping different shares while reading the same site counters (search on 21 Nov 2026; absence is not proof). | The counterexample (300 and 150 where the truth is 200, from the professor), its size in practice (v6: 0.64 to 5.63 × the truth; 29% within 5%), and a 2-byte fix (v6.1 with the counter: 0.97 to 1.16 ×, 95% within 5%; v6.2: 0.95 to 1.04 ×, 100%) for 4–5% more telemetry than v6, the same bytes as every admission rival (Tables 5 and 9 of `final.md`). |
| Steering by **measured** capacity pays when the real capacity differs from the configured one | **Partly.** Adapting to measured server speed exists: dynamic weighted round-robin (family, no single source); C3 (NSDI 2015) ✓ ranks replicas by observed performance; Prequal ✓ probes requests in flight and latency. | Quantified at CATS report rates and budgets: +9.4 ± 1.0 points over the tuned rival in 4 of 4 failure and wrong-weight scenarios, with the same telemetry bytes and no probes; and +2.0 ± 0.2 in bursts once the estimate falls at once (v6.2). |
| A pre-registered evaluation (frozen code, pilot vs evaluation seeds, paired intervals, a rival tuned in its own favour) | **Practice exists**, but CATS proposals so far report no evaluation or only supporting results (see `claude/cats-contribution-directions.md`; draft-luan-cats-catpts-01 ✓). | 7,280 runs on 20 seeds, three networks, every baseline labelled with its source, nothing removed, and the strongest rival we could build from the baselines' own settings. |

## 3. Comparison matrix

Rows are approaches; columns are what each assumes and does in a CATS-like setting (several ingresses, shared periodic site reports, a per-request deadline).

| Approach | Information it uses | Several ingresses on the same shared info? | Drops at the door? | Deadline in the decision? | Uses measured (not configured) capacity? | Offered-traffic estimate when ingresses drop differently? | Evaluation |
|---|---|---|---|---|---|---|---|
| Nearest site (network-only steering; RFC 10053 ✓) | path cost | n/a | no | no | no | n/a | — |
| Capacity round-robin (nginx smooth WRR ✓) | configured weights | yes (no telemetry) | no | no | no | n/a | production use |
| Power of two choices (Mitzenmacher 2001 ✓) | queue lengths of 2 random servers | analysed with fresh info | no | no | no | n/a | analysis + simulation |
| Old information (Mitzenmacher 2000 ✓) | periodic bulletin board | yes: shows herding | no | no | no | n/a | analysis + simulation |
| Interpreting stale load (Dahlin 2000 ✓) | stale loads + their age | yes | no | no | no | n/a | simulation |
| LSQ (Vargaftik, Keslassy, Orda 2020 ✓) | each dispatcher's own local view, refreshed by samples | yes: designed for it | no | no | no | n/a | analysis + simulation |
| Prequal (NSDI 2024 ✓) | asynchronous probes: requests in flight, latency | each client probes on its own | no | latency-aware, no deadline drop | yes (via probes) | n/a | testbed + YouTube production |
| C3 (NSDI 2015 ✓) | per-replica feedback, rate control | yes | backpressure, not drop | no | yes | n/a | EC2 + simulation |
| Liyanage et al. (IWCMC 2026 ✓) | observed latency per server | per client | no | latency SLO risk | via observations | n/a | simulation |
| draft-fu-cats-flow-lb-03 ✓ | CATS metrics, UCMP weights | yes | no | SLA filter | no | n/a | none |
| draft-luan-cats-catpts-01 ✓ | utilisation, link load; two timescales | not addressed | "may reject"; no algorithm | optional field only | no | n/a | supporting results only |
| Breakwater (OSDI 2020 ✓) | server-side queueing delay → credits | yes (many clients) | yes (server-driven) | SLO via delay target | n/a (one server) | n/a | testbed |
| **Ours v6.1 / v6.2** | shared periodic CATS reports + a 2-byte drop counter | **yes: the design point** | **yes, per frame, at the ingress** | **yes: deadline-miss risk per site** | **yes (capacity meter)** | **yes: the drop counter** | **7,280 simulated runs, 3 networks, 20 seeds, tuned rival** |

- Reading: our rule is the only row that combines shared periodic reports at several ingresses, ingress admission and deadline-aware site selection with measured capacity, and that measures the estimate it relies on. Each ingredient exists elsewhere; the combination, the CATS setting and the evidence are what is ours.
- † rows are left out of the matrix until checked.

## 4. Contribution statement (for the paper)

> We study computing-aware site selection when several CATS ingresses share the same periodic, byte-budgeted site reports and each request has a deadline. We make three contributions.
>
> 1. **A correct shared estimate of offered traffic.** We show that the usual drop-corrected estimate is biased when ingresses drop different shares, by 0.64 to 5.63 times the truth in our runs, and fix it with a 2-byte aggregate drop counter in the reports (0.97 to 1.16 times the truth; 0.95 to 1.04 with v6.2) at 4–5% more telemetry.
> 2. **Where steering pays under CATS telemetry.** With a pre-registered evaluation (frozen code, pilot and evaluation seeds kept apart, 7,280 runs on 20 seeds and three networks, a rival tuned in its own favour), we find that admission control decides most of the deadline success under overload. Steering by measured capacity adds +9.4 points when the real capacity differs from the configured one, and +2.0 points in bursts once the estimate falls as fast as it rises; in steady load it is level with round-robin plus well-set admission.
> 3. **Design guidance for CATS metric distribution.** Synchronised shared reports reproduce the herd effect known from stale-information load balancing (Mitzenmacher 2000), so rules that send to the apparently least-loaded site need desynchronised updates or randomness; and recovery after capacity returns is limited by how fast capacity is re-measured.

## 5. What the paper must not claim

- That LSQ collapses, or that herding is our discovery.
- A general gain over round-robin with admission (+2.1 ± 0.2 overall is small; the gain is concentrated in failures, wrong weights and bursts).
- That the backlog penalty, the greedy planner or the v6.1 threshold change improve success (each is within ± 0.1).
- That v6.2 dominates v6.1: it is better in bursts, worse on fast on/off traffic at the report timescale (−8 points on the 8-site network).
- Any result outside the simulator: no testbed; 3 to 8 sites; Poisson arrivals plus one on/off pattern; deadlines 200 and 300 ms.

## 6. Still to check before the paper (†)

- DAGOR (Zhou et al., SoCC 2018) and SEDA (Welsh et al.): venue, year, pages.
- Kelly, Key and Zachary, "Distributed admission control": venue, volume, pages (the paper exists, Microsoft Research copy ✓; venue not checked).
- Pre-Congestion Notification architecture (IETF): RFC number and year.
- These are only needed if the related-work section keeps them.

## Sources (opened or searched on 21 Nov 2026)

- Mitzenmacher 2001: https://www.eecs.harvard.edu/~michaelm/postscripts/tpds2001.pdf
- Mitzenmacher 2000: https://www.eecs.harvard.edu/~michaelm/abstracts/tpds2000.html
- Dahlin 2000: https://researchr.org/publication/Dahlin00/bibtex
- Prequal: https://usenix.org/conference/nsdi24/presentation/wydrowski
- nginx smooth WRR: https://mdounin.ru/hg/nginx/file/c90801720a0c/src/http/ngx_http_upstream_round_robin.h
- Breakwater: https://www.usenix.org/conference/osdi20/presentation/cho
- C3: https://usenix.org/conference/nsdi15/technical-sessions/presentation/suresh
- Kelly, Key, Zachary: https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/dac.pdf
- CATS problem statement and requirements: https://datatracker.ietf.org/doc/html/draft-ietf-cats-usecases-requirements-12 and RFC 10054 https://www.rfc-editor.org/rfc/rfc10054.txt
- draft-luan-cats-catpts-01: https://ftp.kaist.ac.kr/ietf/draft-luan-cats-catpts-01.txt
- Earlier CATS survey (RFC 10053, drafts, LSQ, Liyanage): `claude/cats-contribution-directions.md`, `claude/cats-v6-phase3-baselines.md`
