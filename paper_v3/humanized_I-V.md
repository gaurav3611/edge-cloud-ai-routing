# I. Introduction

Workloads based on inferencing are moving towards the "edge" in networks. Video analytics applications, voice assistant applications and robotic control applications require their responses to be delivered within tens to hundreds of milliseconds, and all of these applications take input from consumers who are subject to increasing amounts of privacy regulation. The response has been an architecture known as "edge-cloud collaborative computing," which uses a three-tiered architecture: the first tier consists of edge servers that are located near the consumer and perform nearly all of the workload; when edge servers cannot handle additional workload, the workload is passed to other edge servers or to the cloud [@liu2025eccc]. Each individual edge server is relatively small and the set of edge servers is heterogeneous; however, there exists a significant amount of combined idle capability across the entire set of servers if incoming requests can be routed quickly to available servers.

EPARA [@epara2025] is a recent example of this type of architecture. EPARA classifies inference services along two dimensions: whether a service is latency-sensitive or frequency-sensitive, and whether it needs less or more than one graphics processing unit (GPU). Based upon this classification, EPARA selects a parallelization strategy for each class. A decentralized request handler is used to determine when to keep a request at its current location and when to forward the request to a peer edge server. When deciding where to send a request, the request handler uses a probabilistic decision rule where the probability of sending the request to a given peer is directly related to that peer's idle goodput. At a regular interval, EPARA also uses a placement mechanism to move models closer to demand. EPARA was evaluated through comparison to several previously developed architectures for serving both edge and centralized inference services [@epara2025].

All of the previous architectures [@interedge], [@galaxy], [@servp], [@alpaserve], [@usher] were designed so that any server that hosts a model can receive any request. In real-world scenarios this assumption often does not hold. For example, imaging data collected by a hospital may need to be processed only by certified operators. Similarly, residency restrictions may confine data processing within an organizational or governmental boundary [@gdpr], [@hummel2021]. A router that does not enforce these types of constraints can indicate high levels of goodput even though some portion of the traffic being served could be considered unlawful. <!--R-->A second implicit assumption concerns energy: many edge sites are power-capped, solar-powered or battery-backed, and steering work toward servers with spare energy, as energy-aware offloading does for mobile devices [@mao2016harvest], looks like an obvious refinement.

As such, we address request routing as a constrained optimization problem: maximize timely service while ensuring all requests are processed within their respective trust boundaries. Two questions then emerge. How much timely service does a fast decentralized router lose by complying with the trust constraints, measured against unconstrained and centralized references, and which routing rules minimize this loss? Additionally, does energy awareness in making offload decisions help, and at what levels of available supply?

The authors' contributions include:

- **Model.** The authors provide a model for trust-constrained routing of categorized edge inference. This includes multi-level security labels (clearance and trust domain) and the stated threat model; the threat model describes how ingress servers forward data even if they are not permitted to process it. Additionally, a closed-form expression is provided for the violation rate of trust-oblivious routing, demonstrating that the violation rate is determined by the distribution of the labels, and not by the behavior of the router itself (Section III).
- **Design.** The authors extend capacity-proportional offloading with a hard trust filter and a best-fit clearance preference, which each server switches on once it has observed sufficient sensitive traffic. Furthermore, SLO-aware (Service Level Objective) admission is used to shed, or send to the cloud, those requests that can no longer meet their SLO deadlines. Each decision takes approximately tens of microseconds of local processing time (Section IV).
- **Evaluation against strong references.** The authors evaluate TRACE against five reference routers: trust-filtered round-robin, power-of-two-choices and join-the-shortest-queue routing, static per-tier pools, and a centralized dispatcher that has perfect knowledge. The evaluation uses thirty evaluation seeds, and all comparisons use Holm-corrected paired tests. Additionally, the authors vary the correlation between data sensitivity and ingress clearance, the proportion of sensitive traffic, overload conditions, state staleness, placement, the availability of a cloud fallback, network topology and every routing parameter (Section VI).
- **Energy-aware routing as a testable hypothesis.** Five energy-aware variants are described and evaluated, including a feasibility oracle that has perfect knowledge of energy, over supply ratios below and above demand, constant and phase-shifted solar supply, <!--R-->and short and long battery buffers; the mechanisms behind the results (load dispersion, availability and forwarding) are measured directly (Section VII).

