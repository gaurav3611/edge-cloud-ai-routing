---
title: "Response to the Reviewer"
subtitle: "TRACE: Trust-Constrained, Category-Aware Request Routing for AI Inference in Edge-Cloud Collaborative Systems"
---

We thank the reviewer for a detailed and constructive report. The comments led us to extend the simulator, add every requested baseline and reference, re-run all experiments with more seeds, longer runs and multiple-comparison correction, and rewrite large parts of the manuscript. Several conclusions changed as a result, and we report those changes openly below. Reviewer comments are in italics; section, figure and table numbers refer to the revised manuscript.

**Summary of the main changes**

1. The problem is now posed as goodput maximization *subject to* zero trust violations (Sec. III-D). The violation rate of trust-oblivious routing is derived in closed form (Eq. (4)) and reported only as a check, not as a finding.
2. New baselines and references: trust-filtered round-robin, power-of-two-choices and join-the-shortest-queue routing; static per-tier pools; and a centralized oracle with perfect information, with and without the trust constraint, which measures the cost of compliance (Sec. V, VI-A).
3. A new experiment varies the alignment $\lambda$ between data sensitivity and ingress clearance (Sec. VI-C).
4. An explicit threat model, processing-versus-relaying semantics and multilevel-security, data-sovereignty and fog-scheduling related work (Sec. II, III-C).
5. SLO-aware admission (shedding requests that can no longer meet their SLO) fixes the collapse at saturation and is now part of TRACE (Sec. IV-C, VI-D).
6. Best-fit clearance is tuned on separate seeds and enabled adaptively (Sec. IV-B, VI-B).
7. The energy study was redesigned: the supply ratio $\Phi$ is controlled, sufficient-energy and phase-shifted solar regimes are added, runs are longer, the mechanism is measured directly, and two new variants are tested (Sec. VII).
8. Statistics: 30 evaluation seeds, 60 s runs (three burst cycles), Holm correction within declared families, and a topology-versus-workload variance decomposition (Sec. V, VI-G).
9. Trust experiments now run with unconstrained energy, so energy scarcity no longer confounds them; energy is studied separately.
10. A cloud fallback tier, partial placement and a one-at-a-time sensitivity analysis of every routing parameter (Sec. VI-F, VI-G, Table IX).

# Major concern 1: The headline result is largely true by construction

> *The 17–20% violation rate follows directly from the assumed marginals … This is arithmetic on the assumptions, not a finding.*

We agree. Sec. III-E now derives the violation rate of trust-oblivious routing in closed form, $V_\mathrm{loc}=\sum_c\Pr[c_o=c]\Pr[s_r>c]$ (Eq. (4)), which gives 18.4% for local service and 21.6% for a uniformly random destination under our label distributions, matching the reviewer's arithmetic. The text states explicitly that the simulated rates are reported only as a check of these values: at $\rho=0.8$, local-only service violates for 18.7% of the requests it processes (10.7% of all requests, because it sheds 43%), and the EPARA-style router for 19.9%. Violation rates no longer appear in the abstract or the contributions as a result.

> *The assumptions are also unrealistic. Sensitivity is independent of the origin server … The paper should vary the correlation between origin clearance and sensitivity, since it would collapse the violation rate.*

We added the alignment parameter $\lambda$, the share of requests that originate only at servers whose clearance covers their sensitivity (Sec. III-E, VI-C, Fig. 4). With $\lambda=1$, local service causes no violations, as the reviewer expected. Offloading, however, still does: the EPARA-style router violates for 13.5% of requests and even a centralized dispatcher with perfect information for 9.9%, because sensitive requests that cannot be served at their ingress server are offloaded to whichever peer has capacity. Alignment therefore reduces violations but does not remove the need for a trust filter in the router. The compliant routers are almost unaffected by $\lambda$ (TRACE 0.960, 0.960 and 0.958 at $\lambda=0$, 0.5 and 1).

