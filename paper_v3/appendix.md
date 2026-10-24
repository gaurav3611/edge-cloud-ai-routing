# Appendix A: Parameter Sensitivity

Table IX varies one routing or topology parameter at a time around the defaults of Table II ($\rho=0.8$, 10 seeds). TRACE is ahead of TF in every setting.

TABLE_PARAM_PLACEHOLDER

# Appendix B: Simulator Details

The simulator processes arrivals in time order. Every $H$ seconds it refreshes the view of every server: spare slots over the next $\Delta$ seconds, computed by clipping each slot's remaining busy time to the horizon; the time until $m$ slots become free, for $m\in\{1,2,8\}$, used as the backlog estimate by TF-P2C and TF-JSQ; the online status; and, for the energy variants, the energy headroom $E_j/B_j$. Between refreshes, a server debits its view of a peer by the work it has itself sent there, so different servers hold different views. A service occupying $m$ slots starts when its $m$ earliest-free slots are available. Energy is charged when a job is admitted, at $P_s$ per slot for its duration, and the buffer refills continuously with the (constant or solar) supply. Network latency is added per forward. The centralized oracles evaluate every eligible, online server hosting the service with exact slot and energy state and the latency from the ingress server. Each seed fixes the topology, placement and arrival sequence, which are identical across routers, so comparisons are paired. A request is counted once, after the warm-up, as successful if it met its SLO, as a violation if it was processed at an ineligible server, and as shed if it was rejected.