<!--R-->All results come from simulation with documented, assumed parameters at the scale of EPARA's testbed. They are not hardware measurements and should not be compared in absolute terms with EPARA's reported numbers.

# II. Background and Related Work

<!--R-->**Categorized parallel inference at the edge.** EPARA [@epara2025] categorizes inference tasks along two axes and applies five operators accordingly: batching, multi-task co-location, model parallelism, multi-frame batching and request-level data parallelism. It couples this allocator with a decentralized request handler that offloads a request to a peer with probability proportional to the peer's idle goodput, a submodular service-placement algorithm with a $1/(1+P)$ guarantee [@fisher1978submodular], and ring-based state synchronization. Its handler, like those of the edge systems it compares against (InterEdge [@interedge], Galaxy [@galaxy], SERV-P [@servp]) and of datacenter serving systems (AlpaServe [@alpaserve], USHER [@usher], Nexus [@nexus], SHEPHERD [@shepherd], Clockwork [@clockwork], INFaaS [@infaas]), treats every server that hosts a model as a valid destination. We study EPARA's *request-handling* layer. Its operators are not modelled mechanistically: we reduce each category to a fixed slot and service-time profile (Section V), so batching gains and co-location interference are outside the scope of this paper.

<!--R-->**Edge-cloud collaborative intelligence.** A recent survey [@liu2025eccc] organizes ECCC research into model optimization, AI-driven resource management and privacy/security enhancement, and names heterogeneity management and real-time scheduling as open challenges. Model partitioning between device and cloud [@neurosurgeon] and collaborative edge LLM inference [@edgeshard] address *where to compute a model*; we address *where a request may be served*.

<!--R-->**Multilevel security and data sovereignty.** Eq. (2) is a two-attribute instance of multilevel-security labelling. The Bell–LaPadula model [@bell1973] assigns subjects and objects levels from an ordered set and forbids a subject from reading data above its clearance; Denning's lattice model [@denning1976] generalizes this to a lattice of security classes along which information may flow only upward. Our clearance levels form such an ordered set, and the trust-domain condition for the highest sensitivity adds a compartment, so the eligible destinations of a request are exactly the servers whose (clearance, domain) label dominates the request's label. Work on data sovereignty [@hummel2021] and legal frameworks like the GDPR [@gdpr] make the domain compartment necessary because certain data can only be processed under the authority of specific organizations or jurisdictions. This paper does not add to this theoretical framework; it uses its most basic formulation as a hard constraint inside a fast decentralized router and then reports on the cost of doing so.

**Privacy- and security-aware fog and edge scheduling.** Prior work classifies applications by privacy level and restricts where they can run. Singh et al. [@singh2021fog] divided applications into three categories, public, semi-private and private, which were to be hosted on untrusted, semi-trusted and trusted resources, respectively; interactive and batch jobs were placed by a distributed orchestrator that weighed each job's performance against its security requirements. PASHE [@fizza2018pashe] schedules real-time public, semi-private and private jobs across edge micro data centers and the cloud, and executes private jobs with tight deadlines on the user's local micro data center. Our clearance levels and sensitivities follow the same conceptual approach. The differences are in the setting and the questions asked: we route individual requests of categorized GPU inference services, decentralized and in microseconds, from periodically synchronized state; we add a domain compartment for the most sensitive data; and we quantify the cost of compliance against both centralized and unconstrained references rather than proposing placement heuristics. Learning-based privacy-aware offloading [@min2019privacy] protects information leaked by the act of offloading, and federated learning [@mcmahan2017fl] keeps training data local. We address a different point in the design space, per-request decentralized routing of categorized inference, and we compare against the decentralized and centralized references a practitioner would consider (round-robin, power of two choices, join-the-shortest-queue, static pools and a centralized dispatcher with perfect information).

<!--R-->**Admission control in inference serving.** Clockwork [@clockwork] and Nexus [@nexus] drop requests that can no longer meet their SLO instead of executing them late, because late work consumes capacity without contributing goodput. We find that the same principle is decisive for decentralized edge routing near saturation (Section VI-D).

<!--R-->**Energy-aware offloading.** Offloading with energy-harvesting devices has been studied with Lyapunov optimization [@mao2016harvest], and carbon-aware provisioning has been proposed for datacenter LLM serving [@ecoserve]. A natural extension of EPARA's handler is to scale the offload score by each peer's energy headroom. We test this hypothesis in Section VII.