> *Comparing a router with a hard constraint against one that ignores the constraint … will always favor the former. The more informative framing is constrained optimization …*

We adopted this framing (Sec. III-D, Eq. (3)). Compliant routers are compared with each other, and the cost of compliance is measured as the gap between the raw SLO attainment of an unconstrained router and a compliant one, both for a centralized oracle with perfect information and for EPARA-style decentralized routing. At the default setting, compliance costs 1.2 points with perfect information and 2.7 points for decentralized routing; the cost grows to 10.4 points (oracle) when 80% of the traffic is sensitive (Sec. VI-A, VI-B). Compliant goodput of trust-oblivious routers is still reported, but only as a reference, and the text says that it compares a feasible and an infeasible solution.

# Major concern 2: Missing baselines and upper bounds

> *There is no trust-filtered power-of-two-choices or join-shortest-queue baseline.*

Both are added (TF-P2C and TF-JSQ, Sec. V). They act on a synchronized backlog estimate and are evaluated in every main experiment. At $\rho=0.8$, TF-JSQ is statistically tied with TRACE (0.956 vs. 0.960 compliant SLO, $p_H=0.08$), and on the category-balanced metric it is 1.0 point ahead ($p_H=0.002$); we report this plainly. At $\rho=1.0$ and 1.2, TRACE is ahead of TF-JSQ by 8.1 and 14.3 points and of TF-P2C by 8.1 and 8.2 points ($p_H<10^{-7}$), and TF-JSQ is also more sensitive to stale state (Sec. VI-E).

> *There is no centralized or oracle trust-aware router to show how close TRACE is to optimal.*

We added a centralized dispatcher with perfect, instantaneous knowledge of every server's slot occupancy, no hop limit and earliest-finish-time dispatch, in a trust-constrained version (with best-fit tie-breaking) and an unconstrained one. Below saturation, TRACE is 0.8 to 2.9 points below the compliant oracle (Sec. VI-A). We are careful not to call it an optimum: greedy dispatch has no look-ahead or admission policy, and in overload TRACE exceeds it (0.895 vs. 0.859 at $\rho=1.0$). The manuscript calls it a strong reference, not an upper bound.

> *There is no static partitioning baseline (dedicated pools per sensitivity tier) …*

Added (Sec. V, VI-A, VI-B). Static pools perform poorly when the traffic mix and the pool sizes diverge (0.673 at the default mix and 0.156 with no sensitive traffic) but are statistically tied with TRACE when 60–80% of traffic is sensitive, where the pools happen to match the traffic. We discuss this trade-off in Sec. VIII.

> *Round-robin without a trust filter is a weak straw man for the trust question.*

Agreed. Trust-oblivious round-robin is kept only as a reference; the comparison for the trust question uses TF-RR (round-robin over eligible peers) and the other trust-filtered baselines.

# Major concern 3: The trust model has a conceptual gap at the origin

> *A request's raw data first arrives at the origin server … Either devices attach only to eligible servers, or forwarding must be secured, and the paper should say which.*

Sec. III-C now distinguishes processing, which requires the plaintext, from relaying. Devices encrypt payloads end-to-end for the processing server and expose only routing metadata (service, sensitivity, ingress domain), so a forwarding server, including an ineligible ingress server, never sees the plaintext; eligibility is checked where the request is processed. For deployments without end-to-end encryption, devices must attach only to eligible ingress servers; this is exactly the $\lambda=1$ case of the new alignment experiment, where offloading still causes violations unless the router enforces (2).

> *Clearance and domain labels are assumed honest. No attestation or threat model is given …*

