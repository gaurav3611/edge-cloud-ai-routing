# Findings (v2: 1,740 runs, 10 seeds, 30 servers unless noted; assumed profiles)
Full statistics: STATS.md. Paper: paper/main.pdf. Superseded Phase-1 notes are in git-less history only (results.csv).

1. Trust violations: trust-oblivious routers serve 17-20% of requests at ineligible servers at every load
   (local-only 16.6%, EPARA-style 17.7-20.0%, round-robin 17.9-20.4%). The trust filter removes all of them.
2. Compliant goodput at rho=0.8: TRACE 1698 req/s vs EPARA-style 1391 (+22%); EPARA-style raw goodput 1737.
   TRACE - EPARA-style compliant SLO: +0.159 (p=0.002, 10/10 seeds); significant at every load.
3. Best-fit clearance (gamma=0.3) over plain trust filter: +0.027 (p=0.006) at 40% sensitive, +0.051 (p=0.002)
   at 60%; not significant at the default mix (+0.026, p=0.065) or at 80%; -0.036 (n.s.) with no sensitive traffic.
   Category-balanced gains smaller and not significant -> enable best-fit when >= ~30% of traffic is sensitive.
4. Cost of compliance: at 80% sensitive traffic, raw SLO 0.883 (EPARA, 41% violations) vs 0.572 (TF).
5. Energy-aware routing (negative result): no variant beats TF significantly. Soft model: TF+EW -0.10 at cap x0.35
   (p=0.002); TF+EC within +/-0.025 (n.s.). Hard outage, cap <= 0.7: EW -0.18..-0.23, EB -0.10..-0.14,
   EC -0.23..-0.28 (all p=0.002); availability 0.47 (TF) vs 0.36-0.40.
6. Not herding: penalty under outage grows as sync gets fresher (EW: -0.17 at H=2 s -> -0.39 at H=0.1 s).
   All policies consume the same energy (~10 kW, spill <= 0.1%); TF buys 9.1 J per good request vs 16.7 J (EW).
7. Saturation (rho=1.0): fresher state lowers capacity-aware routing (TF 0.289 at H=1 s -> 0.176 at H=0.1 s)
   because the 0.5 s capacity view reads ~0 and forwarding stops. Old "RR wins at saturation" result was mostly the
   shared round-robin pointer (+0.057 compliant SLO, p=0.014); the per-server RR is now the baseline.
8. Scale: TRACE compliant SLO 0.854 (N=10) -> 0.933 (N=120); routing 20 -> 51 us per request (Python).