**Load balancing with stale information.** Assigning jobs to the server that appears to have the lowest workload using stale information leads to herd behavior, whereas randomized assignment degrades smoothly [@mitzenmacher2000old]. The power of two choices [@mitzenmacher2001two] and join-the-shortest-queue [@winston1977] are the standard references. EPARA computes idle goodput from periodically synchronized state, and we include both methods as trust-filtered baselines.

# III. System Model and Problem Formulation

## A. Edge servers, trust and energy

Our system contains a set $\mathcal{N}$ of $N$ edge servers. Each edge server $j$ has $S_j$ GPU slots (MPS partitions, four per GPU), a clearance level $c_j\in\{0,1,2\}$ and an administrative trust domain $d_j$. The clearance represents the degree of certification held by the operator of the server (e.g., public, certified, regulated), while the domain describes either ownership or jurisdiction. There is a network latency $\ell_{ij}$ between servers $i$ and $j$. There is also an optional cloud tier, which offers $S_\mathrm{cl}$ slots at a one-way latency $\ell_\mathrm{cl}$. The cloud tier has clearance $c_\mathrm{cl}=1$ (a certified service provider) but does not belong to any edge domain.

Each server receives energy at a mean rate $\bar P_j=\kappa_j S_j P_s$, where $P_s$ is the power consumed by one active slot and $\kappa_j$ is the supply fraction. The supply comes either from a constant source or from a solar source, $P_j(t)=\bar P_j\,(1+\sin(2\pi t/T_\mathrm{s}+\varphi_j))$, with phases $\varphi_j$ that vary across three time zones. Each server $j$ maintains an energy buffer $E_j(t)\le B_j$ as reserve capacity. This buffer is replenished by the supply and charged $P_s$ per slot-second when a job is committed. We use the *supply ratio* to describe the overall scarcity in the system:
$$\Phi=\frac{\sum_j \bar P_j}{\rho\sum_j S_j P_s},\qquad\qquad(1)$$
the average supply divided by the power required to serve the offered load $\rho$; if $\Phi<1$, no router is capable of serving all of the demand.

We investigate two possible results when a server's buffer becomes depleted: (i) *soft throttling*, where, once $E_j/B_j<5\%$, requests run 1.6$\times$ slower and streams cannot start; and (ii) *hard outage*, where, once $E_j/B_j\le 1\%$, a server accepts no additional jobs until it has recharged its buffer to 30%. Both models allow jobs that have already been admitted to complete execution; the energy for these jobs is charged at admission, and thus the buffer may be overdrawn, which models a protected battery reserve that is repaid before the server recovers.

## B. Requests and categories

A request $r$ arrives at its *ingress* server $o_r$ at time $a_r$ for service $l_r$ and carries a sensitivity $s_r\in\{0,1,2\}$. Following EPARA, there are four classes of services: latency-sensitive (LS) or frequency-sensitive (FS) services, each further divided into services that need less than one GPU and services that need more than one GPU. Service $l$ occupies $m_l$ slots for $\tau_l$ seconds (for an FS stream, for the duration of the stream). An LS request is successful as long as it finishes by $a_r+\mathrm{SLO}_l$. Similarly, an FS stream is successful as long as it starts within $\mathrm{SLO}_l$ and runs without throttling.

## C. Trust constraint and threat model

<!--R-->A server $j$ may *process* request $r$ only if
$$\mathrm{elig}(r,j)=\big[c_j\ge s_r\big]\wedge\big([s_r<2]\vee[d_j=d_{o_r}]\big).\qquad\qquad(2)$$
<!--R-->Sensitivity-1 data therefore requires a certified operator, and sensitivity-2 data must, in addition, stay within the ingress server's domain. If an ineligible server processes a request, that represents a trust violation. In lattice terms [@bell1973], [@denning1976], Eq. (2) admits exactly the servers whose (clearance, domain) label dominates the label of the request.

<!--R-->*Processing versus relaying.* We distinguish processing, which requires the plaintext input, from relaying. The device encrypts the payload end-to-end for the processing server and sends only the routing metadata ($l_r$, $s_r$, $d_{o_r}$) in the clear; a server that merely forwards the request, including an ineligible ingress server, never sees the plaintext. Eligibility is therefore checked only where the request is processed. Deployments that cannot provide end-to-end encryption must instead let devices attach only to eligible ingress servers; this corresponds to full alignment ($\lambda=1$) in Section VI-C, where we show that offloading still produces violations unless the router enforces (2).