Sec. III-C adds a threat model: operators of ineligible servers are honest-but-curious; labels are bound to servers by remote attestation (e.g., a TEE reporting a measured software stack and a certificate from the domain's policy authority) and the routing state carries only attested labels; compromised attestation, side channels, metadata traffic analysis and misbehaving eligible servers are out of scope.

> *Eq. (1) resembles multilevel-security (Bell–LaPadula) style labeling. The related work should cite MLS, data-sovereignty, and security-aware fog/edge scheduling literature …*

Added to Sec. II and III-C: Bell–LaPadula and Denning's lattice model (our eligibility rule admits exactly the servers whose (clearance, domain) label dominates the request's label), the data-sovereignty review of Hummel et al., and security- and privacy-aware fog scheduling (Singh et al., IEEE TSC; PASHE). We note that these fog schedulers already map public/semi-private/private tasks to untrusted/semi-trusted/trusted resources, and we position our work against them: per-request decentralized routing of categorized GPU inference in microseconds, a domain compartment, and a measured cost of compliance.

# Major concern 4: The energy experiments cannot support the broad conclusion

> *Aggregate scarcity … even "cap scale 1.0" is energy-deficient … The interesting case is heterogeneous surplus and deficit with sufficient aggregate energy …*

The reviewer is right that the original setting was energy-deficient throughout ($\Phi\approx0.87$ at "cap scale 1.0"). We now define the supply ratio $\Phi$ (Eq. (1)) and control it explicitly. Sec. VII evaluates constant supply at $\Phi=0.6$, 0.9 and 1.2, and phase-shifted solar supply (three time zones, so some sites are in surplus while others are in deficit) at $\Phi=0.9$ and 1.2. The result changes with the regime, and the broad claim of the first version no longer holds. With scarce energy and soft throttling, energy weighting is harmful (TF+EW −9.2 and TF+EC −15.8 points at $\Phi=0.6$). With hard outages it is level with TF at $\Phi=0.6$ (+0.1 points) and slightly ahead at $\Phi=0.9$ and 1.2 (+0.8 and +0.7 points), none significant after Holm correction. With sufficient supply, constant or solar, every variant is within 0.7 points of TF.

> *Unrealistic timescales … the energy results are dominated by the initial transient.*

Energy runs now last 180 s, measurements start after a 60 s warm-up, initial charge is randomized (20–100%), and the default buffer holds 120 s of mean supply. A separate experiment varies the buffer from 20 s to 600 s (Sec. VII). With a 20 s buffer, the soft-throttling penalty of TF+EW remains (−8.7 points); with a 600 s buffer, all variants coincide with TF. The large outage penalties of the first version (−10 to −28 points) do not reproduce with longer runs, randomized initial charge, SLO-aware admission and views that know which peers are offline; we report this explicitly in the revised Section VII. We acknowledge in Sec. VIII that the solar profile is compressed in time relative to a real day.

> *Untested mechanism … report per-server load and availability dispersion; add an EW variant that deprioritizes but never refuses; show an oracle-forecast variant.*

All three were added. We report the coefficient of variation of per-server utilization and availability for every energy variant; EW-bounded multiplies the weight by $(1+h)/2\in[0.5,1]$, never excludes a peer and does no hand-off; and EF is a feasibility oracle that knows every server's true current energy and excludes a server only if it cannot power the job. The measurements support the mechanism only for the soft-throttling regime: at $\Phi=0.6$, TF+EW raises the utilization CV from 0.20 to 0.26 and forwards per request from 0.70 to 0.97. Under outages the mechanism is the opposite of what the first version claimed: energy weighting raises availability (0.888 to 0.957 at $\Phi=0.9$) and reduces drain events. EW-bounded is harmless but never significantly better than TF, and even the feasibility oracle with perfect energy information does not improve on TF (it loses 3.4 points at $\Phi=0.6$ with soft throttling).

> *Unspecified outage semantics. What happens to in-flight jobs when a server goes offline?*

Sec. III-A now specifies it: energy is charged when a job is admitted, admitted jobs always run to completion, and a buffer may be overdrawn (modelling a protected battery reserve that is repaid before the server recovers). An offline server only stops accepting new work.

> *Overreaching abstract. The causal claim … should be softened or backed by the above experiments.*