<!--R-->*Threat model.* Operators of ineligible servers are honest-but-curious: they forward correctly and do not collude to break encryption. Clearance and domain labels are bound to each server by remote attestation [@coker2011] (for example, a trusted execution environment [@costan2016sgx] reporting a measured software stack and a certificate issued by the domain's policy authority), and the routing state carries only attested labels. Compromised attestation, side channels, traffic analysis of metadata and misbehaving eligible servers are out of scope. Under these assumptions, a router that enforces (2) at the processing server cannot cause a violation, whereas a router that ignores (2) causes one whenever it processes a request at an ineligible server.

## D. Objective: goodput subject to compliance

Now let $y_r\in\{0,1\}$ denote whether $r$ met its SLO, and $v_r\in\{0,1\}$ whether $r$ was processed at an ineligible server. We view routing as a constrained optimization problem:
$$\max\ G=\frac{1}{T}\sum_r y_r\quad\text{s.t.}\quad v_r=0\ \ \forall r.\qquad\qquad(3)$$
We compare routers that satisfy the constraint by construction on their SLO attainment $G\,T/|\mathcal R|$ and on its category-balanced counterpart (the average of the four per-category values), so that the numerous short classification requests do not dominate. The cost of compliance is the difference in raw SLO attainment between a router without the constraint and one with it; we measure it both for EPARA-style routing and for a centralized dispatcher with perfect knowledge. A router that ignores (2) is not a feasible solution of (3), and we therefore present such routers only as reference points, using compliant goodput $G_c=\frac1T\sum_r y_r(1-v_r)$ only to illustrate what they deliver lawfully.

## E. How large are violations without a trust filter?

The violation rate of a trust-oblivious router depends on the label distributions rather than on how the router is designed. If a request is processed at its ingress server, and sensitivities are assigned independently of the ingress clearance,
$$V_\mathrm{loc}=\sum_{c} \Pr[c_{o}=c]\,\Pr[s_r>c]\qquad\qquad(4)$$
(no domain violation can occur at the ingress server). With clearances 0/1/2 with probability 0.3/0.4/0.3 and sensitivities with probability 0.60/0.24/0.16, we get $V_\mathrm{loc}=0.3\cdot0.40+0.4\cdot0.16=18.4\%$; when destinations are drawn uniformly at random, we obtain $0.24\cdot0.3+0.16\cdot(1-0.3/3)=21.6\%$. In this paper, we report the simulated violation rates of trust-oblivious routers solely as a check of these values, not as findings. As well, because sensitive information mostly originates at high-clearance sites, we also let a fraction $\lambda$ of requests originate only at servers whose clearance covers their sensitivity; $V_\mathrm{loc}$ then falls to $(1-\lambda)V_\mathrm{loc}$, but offloaded requests can still violate the constraint (Section VI-C).

TABLE I. Notation.

| Symbol | Meaning |
|---|---|
| $\mathcal N$, $N$ | set and number of edge servers |
| $S_j$ | GPU slots (MPS partitions) of server $j$ |
| $c_j$, $d_j$ | clearance level and trust domain of server $j$ |
| $\ell_{ij}$; $S_\mathrm{cl}$, $\ell_\mathrm{cl}$ | latency between $i$ and $j$; cloud slots and latency |
| $P_s$, $\kappa_j$, $\bar P_j$ | slot power, supply fraction, mean supply |
| $E_j(t)$, $B_j$; $\Phi$ | energy buffer level and capacity; supply ratio, Eq. (1) |
| $o_r$, $a_r$, $l_r$, $s_r$ | ingress server, arrival time, service and sensitivity of $r$ |
| $m_l$, $\tau_l$, $\mathrm{SLO}_l$ | slots, service time and SLO of service $l$ |
| $\mathrm{elig}(r,j)$ | trust eligibility, Eq. (2) |
| $y_r$, $v_r$ | SLO met; trust violation |
| $\lambda$ | share of requests whose ingress clearance covers their sensitivity |
| $\hat\sigma_{ij}$, $\hat h_{ij}$ | $i$'s view of $j$'s spare slots and energy headroom |
| $H$, $\Delta$ | state-sync period; capacity horizon |
| $w_{ij}(r)$ | offload weight, Eq. (5) |
| $\gamma$, $q^\ast$, $\hat q_i$ | best-fit strength, enabling threshold, local sensitive-share estimate |
| $K_{\max}$ | maximum forwards per request |

# IV. Design of TRACE

![Fig. 1. Overview of TRACE. Left: edge servers carry a clearance level $c$ and a trust domain $d$ (fill colour) and synchronize state over a ring every $H$ seconds; the cloud tier performs periodic placement and serves as a fallback for requests of sensitivity at most 1. A request may only be processed at an eligible server (green); processing a sensitivity-2 request at a clearance-0 server is blocked (red). Ingress servers relay ciphertext only. Right: the per-request decision path executed by every server.](../figures_v3/fig_arch.png){width=6.5in}

Fig. 1 illustrates the overall design. TRACE replaces EPARA's request handler; the category profiles and the placement of services are treated as fixed. Each server $i$ maintains a view of every peer $j$ with two items: the number of spare slots $\hat\sigma_{ij}$ over a horizon $\Delta=0.5$ s, and whether the peer is currently online. This information is taken from the last ring synchronization and debited by the offloads that server $i$ has performed since then.

## A. Trust-filtered, capacity-proportional offloading

When server $i$ (the ingress server or a forwarder) receives a request $r$, it processes the request locally if all of the following conditions hold: $i$ is eligible, $i$ is currently online, $i$ hosts $l_r$, and $i$ can meet the SLO. If any of these conditions does not hold, server $i$ selects a peer $j$ with probability proportional to
$$w_{ij}(r)=\mathrm{elig}(r,j)\cdot\phi(\hat\sigma_{ij},m_{l_r})\cdot\frac{1}{1+\ell_{ij}/\ell_0}\cdot\gamma_i^{\,\max(0,\,c_j-s_r)},\qquad\qquad(5)$$
where $\phi(\sigma,m)=\sigma$ if $\sigma\ge m$ and $0.05\,\sigma$ otherwise (a preference for peers on which the request fits), $\ell_0=20$ ms, and a peer $j$ is excluded from consideration if it has already been visited by this request or does not host $l_r$. A request is forwarded at most $K_{\max}=2$ times. Rather than always selecting the peer with the largest weight, we sample from the candidate peers; in doing so, the router remains robust to stale views [@mitzenmacher2000old]. Without the final factor ($\gamma_i=1$), (5) is the trust filter (TF).

## B. Adaptive best-fit clearance

Non-sensitive requests that run on high-clearance servers consume the only capacity that sensitive requests are allowed to use. The final factor in (5), with $\gamma_i<1$, makes a request prefer the *lowest* clearance that suffices rather than any eligible server; the fragmentation argument for best-fit bin packing applies here as well. Best-fit only pays when there is significant sensitive traffic, and it loses SLO attainment when there is little sensitive traffic, because it concentrates non-sensitive load on low-clearance servers. Therefore, TRACE turns it on and off as needed: each server keeps an exponentially weighted estimate $\hat q_i$ of the share of sensitive requests it receives (weight 0.002 per request, a memory of a few seconds) and uses $\gamma_i=\gamma$ if $\hat q_i\ge q^\ast$ and $\gamma_i=1$ otherwise. Both $\gamma=0.3$ and $q^\ast=30\%$ were chosen on tuning seeds that are separate from the evaluation seeds (Section V).

## C. SLO-aware admission and cloud fallback

If no eligible peer remains, or $K_{\max}$ has been reached, and the request cannot meet its SLO at the current server, TRACE sends the request to the cloud if the cloud is eligible and can meet the SLO; otherwise, it sheds the request (rejects it immediately, so the client may choose to retry or degrade). Executing such a request late would take up slots without adding goodput and would delay the requests queued behind it. We show in Section VI-D that this rule, which we apply to every router in our main experiments so that the comparison is fair, removes the collapse of capacity-aware routing at saturation.

**Algorithm 1: TRACE request handling at server $i$** (input: request $r$, visited set $V$, forward count $k$)

1. If $\mathrm{elig}(r,i)$, $i$ is online, hosts $l_r$ and the SLO is feasible at $i$: process $r$ at $i$ and return.
2. If $k<K_{\max}$: compute $w_{ij}(r)$ by (5) for all $j\notin V$; if $\sum_j w_{ij}>0$, sample $j\sim w_{ij}/\sum_{j'}w_{ij'}$, debit $\hat\sigma_{ij}$, forward $r$ to $j$ with $V\cup\{j\}$ and $k+1$, and return.
3. If the cloud is eligible for $r$ and can meet the SLO: send $r$ to the cloud and return.
4. Shed $r$.

**Computational complexity and state.** The cost of one decision is $O(N)$ arithmetic on the local view, and no communication occurs. Each server keeps a few bytes of synchronized state per peer (spare slots, online status and an estimated backlog); clearance and domain labels are static and exchanged only once, at attestation. A ring synchronization therefore moves $O(N)$ bytes per server per period, about 1.2 kB per hop for $N=120$ servers and $H=1$ s. Latency, not volume, limits scale: one circulation of the ring takes $N$ hops, roughly 1.5 s for $N=120$ servers under our latency model, so views become older as $N$ grows. Our simulator synchronizes all views instantaneously every $H$ seconds and studies staleness through $H$ (Section VI-E); for large $N$, gossip or tree-based dissemination would be needed.

## D. Energy-aware variants (hypotheses tested in Section VII)

We test whether the offload score should consider the energy headroom $\hat h_{ij}=E_j/B_j$ (from the last synchronization) by evaluating five extensions of TF. **EW** multiplies (5) by $\hat h_{ij}^{\beta}$ ($\beta=1$) and hands a request off a server whose own headroom falls below $\theta=0.25$ when its SLO slack exceeds 50 ms and a peer with headroom above 0.5 fits; **EB** uses a barrier weight $\min\{1,\max(0.05,\hat h_{ij}/0.3)\}$; **EC** treats energy as a capacity dimension, replacing $\hat\sigma_{ij}$ by $\min(\hat\sigma_{ij},\hat e_{ij})$, where $\hat e_{ij}$ is the number of slots that $j$'s energy can power over the horizon; **EW-bounded** multiplies (5) by $(1+\hat h_{ij})/2\in[0.5,1]$, so that energy can only deprioritize, never exclude, a peer, and does no hand-off; and **EF** is a feasibility oracle that uses the true, current buffer of every server and excludes a server (including the local one) only if it cannot power the job without throttling or outage, with no preference among feasible servers.

# V. Evaluation Methodology

**Simulator.** We extended our lightweight event-driven simulator (Python/NumPy). It implements the full routing logic for each request, but models computation and transmission through service-time and latency tables, the technique EPARA employs for its large-scale study [@epara2025]. We do not model EPARA's operators: each class has a fixed number of slots and a fixed service time after operator selection, so batching benefits and co-location interference are not modelled. Unless otherwise specified, every server offers all services (full replication); Section VI-F also evaluates partial placement. All parameters (Table II) are assumptions based on the scale of EPARA's P100 testbed, not measurements, so the absolute numbers are not directly comparable to EPARA's. The simulator, experiment scripts and raw results are available at https://github.com/gaurav3611/edge-cloud-ai-routing.

**Decoupling trust and energy.** When servers are energy-capped below the offered load, energy scarcity lowers every router's SLO attainment and masks the impact of the trust constraint. As a result, the trust experiments (Section VI) are carried out with unconstrained energy, and the impact of energy is examined on its own in Section VII, where the supply ratio $\Phi$ of Eq. (1) is controlled explicitly.

TABLE II. Simulation parameters (defaults; ranges studied in parentheses).

| Parameter | Value |
|---|---|
| Servers $N$ | 30 (10–120) |
| GPUs per server; slots | 2 or 4 (uniform); 4 slots per GPU |
| Clearance $c_j$ | 0/1/2 w.p. 0.30/0.40/0.30 (also 0.5/0.3/0.2 and 0.2/0.4/0.4) |
| Trust domains | 3, uniform (1, 2, 5) |
| Network latency | 2 ms + 20 ms × distance (unit square) |
| Sensitivity mix $s_r$ | 0/1/2 w.p. 0.60/0.24/0.16 (sensitive share 0–80%, split 3:2) |
| Origin–sensitivity alignment $\lambda$ | 0 (0, 0.5, 1) |
| LS<1 (classification) | 1 slot, 30 ms, SLO 150 ms, 20% of demand |
| LS>1 (LLM chat) | 8 slots, 800 ms, SLO 3 s, 30% |
| FS<1 (video detection) | 2 slots, stream 5–15 s, start SLO 200 ms, 30% |
| FS>1 (video segmentation) | 8 slots, stream 5–10 s, start SLO 300 ms, 20% |
| Arrivals | Poisson; log-normal ingress hot spots; ±80% sinusoidal bursts, period 20 s |
| Sync period $H$; horizon $\Delta$ | 1 s (0.1–2 s); 0.5 s (0.1–1 s) |
| $K_{\max}$; $\ell_0$; fit factor | 2 (1–4); 20 ms (5–80 ms); 0.05 (0–1) |
| Best-fit $\gamma$; threshold $q^\ast$ | 0.3; 30% (tuned on separate seeds) |
| Cloud tier (Sec. VI-F) | 96 slots, 40 ms one-way, clearance 1, no domain |
| Slot power $P_s$ | 60 W (250 W GPU / 4) |
| Supply fraction $\kappa_j$ | 0.45/0.70/1.0 w.p. 0.35/0.35/0.30, rescaled to the target $\Phi$ |
| Supply profile | constant, or solar: period 120 s, amplitude 1, three phases |
| Buffer $B_j$; initial charge | 120 s of mean supply (20 s, 600 s); uniform 20–100% |
| Run length; seeds | trust: 60 s (10 s warm-up), 30 seeds; energy: 180 s (60 s warm-up), 10 seeds |

**Load.** The offered load $\rho$ is the demanded slot-seconds per second divided by the total number of slots. Shares of demand are measured in slot-seconds; by request count, classification requests are close to 99% of all requests, which is why we present the category-balanced metric.

**Routers.** *Trust-oblivious references:* local only; decentralized round-robin (RR), an InterEdge-style baseline [@interedge]; EPARA-style capacity-proportional offloading, i.e., (5) without the trust and best-fit factors; and a *centralized oracle* that forwards every request, with perfect instantaneous knowledge of every server's slot occupancy, to the server with the earliest finish time (no hop limit). *Compliant routers:* TF; TRACE; TF-RR (round-robin over eligible peers); TF-P2C (power of two choices [@mitzenmacher2001two]: two eligible peers sampled uniformly, forward to the one with the smaller synchronized backlog); TF-JSQ (join-the-shortest-queue [@winston1977]: the eligible peer with the smallest synchronized backlog plus latency); *static pools*, the partitioning a practitioner would deploy, in which a request may only be processed by servers whose clearance equals its sensitivity (and, for sensitivity 2, within its domain), with capacity-proportional offloading inside the pool; and the *centralized oracle with trust*, which restricts the oracle to eligible servers and, among those that meet the SLO, prefers the least sufficient clearance. The oracles are strong references, not proven optima: greedy earliest-finish dispatch has no look-ahead. All routers share the same admission rule (Section IV-C), category profiles, topology and arrival sequence for a given seed.

**Metrics.** We present raw and compliant SLO attainment (per request and category-balanced), compliant goodput, violation rate, forwards and shed requests per request, and routing time per decision. For energy, we also report the throttled fraction, server availability (outage model), the coefficient of variation (CV) of per-server utilization and availability, and energy per successful request.

**Seeds, run length and statistics.** The trust experiments use 30 evaluation seeds (20 for the staleness and placement studies, and 10 for the parameter-sensitivity and scale experiments); each seed generates a new topology and arrival sequence. Runs last 60 s with a 10 s warm-up, covering three 20 s burst cycles. Energy experiments use 10 seeds and 180 s runs with a 60 s warm-up and a random initial charge, so that measurements start after the initial transient. $\gamma$ and $q^\ast$ were chosen on 10 separate tuning seeds (1001–1010) that are never used for evaluation. We report means with 95% Student-t confidence intervals over seeds. Differences are paired over seeds and tested with the Wilcoxon signed-rank test; we declare a family of tests for each experiment and correct within it with Holm's method [@holm1979], reporting Holm-adjusted $p$-values ($p_H$). With 30 seeds the smallest two-sided $p$ possible is about $2\times10^{-9}$, so corrected tests have power. To separate the effects of topology and workload, a variance-decomposition experiment runs 5 arrival sequences on each of 10 topologies.