The abstract and Sec. VII now state the energy result conditionally on the supply regime and report the directly measured mechanism instead of the earlier causal claim. The earlier statement that staleness is not the cause has been removed from the abstract; Sec. VII reports that the TF+EW versus TF difference is +1.1 points with fresh state and +0.8 points with stale state under solar supply and outages.

# Major concern 5: Best-fit clearance evidence is thin and partly selected

> *γ = 0.3 was tuned at a single sensitivity level (60%) … the abstract's "up to 5.1 points" is the maximum over the sweep …*

$\gamma$ and the enabling threshold were re-selected on 10 tuning seeds (1001–1010) that are never used for evaluation, over five sensitive shares (Table IV). $\gamma=0.3$ had the largest mean gain across shares, and the gain changed sign between 20% and 40%, which fixed the threshold at 30%. All reported results use 30 different evaluation seeds. The abstract no longer reports a maximum over a sweep.

> *At the default mix … not significant (+0.026 ± 0.041, p = 0.065). The sweep reports +0.027 ± 0.015, p = 0.006 at what should be the same 40% operating point … Please reconcile this.*

The two operating points were not identical. The default mix was 0.60/0.25/0.15, whereas the sweep split the sensitive share 3:2 and used 0.60/0.24/0.16. Both used the same ten seeds and topologies, but the different sensitivity labels changed the realized outcomes, and with ten seeds the paired difference was dominated by two outlying seeds in the load experiment (−0.102 and +0.129). This produced the threefold difference in confidence-interval width. The revised study uses one mix (0.60/0.24/0.16) everywhere and 30 seeds; at 40% sensitive traffic, best-fit now adds +0.010 ± 0.003 ($p_H=10^{-6}$) in both experiments.

> *Gains vanish in the category-balanced metric, and best-fit costs −0.036 at zero sensitivity. The title-level framing … overstates a contribution that is conditional and modest.*

We agree and changed the design and its framing. TRACE now enables best-fit adaptively from a locally estimated sensitive share, which removes the cost at low sensitivity (always-on best-fit costs 1.3 points with no sensitive traffic, $p_H=2\times10^{-8}$; adaptive best-fit is indistinguishable from TF, $p_H=1$). The gain is modest (+1.0 to +2.4 points at 40–80% sensitive traffic) and is now significant on the category-balanced metric as well (+0.9 to +1.9 points). The paper describes best-fit as an optional refinement; the core contributions are the trust filter and SLO-aware admission (Sec. VIII).

# Major concern 6: Overload behavior undercuts the design

> *At ρ = 1.0, TF/TRACE raw SLO is no better than round-robin … That is a design flaw … The claim that uniform probing "did not help" is given with no data. Include it, or fix the fallback (exploration, P2C) and evaluate it.*

We agree it was a design flaw, and we traced it to admission rather than to peer selection. Routers that execute requests after they can no longer meet their SLO collapse at saturation; this affects every router, including the centralized oracle (Table V). With SLO-aware admission, which sheds such requests or sends eligible ones to the cloud, compliant SLO attainment at $\rho=1.0$ rises by 51 to 76 points for every router, and TRACE becomes the best router at $\rho=1.0$ (0.895) and remains ahead at $\rho=1.2$ (0.733, tied with TF there). Table V also reports the requested fallback data: probing a uniformly random eligible peer is neutral (within ±1.1 points, $p_H\ge0.25$), and a P2C fallback on synchronized backlog is harmful (−1.1 to −5.9 points). With shedding in place, fresher state now helps rather than hurts at saturation (Sec. VI-E).

# Major concern 7: Statistical practice

> *Dozens of Wilcoxon tests … no multiple-comparison correction … Use more seeds (30 or more) and correct.*

All trust experiments now use 30 evaluation seeds (20 for staleness and placement, 10 for parameter sensitivity and scale). We declare a family of tests for each experiment and apply Holm's correction within it; Holm-adjusted $p$-values are reported throughout. With 30 seeds the smallest attainable two-sided $p$ is about $2\times10^{-9}$, and all main comparisons remain significant after correction, except TRACE versus TF-JSQ below saturation, where the two are tied. Energy experiments use 10 seeds with 180 s runs.

> *The CIs are very wide … which shows strong topology dependence. Report results across topology families or sensitivity-to-topology analyses.*

We added a variance-decomposition experiment with five arrival sequences on each of ten topologies (Sec. VI-G). Topology explains 88% of the variance of the EPARA-style router's compliant SLO and 58% of TRACE's. TRACE's gain over the EPARA-style router is positive on every topology (+12.6 to +18.5 points) and uncorrelated with the share of capacity eligible for the most sensitive class. The one-at-a-time sensitivity study also varies the clearance mix and the number of domains, which are the main topology parameters.

> *Runs of 30 s cover about 1.25 burst cycles, which is short.*

Trust runs now last 60 s after a 10 s warm-up (three burst cycles); energy runs last 180 s after a 60 s warm-up.

# Major concern 8: Fidelity of "EPARA-style"

> *EPARA's operators … are abstracted into fixed slot and time tables … Claiming to "keep EPARA's operator layer" is therefore nominal.*

We agree and removed the claim. The paper now states in Sec. II and V that EPARA's operators are reduced to fixed per-category slot and service-time profiles, that batching gains and co-location interference are not modelled, and that the study concerns the request-handling layer only.

> *Model placement per server is also unspecified …*

The default is now stated explicitly (every server hosts every service), and Sec. VI-F adds partial placement, in which each service is hosted on half of the servers (at least one per domain).

> *Despite the "edge-cloud" title, no cloud offload path is modeled … Cloud is the natural fallback for non-sensitive overflow.*

We added a cloud tier with 96 slots, 40 ms one-way latency and clearance 1 outside every edge domain, so it is eligible for sensitivity 0 and 1 only (Sec. III-A, IV-C, VI-F). It raises TRACE's compliant SLO from 0.961 to 0.970 with full placement and from 0.906 to 0.932 with partial placement, while serving 0.9–2.7% of requests.

# Minor issues

- *2.3% vs. 2.2%.* The reviewer is right: (1737−1698)/1737 = 2.2%. All numbers were regenerated from the new experiments, and every number in the revised text is produced by the analysis script from the raw results.
- *Hard-outage deltas differ from Table VII.* The energy section and its tables are now generated from the same data by the same script, so text and tables agree.
- *Per-decision timing and state-sync cost.* Sec. IV-C now quantifies synchronization: a few bytes per peer, about 1.2 kB per hop per period for $N=120$; and it notes that ring propagation latency (about 1.5 s for 120 servers), not volume, limits scale. Sec. VIII lists the instantaneous-synchronization assumption as a limitation.
- *Only γ is tuned.* Table IX varies $K_{\max}$, $\ell_0$, $\Delta$ and the 0.05 fit factor one at a time. TRACE stays between 0.919 and 0.981 compliant SLO, ahead of TF in every setting; $K_{\max}=1$ has the largest effect (−4.3 points).
- *Sensitivity mix, clearance mix and domain count are fixed.* The sensitive share is varied from 0 to 80% (Sec. VI-B), and the clearance mix (two alternatives) and the number of domains (1, 2, 3, 5) are varied in Table IX. More domains reduce the capacity eligible for sensitivity-2 requests (TRACE 0.981 with one domain, 0.942 with five).
- *Table II glitch and [FILL] placeholders.* Table II was rebuilt; we checked the author block and the whole manuscript for placeholders.
- *Lab-notebook tone.* We removed the process narrative ("our original proposal", "our earlier experiments") and present the energy result as a test of a stated hypothesis (Sec. IV-D, VII).

We hope that the revised manuscript addresses the reviewer's concerns. The simulator, experiment scripts, analysis script and raw results are available in the public repository (branch revision-v3).
