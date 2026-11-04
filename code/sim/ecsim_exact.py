"""
ecsim_exact.py - revision simulator. Derived from ecsim_variants.py; every default reproduces it exactly
(tests/test_regression.py). New, all opt-in:
  event_mode="exact"       each hop, view refresh and snapshot is its own timed event
  energy_model="bounded"   energy-conserving: throttled power scales down, admission needs energy, debt is bounded
  ov_slot=True             crypto delay occupies the GPU slot instead of preceding service
  owner_cross=x            share of requests whose device-selected owner domain differs from the ingress domain
  q_mode, q_hyst           definition of the sensitive-share estimate, hysteresis around the threshold
  policies tf_rjsq, tf_p3c, pashe_a, singh_a; flags local_bf, large_jsq="8", trunk, adm_big, adm_small

ecsim.py (v3) - event-driven edge(-cloud) inference routing simulator.

The EPARA operator layer (BS/MT/MP/MF/DP) is NOT modelled mechanistically: each service
category is reduced to a fixed (slots, service time) profile, i.e. the output of operator
selection is assumed, and batching gains / co-location interference are not modelled.
All parameters are ASSUMED (see the paper, Table II).

Routing policies (Sim(..., policy=...))
  trust-oblivious references
    local      never offload
    rr         decentralized round-robin (per-server pointer)
    rr_g       round-robin with a pointer shared by all servers (global coordination; reference)
    epara      EPARA-style capacity-proportional offloading
    oracle_u   centralized dispatcher with perfect, fresh state, no trust constraint
  trust-compliant (zero violations by construction)
    tf         EPARA-style + hard trust filter
    trace      TRACE: tf + best-fit clearance enabled adaptively (local sensitive-share estimate)
    tera       tf + best-fit clearance with a fixed gamma (always on)
    tf_rr      round-robin over eligible peers
    tf_p2c     power-of-two-choices over eligible peers on synchronized backlog
    tf_jsq     join-shortest-(estimated)-queue over eligible peers on synchronized backlog
    static     static partitioning: a request is served only by servers whose clearance
               equals its sensitivity (dedicated pools per tier), capacity-proportional inside
    oracle_c   centralized dispatcher with perfect, fresh state, trust filter + best-fit tie-break
  energy-aware variants of tf
    ew         energy weight h^beta (+ retention theta)
    eb         energy barrier weight
    ec         energy as a capacity dimension
    ewd        bounded deprioritisation: weight (1+h)/2, never zero, no retention
    ef         feasibility oracle: peers (and the local server) are used only if their TRUE
               current energy can power the job without throttling/outage; no preference
    ew_only    energy weight without trust filter
Overload fallback (fallback=...): 'none' | 'uniform' | 'p2c'  (used when no eligible peer
fits in the local view).
"""
import heapq
import time
import numpy as np

SLOTS_PER_GPU = 4
P_SLOT = 60.0
# name, category, slots m, run time (s), SLO (s), is_stream, slot-second share
SERVICES = [
    ("cls", "LS<1", 1, 0.030, 0.15, False, 0.20),
    ("llm", "LS>1", 8, 0.800, 3.00, False, 0.30),
    ("det", "FS<1", 2, None, 0.20, True, 0.30),
    ("big", "FS>1", 8, None, 0.30, True, 0.20),
]
STREAM_DUR = {"det": (5, 15), "big": (5, 10)}
SENS_P = [0.60, 0.24, 0.16]          # default sensitivity mix (40% sensitive, s1:s2 = 3:2)
TRUST = {"tracex", "tf_sjsq", "tf_rjsq", "tf_p3c", "pashe_a", "singh_a", "tf", "trace", "tera", "tf_rr", "tf_p2c", "tf_jsq", "static", "static_sized", "oracle_c",
         "ew", "eb", "ec", "ewd", "ef"}
ENERGY = {"ew", "eb", "ec", "ewd", "ef", "ew_only"}
CAPPROP = {"epara", "tf", "trace", "tera", "static", "ew", "eb", "ec", "ewd", "ef", "ew_only"}


LITE = {"llm": (4, 0.7), "big": (4, 0.7)}   # PLACEHOLDER lite variant: slots, service-time factor (assumed)
FLAGS = dict(feas=False, large_jsq=False, resv=0.0, adfit=False, frag=False, pred=False, ewd=False,
             no_load=False, no_net=False, lite=False, fit_small=None, fit_large=None, netfit=False,
             jsq_bf=None, local_bf=False, trunk=0.0, trunk_hard=False, adm_big=None, adm_small=None,
             age_large=True, age_jsq=False)      # whether a backlog read subtracts view age (estimator sensitivity)
THROTTLE = 1.6                       # slowdown under throttling; bounded power is P_SLOT / THROTTLE
REQ_STATE = ("now", "proc", "_dc_ctx", "_lat", "_slack", "_net", "counting")     # per-request fields on self


def build_topology(n, rng, clear_p=(0.30, 0.40, 0.30), n_dom=3,
                   cap_levels=(0.45, 0.7, 1.0), cap_p=(0.35, 0.35, 0.30)):
    gpus = rng.choice([2, 4], size=n)
    slots = gpus * SLOTS_PER_GPU
    clear = rng.choice([0, 1, 2], size=n, p=list(clear_p))
    dom = rng.integers(0, n_dom, size=n)
    capfrac = rng.choice(list(cap_levels), size=n, p=list(cap_p))
    pos = rng.random((n, 2))
    lat = 0.002 + 0.020 * np.sqrt(((pos[:, None] - pos[None]) ** 2).sum(-1))
    phase = rng.integers(0, 3, size=n) * (2 * np.pi / 3)        # 3 "time zones" for solar
    return dict(n=n, slots=slots, clear=clear, dom=dom, capfrac=capfrac, lat=lat,
                n_dom=n_dom, sphase=phase)


class Sim:
    def __init__(self, topo, policy, rho, T, seed, beta=1.0, theta=0.25, outage=False,
                 hsync=1.0, gamma=0.3, warm=None, fallback="none", corr=0.0,
                 kmax=2, l0=0.02, horizon=0.5, fitfac=0.05, cloud=None, place=1.0,
                 buf_s=20.0, init="0.6", solar_amp=0.0, solar_period=120.0,
                 bf_thresh=0.30, bf_alpha=0.002, sens_p=None, energy=True, okey='eft', late='serve',
                 pool_mix=None, adm_util=None, ov_proc=0.0, ov_fwd=0.0, ov_scope="sens", run_mult=1.0,
                 burst_sync=False, ring=False, trace_energy=False, bin_s=None,
                 vflags=None, burst_amp=0.8, burst_period=20.0, svc_share=None, net_var=0.0, net_kappa=5.0, record=False,
                 event_mode="batch", energy_model="legacy", e_floor=0.01, ov_slot=False, owner_cross=0.0,
                 q_mode="count", q_hyst=0.0, rjsq_eps=0.01, snap_dt=0.05, age_hist=False):
        assert event_mode in ("batch", "exact") and energy_model in ("legacy", "bounded") and q_mode in ("count", "slotsec")
        self.event_mode, self.bounded, self.e_floor = event_mode, energy_model == "bounded", e_floor
        self.ov_slot, self.owner_cross, self.q_mode, self.q_hyst, self.rjsq_eps = ov_slot, owner_cross, q_mode, q_hyst, rjsq_eps
        self.snap_dt, self.owner_seed = snap_dt, seed + 31337
        self.vage_sum, self.vage_n, self.bf_switch = 0.0, 0, 0
        self.age_hist, self.vage_bins = age_hist, {}
        self.ledger = dict(init=0.0, income=0.0, spill=0.0, charged=0.0)
        self.cat_shed, self.cat_recov, self.cat_kmax = {}, {}, {}
        self.vf = dict(FLAGS); self.vf.update(vflags or {})
        self.burst_amp, self.svc_share, self.record = burst_amp, svc_share, record
        self.burst_period = burst_period
        self.net_var, self.net_kappa = net_var, net_kappa
        self.netseed = seed + 555
        # audit-only options; every default reproduces ecsim.py v3 exactly (see test_regression.py)
        self.pool_mix, self.adm_util = pool_mix, adm_util
        self.ov_proc, self.ov_fwd, self.ov_scope, self.run_mult = ov_proc, ov_fwd, ov_scope, run_mult
        self.burst_sync, self.ring, self.trace_energy, self.bin_s = burst_sync, ring, trace_energy, bin_s
        self.late = late
        self.eon = energy
        self.okey = okey
        self.t = topo
        n = topo["n"]
        self.n = n
        self.pol = policy
        self.rho, self.T = rho, T
        self.warm = (T / 6.0) if warm is None else warm
        self.rng = np.random.default_rng(seed)
        self.beta, self.theta, self.gamma = beta, theta, gamma
        self.outage, self.hsync = outage, hsync
        self.fallback = fallback
        self.corr = corr
        self.kmax, self.l0, self.hor, self.fitfac = kmax, l0, horizon, fitfac
        self.sens_p = list(sens_p) if sens_p is not None else list(SENS_P)
        self.bf_thresh, self.bf_alpha = bf_thresh, bf_alpha
        self.trust = policy in TRUST
        S = np.array(topo["slots"], int)
        self.S = S
        self.Smax = int(S.max())
        F = np.full((n, self.Smax), np.inf)
        for j in range(n):
            F[j, :S[j]] = 0.0
        self.F = F
        # placement: each service hosted on a random fraction of servers (>=1 per domain)
        self.host = np.ones((n, len(SERVICES)), bool)
        if place < 1.0:
            prng = np.random.default_rng(seed + 7777)
            for l in range(len(SERVICES)):
                h = prng.random(n) < place
                for d in range(topo["n_dom"]):
                    ids = np.where(topo["dom"] == d)[0]
                    if len(ids) and not h[ids].any():
                        h[prng.choice(ids)] = True
                self.host[:, l] = h
        clear, dom = topo["clear"], topo["dom"]
        # true eligibility per (sensitivity, origin domain)
        self.EL = {(s, d): (clear >= s) & ((s < 2) | (dom == d))
                   for s in range(3) for d in range(topo["n_dom"])}
        if policy == "static":
            self.RM = {(s, d): (clear == s) & ((s < 2) | (dom == d))
                       for s in range(3) for d in range(topo["n_dom"])}
        elif policy == "static_sized":
            tier = self._size_pools(pool_mix if pool_mix is not None else self.sens_p)
            self.tier = tier
            self.RM = {(s, d): (tier == s) & ((s < 2) | (dom == d))
                       for s in range(3) for d in range(topo["n_dom"])}
        elif self.trust:
            self.RM = self.EL
        else:
            allm = np.ones(n, bool)
            self.RM = {(s, d): allm for s in range(3) for d in range(topo["n_dom"])}
        self.excess = {s: np.maximum(clear - s, 0) for s in range(3)}
        # energy
        self.pbar = topo["capfrac"] * S * P_SLOT
        self.bcap = self.pbar * buf_s
        if init == "rand":
            self.level = self.bcap * np.random.default_rng(seed + 99).uniform(0.2, 1.0, n)
        else:
            self.level = self.bcap * float(init)
        self.ledger["init"] = float(self.level.sum())
        self.lastu = np.zeros(n)
        self.samp, self.sper = solar_amp, solar_period
        self.sph = topo["sphase"]
        self.offl = np.zeros(n, bool)
        self.offtime = np.zeros(n)
        self.spill = 0.0
        self.income = 0.0
        # cloud tier (clearance cl, outside every trust domain)
        self.cloud = cloud
        if cloud:
            self.cF = np.zeros(int(cloud["slots"]))
        # views (observer x target)
        self.sp = np.tile(S.astype(float), (n, 1))
        self.esp = self.sp.copy()
        self.hd = np.ones((n, n))
        self.bk = np.zeros((n, n, 3))      # estimated wait for m=1,2,8 at last sync
        self.tsync = 0.0
        self.rr_ptr = 0
        self.rr_ptrs = np.arange(n)
        self.sshare = np.full(n, 0.4)       # TRACE: local estimate of sensitive share
        self.bf_on = self.sshare >= bf_thresh + q_hyst
        self.counting = False
        self.t_dec = 0.0
        self.n_dec = 0
        self.busy = np.zeros(n)             # committed slot-seconds per server (measured)
        self.avs = []
        self.n_down = 0
        self.st = dict(n=0, good=0, cgood=0, viol=0, thr=0, energy=0.0, hops=0, cloud=0,
                       drop=0, by_cat={})
        self.dc = {}                        # violation decomposition counters
        self.L = topo["lat"].copy()         # true latency now
        self.Lv = topo["lat"].copy()        # latency as seen by routers
        self.base_lat = topo["lat"]
        self.Lew = np.ones(n)               # per-server congestion estimate (EWMA of synced samples)
        self.cong = np.ones(n)
        self.nrng = np.random.default_rng(self.netseed)
        self.rec = {}                       # cat -> list of (latency, wait)
        self.shed_n = self.shed_feas = self.degraded = 0
        self.fleet = np.ones(n)             # per-observer EWMA of the free-capacity share (adfit="ewma")
        self._net = 0.0
        self.proc = None
        self.now = 0.0
        self.bins = {}
        self.en = dict(n=0, low=0, empty=0, hsum=0.0, first=np.full(n, np.nan), series=[])
        self.hist = []
        if ring:
            hop = np.array([topo["lat"][j, (j + 1) % n] for j in range(n)])
            self.age = np.zeros((n, n))     # age[i, j]: ring travel time from j to observer i
            for j in range(n):
                a, i = 0.0, j
                for _ in range(n - 1):
                    a += hop[i]; i = (i + 1) % n
                    self.age[i, j] = a
            self.ring_time = float(hop.sum())

    def _size_pools(self, mix):
        """Dedicated pools sized to a traffic mix; a server may only join a tier <= its clearance."""
        S, clear, dom = self.S, self.t["clear"], self.t["dom"]
        tier = np.zeros(self.n, int)
        free = np.ones(self.n, bool)
        for d in range(self.t["n_dom"]):       # tier 2 first: only same-domain clearance-2 servers qualify
            need = mix[2] * S[dom == d].sum()
            have = 0
            for j in np.flatnonzero((clear == 2) & (dom == d)):
                if have >= need:
                    break
                tier[j] = 2; free[j] = False; have += S[j]
        need, have = mix[1] * S.sum(), 0
        for j in sorted(np.flatnonzero(free & (clear >= 1)), key=lambda j: clear[j]):
            if have >= need:
                break
            tier[j] = 1; free[j] = False; have += S[j]
        return tier

    # ---------------- energy ----------------
    def _inc(self, j, a, b):
        p = self.pbar[j]
        if self.samp <= 0:
            return p * (b - a)
        w = 2 * np.pi / self.sper
        return p * ((b - a) + self.samp / w * (np.cos(w * a + self.sph[j]) - np.cos(w * b + self.sph[j])))

    def _refill(self, j, t):
        a = self.lastu[j]
        if t > a:
            inc = self._inc(j, a, t)
            new = self.level[j] + inc
            self.ledger["income"] += inc; self.ledger["spill"] += max(0.0, new - self.bcap[j])
            if self.counting:
                self.income += inc
                self.spill += max(0.0, new - self.bcap[j])
            self.level[j] = min(self.bcap[j], new)
            self.lastu[j] = t

    def head(self, j, t):
        if not self.eon:
            return 1.0
        self._refill(j, t)
        return max(self.level[j], 0.0) / self.bcap[j]

    def down(self, j, t):
        if not self.outage or not self.eon:
            return False
        h = self.head(j, t)
        if self.offl[j] and h >= 0.30:
            self.offl[j] = False
        elif not self.offl[j] and h <= 0.01:
            self.offl[j] = True
            if self.counting:
                self.n_down += 1
        return bool(self.offl[j])

    def efeasible(self, j, t, m, dur):
        """TRUE energy can power m slots for dur without dropping below the threshold."""
        if not self.eon:
            return True
        self._refill(j, t)
        need = m * P_SLOT * dur - self._inc(j, t, t + dur)
        floor = self.e_floor * self.bcap[j] if self.bounded else (0.05 if not self.outage else 0.01) * self.bcap[j]
        return self.level[j] - need >= floor

    # ---------------- state sync ----------------
    def _net_tick(self, t):
        """Two-state congestion per server: a link is as slow as its worse end. Views refresh at sync."""
        if self.net_var <= 0:
            return
        turn = self.nrng.random(self.n)
        stay = 1.0 - self.hsync / 10.0                              # mean dwell about 10 s
        on = self.nrng.random(self.n) < self.net_var
        c = np.where(turn < stay, self.cong, np.where(on, self.net_kappa, 1.0))
        self.cong = c
        m = np.maximum(c[:, None], c[None, :])
        self.L = self.base_lat * m
        if self.vf["pred"] == "sync":           # newest sample, as reported at this sync
            self.Lv = self.L
        elif self.vf["pred"] == "ewma":         # smoothed prediction of the next interval
            self.Lew += 0.3 * (c - self.Lew)
            self.Lv = self.base_lat * np.maximum(self.Lew[:, None], self.Lew[None, :])

    def refresh(self, t):
        self._net_tick(t)
        n, hor = self.n, self.hor
        back = np.clip(self.F - t, 0, hor)
        back[~np.isfinite(self.F)] = 0.0
        busy = back.sum(1)
        sp = np.maximum(0.0, self.S - busy / hor)
        hd = np.zeros(n)
        for j in range(n):
            hd[j] = 0.0 if self.down(j, t) else self.head(j, t)
        e_slots = (np.maximum(self.level, 0) + self.pbar * hor) / (P_SLOT * hor)
        es = np.where(hd == 0.0, 0.0, np.maximum(0.0, e_slots - busy / hor))
        if self.outage:
            sp = np.where(self.offl, 0.0, sp)
        srt = np.sort(self.F, axis=1)
        bk = np.stack([np.maximum(0.0, srt[:, m - 1] - t) for m in (1, 2, 8)], 1)
        bk[self.offl] = 1e3
        if self.ring:
            self.snap(t, sp, es, hd, bk)
            self._ring_views(t)
        else:
            self.sp[:] = sp; self.esp[:] = es; self.hd[:] = hd; self.bk[:] = bk
        self.tsync = t
        self.fleet += 0.3 * ((self.sp / self.S).mean(1) - self.fleet)   # only read when adfit="ewma"
        if self.trace_energy:
            self._trace_energy(t)
        if self.counting:
            self.avs.append(~self.offl)

    def snap(self, t, sp=None, es=None, hd=None, bk=None):
        """Store the true per-server state at time t for delayed ring views (no energy in ring runs)."""
        if sp is None:
            hor = self.hor
            back = np.clip(self.F - t, 0, hor)
            back[~np.isfinite(self.F)] = 0.0
            sp = np.maximum(0.0, self.S - back.sum(1) / hor)
            es, hd = sp.copy(), np.ones(self.n)
            srt = np.sort(self.F, axis=1)
            bk = np.stack([np.maximum(0.0, srt[:, m - 1] - t) for m in (1, 2, 8)], 1)
        self.hist.append((t, sp.copy(), es.copy(), hd.copy(), bk.copy()))
        tmin = t - self.ring_time - 1.0
        while len(self.hist) > 2 and self.hist[1][0] < tmin:
            self.hist.pop(0)

    def _ring_views(self, t):
        """View of j at observer i = j's state at t - age[i, j] (no extrapolation to the present)."""
        times = np.array([h[0] for h in self.hist])
        arr_sp = np.stack([h[1] for h in self.hist]); arr_bk = np.stack([h[4] for h in self.hist])
        ii = np.clip(np.searchsorted(times, t - self.age, side="right") - 1, 0, len(times) - 1)
        tgt = np.broadcast_to(np.arange(self.n), ii.shape)
        self.sp[:] = arr_sp[ii, tgt]
        self.esp[:] = self.sp
        self.bk[:] = arr_bk[ii, tgt]
        self.age_sum = getattr(self, "age_sum", 0.0) + float((t - times[ii]).mean())
        self.age_n = getattr(self, "age_n", 0) + 1

    def _trace_energy(self, t):
        """Buffer-occupancy record, sampled at every sync."""
        h = np.array([max(self.level[j], 0.0) / self.bcap[j] for j in range(self.n)])
        true = self.level / self.bcap if self.bounded else h     # bounded runs log the unclipped level, stability rule 3
        e = self.en
        new = np.isnan(e["first"]) & (h <= 0.05)
        e["first"][new] = t
        if self.counting:
            e["n"] += self.n; e["low"] += int((h < 0.05).sum()); e["empty"] += int((h <= 0.01).sum())
            e["hsum"] += float(h.sum())
        if int(t) % 30 == 0:
            e["series"].append((round(t, 1), round(float(true.mean()), 4), round(float(true.min()), 4)))

    # ---------------- local service ----------------
    def try_local(self, j, t, m, run, deadline, stream):
        f = self.F[j]
        if m == 1:
            idx = np.array([int(np.argmin(f))])
            st0 = f[idx[0]]
        else:
            idx = np.argpartition(f, m - 1)[:m]
            st0 = f[idx].max()
        start = max(t, st0)
        thr = self.head(j, t if self.bounded else start) < 0.05    # bounded: never read energy from the future
        self._slowed = thr and not stream
        r = run * (THROTTLE if self._slowed else 1.0)
        fin = start + r
        ok = ((start - t) <= deadline and not thr) if stream else (fin <= deadline)
        if ok and self.bounded and self.eon and not self.efeasible(j, t, m, run):
            ok = False                  # admission refused below the energy floor
        return ok, start, fin, thr, idx

    def commit(self, j, idx, start, fin, m):
        self.F[j, idx] = fin
        e = m * P_SLOT * (fin - start)
        if self.bounded:
            e /= THROTTLE if self._slowed else 1.0     # slower job, proportionally lower power, same energy
            self._refill(j, self.now_e)
        else:
            self._refill(j, start)
        self.level[j] -= e          # energy charged at commit; in-flight jobs always complete
        if self.eon:
            self.ledger["charged"] += e
        if self.counting:
            self.st["energy"] += e
            self.busy[j] += m * (fin - start)

    def cloud_try(self, t, m, run, deadline, stream):
        lat = self.cloud["lat"]
        f = self.cF
        idx = np.argpartition(f, m - 1)[:m] if m > 1 else np.array([int(np.argmin(f))])
        start = max(t + lat, f[idx].max())
        fin = start + run + lat
        ok = ((start - t) <= deadline) if stream else (fin <= deadline)
        return ok, start, fin, idx

    # ---------------- peer selection ----------------
    def mi(self, m):
        return 0 if m == 1 else (1 if m == 2 else 2)

    def est_start(self, cur, j, m):
        return max(0.0, self.bk[cur, j, self.mi(m)] - 0.0)

    def pick(self, cur, m, s, odom, l, visited, stream, run, t):
        t0 = time.perf_counter()
        p = self._pick(cur, m, s, odom, l, visited, stream, run, t)
        self.t_dec += time.perf_counter() - t0
        self.n_dec += 1
        if self.counting:
            a = t - self.tsync + (float(self.age[cur].sum()) / (self.n - 1) if self.ring else 0.0)
            self.vage_sum += a
            self.vage_n += 1
            if self.age_hist:
                b = int(a * 10)         # 100 ms bins
                self.vage_bins[b] = self.vage_bins.get(b, 0) + 1
        return p

    def _cand(self, cur, s, odom, l, visited):
        c = self.RM[(s, odom)] & self.host[:, l]
        c = c.copy()
        c[list(visited)] = False
        return c

    def _debit(self, cur, p, m, stream, run):
        d = m if stream else m * run / self.hor
        self.sp[cur, p] = max(0.0, self.sp[cur, p] - d)
        self.esp[cur, p] = max(0.0, self.esp[cur, p] - d)
        dur = run
        self.bk[cur, p, :] += m * dur / self.S[p]

    def _bf(self, cur):
        """Best-fit active at server cur. Without hysteresis this is the original threshold test."""
        if self.q_hyst <= 0:
            return self.sshare[cur] >= self.bf_thresh
        q, on = self.sshare[cur], self.bf_on[cur]
        new = (q >= self.bf_thresh - self.q_hyst) if on else (q >= self.bf_thresh + self.q_hyst)
        if new != on:
            self.bf_on[cur] = new
            self.bf_switch += int(self.counting)
        return new

    def _p2c(self, cur, c, m, stream, run, d=2):
        ids = np.flatnonzero(c)
        if len(ids) == 0:
            return None
        k = self.rng.choice(ids, size=min(d, len(ids)), replace=False)
        mi = self.mi(m)
        p = int(k[np.argmin(self.bk[cur, k, mi])])
        self._debit(cur, p, m, stream, run)
        return p

    def _pick(self, cur, m, s, odom, l, visited, stream, run, t, dry=False):
        pol = self.pol
        n = self.n
        if pol == "jsq":
            c = self._cand(cur, s, odom, l, visited)
            ids = np.flatnonzero(c)
            if len(ids) == 0:
                return None
            b = self.bk[cur, ids, self.mi(m)] + self.Lv[cur, ids]
            p = int(ids[np.argmin(b)])
            self._debit(cur, p, m, stream, run)
            return p
        if pol in ("rr", "tf_rr"):
            c = self._cand(cur, s, odom, l, visited)
            if not c.any():
                return None
            for _ in range(n):
                self.rr_ptrs[cur] = (self.rr_ptrs[cur] + 1) % n
                if c[self.rr_ptrs[cur]]:
                    return int(self.rr_ptrs[cur])
            return None
        if pol == "rr_g":
            c = self._cand(cur, s, odom, l, visited)
            if not c.any():
                return None
            for _ in range(n):
                self.rr_ptr = (self.rr_ptr + 1) % n
                if c[self.rr_ptr]:
                    return int(self.rr_ptr)
            return None
        if pol == "tf_p2c":
            return self._p2c(cur, self._cand(cur, s, odom, l, visited), m, stream, run)
        if pol == "tf_p3c":
            return self._p2c(cur, self._cand(cur, s, odom, l, visited), m, stream, run, d=3)
        if pol == "tf_rjsq":                    # random among near-minimum delays, breaks deterministic herding
            ids = np.flatnonzero(self._cand(cur, s, odom, l, visited))
            if len(ids) == 0:
                return None
            b = self.bk[cur, ids, self.mi(m)] + self.Lv[cur, ids]
            near = ids[b <= b.min() + self.rjsq_eps]
            p = int(self.rng.choice(near))
            self._debit(cur, p, m, stream, run)
            return p
        if pol == "pashe_a":                    # adapted from PASHE: private work stays near, public work spreads
            ids = np.flatnonzero(self._cand(cur, s, odom, l, visited))
            if len(ids) == 0:
                return None
            if s > 0:
                fit = ids[self.sp[cur, ids] >= m]
                p = int((fit if len(fit) else ids)[np.argmin(self.Lv[cur, fit if len(fit) else ids])])
            else:
                w = self.sp[cur, ids].copy()
                w = np.where(w >= m, w, w * self.fitfac) / (1.0 + self.Lv[cur, ids] / self.l0)
                if w.sum() <= 0:
                    return None
                p = int(self.rng.choice(ids, p=w / w.sum()))
            self._debit(cur, p, m, stream, run)
            return p
        if pol == "singh_a":                    # adapted from Singh et al.: lowest sufficient trust tier first
            ids = np.flatnonzero(self._cand(cur, s, odom, l, visited))
            if len(ids) == 0:
                return None
            ex = self.excess[s][ids]
            b = self.bk[cur, ids, self.mi(m)] + self.Lv[cur, ids]
            feas = (b if stream else b + run) <= self._slack
            tier = ex[feas].min() if feas.any() else ex.min()
            k = np.flatnonzero((ex == tier) & (feas if feas.any() else True))
            p = int(ids[k[np.argmin(b[k])]])
            self._debit(cur, p, m, stream, run)
            return p
        if pol == "tf_jsq":
            c = self._cand(cur, s, odom, l, visited)
            ids = np.flatnonzero(c)
            if len(ids) == 0:
                return None
            bk = self.bk[cur, ids, self.mi(m)]
            b = (np.maximum(0.0, bk - (t - self.tsync)) if self.vf["age_jsq"] else bk) + self.Lv[cur, ids]
            p = int(ids[np.argmin(b)])
            self._debit(cur, p, m, stream, run)
            return p
        if pol == "tf_sjsq":                    # soft JSQ: exponential weights on estimated delay
            c = self._cand(cur, s, odom, l, visited)
            ids = np.flatnonzero(c)
            if len(ids) == 0:
                return None
            b = self.bk[cur, ids, self.mi(m)] + self.Lv[cur, ids]
            w = np.exp(-(b - b.min()) / 0.05)
            p = int(ids[self.rng.choice(len(ids), p=w / w.sum())])
            self._debit(cur, p, m, stream, run)
            return p
        if pol == "tracex":
            return self._pick_x(cur, m, s, odom, l, visited, stream, run, t, dry)
        # capacity-proportional family
        c = self._cand(cur, s, odom, l, visited)
        if pol == "ec":
            w = np.minimum(self.sp[cur], self.esp[cur])
        else:
            w = self.sp[cur].copy()
        fits = (w >= m) & c
        w = np.where(w >= m, w, w * self.fitfac)
        w = w / (1.0 + self.Lv[cur] / self.l0)
        if pol in ("ew", "ew_only"):
            w = w * np.power(np.maximum(self.hd[cur], 1e-3), self.beta)
        elif pol == "eb":
            w = w * np.clip(self.hd[cur] / 0.3, 0.05, 1.0)
        elif pol == "ewd":
            w = w * (0.5 + 0.5 * self.hd[cur])
        elif pol == "ef":
            dur = run
            for j in np.flatnonzero(c):
                if not self.efeasible(j, t, m, dur):
                    c[j] = False
            fits &= c
        bf = (pol == "tera") or (pol == "trace" and self._bf(cur))
        if bf:
            w = w * np.power(self.gamma, self.excess[s])
        w = np.where(c, w, 0.0)
        if self.fallback != "none" and not fits.any() and c.any():
            if self.fallback == "uniform":
                p = int(self.rng.choice(np.flatnonzero(c)))
                self._debit(cur, p, m, stream, run)
                return p
            return self._p2c(cur, c, m, stream, run)
        tot = w.sum()
        if tot <= 0:
            return None
        cw = np.cumsum(w)
        p = int(np.searchsorted(cw, self.rng.random() * tot, side="right"))
        p = min(p, n - 1)
        if dry:
            return p
        self._debit(cur, p, m, stream, run)
        return p

    def _pick_x(self, cur, m, s, odom, l, visited, stream, run, t, dry):
        """TRACE variants. The trust mask is applied first and is never relaxed by any flag."""
        v = self.vf
        c = self._cand(cur, s, odom, l, visited)
        ids = np.flatnonzero(c)
        if len(ids) == 0:
            return None
        mi = self.mi(m)
        lat = self.Lv[cur, ids]
        age = (t - self.tsync) if v["age_large"] else 0.0
        wait = np.maximum(0.0, self.bk[cur, ids, mi] - age)
        if v["feas"]:                           # estimated SLO feasibility from the view
            slack = self._slack
            need = (lat + wait) if stream else (lat + wait + run)
            keep = need <= slack
            if not keep.any():
                return None
            ids, lat, wait = ids[keep], lat[keep], wait[keep]
        if v["jsq_bf"] is not None:             # JSQ on delay, plus a clearance-excess penalty in seconds
            b = wait + lat
            if self._bf(cur):
                b = b + v["jsq_bf"] * self.excess[s][ids]
            p = int(ids[np.argmin(b)])
        elif v["large_jsq"] and (m == 8 if v["large_jsq"] == "8" else m > 1):   # large jobs: shortest estimated start
            p = int(ids[np.argmin(wait + lat)])
        else:
            w = self.sp[cur, ids].copy() if not v["no_load"] else np.ones(len(ids))
            if not v["feas"] and not v["no_load"]:
                fit = self.fitfac
                if m < 8 and v["fit_small"] is not None:    # category-dependent fit
                    fit = v["fit_small"]
                elif m == 8 and v["fit_large"] is not None:
                    fit = v["fit_large"]
                if v["adfit"] == "ewma":        # smoothed load signal, damps sync-to-sync swings
                    fit = fit * 4 * float(self.fleet[cur])
                elif v["adfit"]:                # fallback weight shrinks as the view shows the fleet filling
                    fit = fit * 4 * float(np.mean(self.sp[cur] / self.S))
                if v["netfit"]:                 # distrust far fallbacks when the network is slow
                    fit = fit * float(self.base_lat[cur].mean() / self.Lv[cur].mean())
                w = np.where(w >= m, w, w * fit)
            if not v["no_net"]:
                w = w / (1.0 + lat / self.l0)
            if self._bf(cur):
                w = w * np.power(self.gamma, self.excess[s][ids])
            if v["ewd"]:
                w = w * (0.5 + 0.5 * self.hd[cur, ids])
            tot = w.sum()
            if tot <= 0:
                if v["no_load"]:
                    return None
                return None
            p = int(ids[min(int(np.searchsorted(np.cumsum(w), self.rng.random() * tot, side="right")), len(ids) - 1)])
        if not dry:
            self._debit(cur, p, m, stream, run)
        return p

    def _can_defer(self, cur, s, m, run, hops, t, stream, l, odom, visited):
        """Local-step refinements for tracex. True: forward although cur could serve now. Trust unaffected."""
        if hops >= self.kmax:
            return None
        v = self.vf
        free = int((self.F[cur] <= t).sum())
        S = int(self.S[cur])
        want = False
        if v["resv"] > 0 and self.excess[s][cur] > 0 and free - m < v["resv"] * S:
            want = True                         # keep the last slots of a high-clearance server for sensitive work
        if v["frag"] and run > 1.0 and m < 8 and free >= 8 and free - m < 8:
            want = True                         # a long small job would break the last whole 8-slot block
        if v["trunk"] > 0 and s == 0 and self.t["clear"][cur] > 0 and free - m < v["trunk"] * S:
            want = True                         # trunk reservation: public work leaves the last slots of cleared servers
        if v["local_bf"] and self._bf(cur) and self.excess[s][cur] > 0 \
                and self.rng.random() >= self.gamma ** self.excess[s][cur]:
            want = True                         # best-fit also on the local step, same factor as the offload weight
        if not want:
            return None
        return self._pick(cur, m, s, odom, l, visited, stream, run, t, dry=True)

    def _shed_check(self, t0, m, run, slo, stream, s, odom, l):
        """Was an eligible server truly able to meet the SLO when this request was shed? (diagnostic)"""
        c = self.EL[(s, odom)] & self.host[:, l]
        ids = np.flatnonzero(c)
        if not len(ids):
            return False
        kth = np.partition(self.F[ids], m - 1, axis=1)[:, m - 1]
        st = np.maximum(t0, kth)
        return bool(((st - t0 <= slo) if stream else (st + run <= t0 + slo)).any())

    # ---------------- centralized oracle ----------------
    def oracle(self, t0, o, l, m, run, slo, stream, s, odom):
        n = self.n
        if self.adm_util is not None and m == 8:
            fin_mask = np.isfinite(self.F)
            if (self.F[fin_mask] > t0).mean() >= self.adm_util:
                return False, False, 0, None    # reserved: large job refused above the utilisation cap
        c = self.host[:, l].copy()
        if self.pol == "oracle_c":
            c &= self.EL[(s, odom)]
        if self.outage:
            for j in np.flatnonzero(c):
                if self.down(j, t0):
                    c[j] = False
        ids = np.flatnonzero(c)
        lat = self.L[o, ids].copy()
        lat[ids == o] = 0.0
        best = None
        if len(ids):
            kth = np.partition(self.F[ids], m - 1, axis=1)[:, m - 1]
            start = np.maximum(t0 + lat, kth)
            h = np.array([self.head(j, st) for j, st in zip(ids, start)])
            thr = h < 0.05
            fin = start + run * np.where(thr & (not stream), THROTTLE, 1.0)
            if stream:
                ok = ((start - t0) <= slo) & ~thr
            else:
                ok = fin <= t0 + slo
            if self.bounded and self.eon:
                ok = ok & np.array([self.efeasible(j, t0, m, run) for j in ids])
            if ok.any():
                bfk = self.excess[s][ids] * 1e3 if self.pol == "oracle_c" else 0.0
                free_now = (self.F[ids] <= start[:, None]).sum(1) - m   # slots left free after placement
                if self.okey == "eft":
                    key = bfk + fin
                elif self.okey == "local":
                    key = bfk + fin + np.where(ids == o, -1e2, 0.0)
                elif self.okey == "pack":        # bin-packing best fit (consolidate)
                    key = bfk + free_now * 1.0 + fin * 1e-3 + np.where(ids == o, -0.5, 0.0)
                else:                            # worst fit (balance)
                    key = bfk - free_now * 1.0 + fin * 1e-3
                key = key.astype(float)
                key = np.where(ok, key, np.inf)
                k = int(np.argmin(key))
            else:
                k = int(np.argmin(fin))
            best = (int(ids[k]), bool(ok[k]))
            if not best[1] and self.late == "drop":
                best = None
                ids = ids[:0]
        cl_ok = False
        if self.cloud and (not self.pol == "oracle_c" or s <= self.cloud["clear"]):
            if best is None or not best[1]:
                okc, cs, cf, cidx = self.cloud_try(t0, m, run, (slo if stream else t0 + slo), stream)
                if okc or best is None:
                    self.cF[cidx] = cf - self.cloud["lat"]
                    viol = s > self.cloud["clear"]
                    return okc, viol, 1, True
        if best is None:
            return False, False, 0, None   # dropped
        j, okj = best
        if j == o:
            ok, start, fin, thr, idx = self.try_local(j, t0, m, run, (slo if stream else t0 + slo), stream)
        else:
            ok, start, fin, thr, idx = self.try_local(j, t0 + self.L[o, j], m, run,
                                                      (slo - self.L[o, j] if stream else t0 + slo), stream)
        if self.bounded and self.eon and not ok:
            return False, False, 0, None    # no energy for a late job
        self.commit(j, idx, start, fin, m)
        self._net = self.L[o, j] if j != o else 0.0
        self._lat = ((start - t0) if stream else (fin - t0), max(start - t0 - self._net, 0.0))
        self.proc = j
        viol = not self.EL[(s, odom)][j]
        if thr and self.counting:
            self.st["thr"] += 1
        return ok, viol, int(j != o), False

    # ---------------- request handling ----------------
    def serve_at(self, j, t, m, run, deadline, stream, s, odom):
        ok, start, fin, thr, idx = self.try_local(j, t, m, run, deadline, stream)
        if self.bounded and self.eon and not self.efeasible(j, t, m, run):
            return None                 # serve-late may not overdraw either
        self.commit(j, idx, start, fin, m)
        if thr and self.counting:
            self.st["thr"] += 1
        return ok, (not self.EL[(s, odom)][j])

    def _try_lite(self, cur, t, l, s, odom, t0, slo, stream, dl, run):
        """Last resort before shedding: run a smaller model variant here. Assumed profile, see LITE."""
        m2, f = LITE[SERVICES[l][0]]
        r2 = run * f
        ok, start, fin, thr, idx = self.try_local(cur, t, m2, r2, dl, stream)
        if not ok:
            return False
        self.commit(cur, idx, start, fin, m2)
        self._lat = ((start - t0) if stream else (fin - t0), start - t)
        self._net = t - t0
        self.proc = cur
        if self.counting:
            self.degraded += 1
        return True

    def to_cloud(self, t, m, run, deadline, stream, s, force=False):
        if not self.cloud:
            return None
        if self.trust and s > self.cloud["clear"]:
            return None
        ok, start, fin, idx = self.cloud_try(t, m, run, deadline, stream)
        if ok or (force and not self.cloud.get("strict")):      # strict: Algorithm 1, a lost deadline is shed
            self.cF[idx] = fin - self.cloud["lat"]
            self._lat = ((start - self.now) if stream else (fin - self.now), start - t)
            return ok, s > self.cloud["clear"]
        return None

    def handle(self, t0, o, l, s, dur, odom=None):
        for _ in self._handle(t0, o, l, s, dur, odom):
            pass

    def _handle(self, t0, o, l, s, dur, odom=None):
        """One request. Yields the arrival time of each forward; exact mode resumes it at that time."""
        name, cat, m, run, slo, stream, _ = SERVICES[l]
        if stream:
            run = dur
        odom = self.t["dom"][o] if odom is None else odom
        self.now, self.proc, self._dc_ctx = t0, None, (o, s, odom)
        self.now_e = t0
        self._lat = None
        covered = self.ov_scope == "all" or s > 0
        ovp = self.ov_proc if covered else 0.0
        ovf = self.ov_fwd if covered else 0.0
        if covered:
            run = run * self.run_mult
        ovs = 0.0
        if self.ov_slot:                    # delay runs inside the slot: holds capacity, still counts against the SLO
            ovs, ovp = ovp, 0.0
            run = run + ovs
        if self.pol in ("trace", "tracex"):
            if self.q_mode == "count":
                self.sshare[o] += self.bf_alpha * ((s > 0) - self.sshare[o])
            else:                           # slot-seconds: each request weighs its demand relative to the mean request
                w = min(50.0, m * (sum(STREAM_DUR[name]) / 2 if stream else SERVICES[l][3]) / self.mean_ss)
                self.sshare[o] += self.bf_alpha * w * ((s > 0) - self.sshare[o])
        incloud = False
        if self.pol in ("oracle_c", "oracle_u"):
            t_d0 = time.perf_counter()
            ok, viol, hops, incloud = self.oracle(t0 + ovp, o, l, m, run, slo - ovp, stream, s, odom)
            self.t_dec += time.perf_counter() - t_d0
            self.n_dec += 1
            res = ok
            if incloud is None:
                res, viol, hops, incloud = False, False, 0, False
                self._count(cat, False, False, 0, False, dropped=True)
                return
            self._count(cat, res, viol, hops, incloud)
            return
        route = self.RM[(s, odom)]
        cur, t, hops = o, t0, 0
        visited = {o}
        res, viol, dropped = False, False, False
        handover = None
        if self.pol == "tracex":
            cap = self.vf["adm_big"] if m == 8 else (self.vf["adm_small"] if m == 1 else None)
            if cap is not None and float(np.mean(self.sp[o] / self.S)) < cap:   # class-aware admission on the local view
                self._count(cat, False, False, 0, False, dropped=True)
                return
        while True:
            dl = (slo - (t - t0) - ovs) if stream else (t0 + slo)
            self._slack = dl if stream else (t0 + slo - t)
            self.now_e = t
            can_here = route[cur] and self.host[cur, l] and not self.down(cur, t)
            if can_here and self.pol == "ef" and not self.efeasible(cur, t, m, run):
                can_here_e = False
            else:
                can_here_e = can_here
            ok = False
            if can_here_e:
                ok, start, fin, thr, idx = self.try_local(cur, t + ovp, m, run, dl - ovp if stream else dl, stream)
                if ok and self.pol == "ew" and self.theta > 0 and hops < self.kmax \
                        and self.head(cur, t) < self.theta:
                    slack = (t0 + slo - fin) if not stream else (dl - (start - t))
                    if slack > 0.05:
                        p = self._pick(cur, m, s, odom, l, visited, stream, run, t, dry=True)
                        if p is not None and self.hd[cur][p] > 0.5 and self.sp[cur][p] >= m:
                            ok = False
                            handover = p
                if ok and self.pol == "tracex":
                    p = self._can_defer(cur, s, m, run, hops, t, stream, l, odom, visited)
                    if p is not None:
                        ok = False
                        handover = p
                    elif self.vf["trunk_hard"] and self.vf["trunk"] > 0 and s == 0 and self.t["clear"][cur] > 0 \
                            and int((self.F[cur] <= t).sum()) - m < self.vf["trunk"] * self.S[cur]:
                        ok = False              # hard trunk: refuse here even with no peer
            if ok:
                self._lat = ((start - t0) if stream else (fin - t0), start - t)
                self._net = t - t0
                self.commit(cur, idx, start, fin, m)
                if thr and self.counting:
                    self.st["thr"] += 1
                res, viol = True, (not self.EL[(s, odom)][cur])
                self.proc = cur
                break
            p = None
            if self.pol != "local" and hops < self.kmax:
                if handover is not None:
                    p, handover = handover, None
                    self._debit(cur, p, m, stream, run)
                else:
                    p = self.pick(cur, m, s, odom, l, visited, stream, run, t)
            if p is None:
                c = self.to_cloud(t + ovp, m, run, dl - ovp if stream else dl, stream, s)
                if c is not None:
                    res, viol = c
                    incloud = True
                elif can_here and self.late == "serve":
                    out = self.serve_at(cur, t + ovp, m, run, dl - ovp if stream else dl, stream, s, odom)
                    if out is None:
                        dropped = True
                    else:
                        res, viol = out
                        self.proc = cur
                elif can_here:
                    if self.vf["lite"] and name in LITE and self._try_lite(cur, t, l, s, odom, t0, slo, stream, dl, run):
                        res, viol = True, False
                    else:
                        dropped = True
                else:
                    c = self.to_cloud(t + ovp, m, run, dl - ovp if stream else dl, stream, s, force=True)
                    if c is not None:
                        res, viol = c
                        incloud = True
                    else:
                        dropped = True
                break
            t += self.L[cur][p] + ovf
            cur = p
            visited.add(p)
            hops += 1
            yield t
        if dropped and self.counting:
            self.shed_n += 1
            rec = int(self._shed_check(t0, m, run, slo, stream, s, odom, l))
            self.shed_feas += rec
            self.cat_shed[cat] = self.cat_shed.get(cat, 0) + 1
            self.cat_recov[cat] = self.cat_recov.get(cat, 0) + rec
            self.cat_kmax[cat] = self.cat_kmax.get(cat, 0) + int(hops >= self.kmax)
        self._count(cat, res, viol, hops, incloud, dropped)

    def _decomp(self, viol, incloud, dropped):
        """Classify one counted request by ingress eligibility and where it was processed."""
        o, s, odom = self._dc_ctx
        ing = "ie" if self.EL[(s, odom)][o] else "ii"      # ingress eligible / ineligible
        j = self.proc
        if dropped or (j is None and not incloud):
            out = "shed"
        elif incloud:
            out = "cloud_v" if viol else "cloud_ok"
        elif j == o:
            out = "local_v" if viol else "local_ok"
        elif not viol:
            out = "fwd_ok"
        else:
            out = "fwd_v_clear" if self.t["clear"][j] < s else "fwd_v_dom"
        k = f"dc_{ing}_{out}"
        self.dc[k] = self.dc.get(k, 0) + 1
        k = f"dcs{s}_{out}"
        self.dc[k] = self.dc.get(k, 0) + 1

    def _count(self, cat, res, viol, hops, incloud, dropped=False):
        if not self.counting:
            return
        self._decomp(viol, incloud, dropped)
        if self.record and res and self._lat is not None:
            self.rec.setdefault(cat, []).append((*self._lat, self._net))
        if self.bin_s:
            b = self.bins.setdefault(int(self.now // self.bin_s), [0, 0])
            b[0] += 1; b[1] += int(res and not viol)
        st = self.st
        st["n"] += 1
        st["good"] += int(res)
        st["cgood"] += int(res and not viol)
        st["viol"] += int(viol)
        st["hops"] += hops
        st["cloud"] += int(bool(incloud))
        st["drop"] += int(dropped)
        c = st["by_cat"].setdefault(cat, [0, 0, 0])
        c[0] += 1; c[1] += int(res); c[2] += int(res and not viol)

    # ---------------- workload ----------------
    def gen_arrivals(self):
        n = self.n
        rng = self.rng
        total = self.S.sum()
        base = rng.lognormal(0, 0.8, n)
        base /= base.sum()
        phase = rng.random(n) * 2 * np.pi
        if self.burst_sync:
            phase[:] = 0.0
        clear = self.t["clear"]
        out = []
        for l, sv in enumerate(SERVICES):
            name, cat, m, run, slo, stream, share = sv
            if self.svc_share is not None:
                share = self.svc_share[l]
            slotsec = m * (sum(STREAM_DUR[name]) / 2 if stream else run)
            rate = self.rho * total * share / slotsec
            k = rng.poisson(rate * self.T)
            ts = np.sort(rng.random(k) * self.T)
            sens = rng.choice(3, size=k, p=self.sens_p)
            al = rng.random(k) < self.corr
            u = rng.random(k)
            dur = rng.uniform(*STREAM_DUR[name], size=k) if stream else np.zeros(k)
            org = np.empty(k, int)
            for a in range(0, k, 20000):
                b = min(k, a + 20000)
                W = base[None] * (1 + self.burst_amp * np.sin(2 * np.pi * ts[a:b, None] / self.burst_period + phase[None]))
                # aligned requests originate only at servers whose clearance covers them
                W = np.where(al[a:b, None] & (clear[None] < sens[a:b, None]), 0.0, W)
                cw = np.cumsum(W, 1)
                org[a:b] = np.minimum((cw < (u[a:b] * cw[:, -1])[:, None]).sum(1), n - 1)
            out.append(np.rec.fromarrays([ts, org, np.full(k, l), sens, dur],
                                         names="t,o,l,s,d"))
        arr = np.concatenate(out)
        arr.sort(order="t")
        self.odom = None
        if self.owner_cross > 0:            # device-selected data-owner domain; own stream so arrivals do not change
            g = np.random.default_rng(self.owner_seed)
            nd = self.t["n_dom"]
            d0 = self.t["dom"][arr["o"]]
            self.odom = np.where(g.random(len(arr)) < self.owner_cross, (d0 + g.integers(1, nd, len(arr))) % nd, d0).tolist()
        return arr

    def _state(self):
        return {k: getattr(self, k, None) for k in REQ_STATE}

    def run_exact(self, arr):
        """Every arrival, hop, refresh and snapshot is processed in time order. Ties: refresh, then snapshot, then FIFO."""
        T_, O, L, Sx, D = (arr["t"].tolist(), arr["o"].tolist(), arr["l"].tolist(),
                           arr["s"].tolist(), arr["d"].tolist())
        heap, seq, i, nref, nsnap, k, ks = [], 0, 0, 0.0, 0.0, 0, 0
        n = len(T_)
        while i < n or heap:
            hop = bool(heap) and (i == n or heap[0][0] < T_[i])
            t = heap[0][0] if hop else T_[i]
            while self.ring and nsnap <= t:
                self.snap(nsnap); ks += 1; nsnap = ks * self.snap_dt
            while nref <= t:
                self.refresh(nref); k += 1; nref = k * self.hsync
            if hop:
                _, _, g, st = heapq.heappop(heap)
                for a, v in st.items():
                    setattr(self, a, v)
            else:
                self.counting = t >= self.warm
                g = self._handle(t, O[i], L[i], Sx[i], D[i], self.odom[i] if self.odom else None)
                i += 1
            try:
                tn = next(g)
            except StopIteration:
                continue
            seq += 1
            heapq.heappush(heap, (tn, seq, g, self._state()))
        return self.summary()

    def run(self):
        arr = self.gen_arrivals()
        self.now_e, self._slowed = 0.0, False
        share = self.svc_share if self.svc_share is not None else [v[6] for v in SERVICES]
        ss = [v[2] * (sum(STREAM_DUR[v[0]]) / 2 if v[5] else v[3]) for v in SERVICES]
        cnt = [a / b for a, b in zip(share, ss)]
        self.mean_ss = sum(c * x for c, x in zip(cnt, ss)) / sum(cnt)
        if self.event_mode == "exact":
            return self.run_exact(arr)
        nxt = 0.0
        nsnap = 0.0
        warm = self.warm
        T_, O, L, Sx, D = (arr["t"].tolist(), arr["o"].tolist(), arr["l"].tolist(),
                           arr["s"].tolist(), arr["d"].tolist())
        for i in range(len(T_)):
            t = T_[i]
            self.counting = t >= warm
            if self.ring and t >= nsnap:
                self.snap(t)
                nsnap = t + 0.05
            if t >= nxt:
                self.refresh(t)
                nxt = t + self.hsync
            self.handle(t, O[i], L[i], Sx[i], D[i], self.odom[i] if self.odom else None)
        return self.summary()

    def summary(self):
        st = self.st
        n = max(st["n"], 1)
        Tm = self.T - self.warm
        util = self.busy / (self.S * Tm)
        av = np.array(self.avs).mean(0) if self.avs else np.ones(self.n)
        r = dict(
            policy=self.pol, rho=self.rho,
            slo=st["good"] / n, viol=st["viol"] / n, cslo=st["cgood"] / n,
            goodput=st["good"] / Tm, cgoodput=st["cgood"] / Tm,
            throttled=st["thr"] / n, hops=st["hops"] / n, cloud=st["cloud"] / n,
            drop=st["drop"] / n,
            energy_per_good=st["energy"] / max(st["good"], 1),
            energy_kw=st["energy"] / 1e3 / Tm,
            spill=self.spill / max(self.income, 1e-9),
            avail=float(av.mean()), avail_min=float(av.min()),
            avail_cv=float(av.std() / max(av.mean(), 1e-9)),
            util_cv=float(util.std() / max(util.mean(), 1e-9)),
            util_max=float(util.max()),
            drains=self.n_down / Tm * 60.0,
            dec_us=self.t_dec / max(self.n_dec, 1) * 1e6,
            dec_per_req_us=self.t_dec / n * 1e6,
        )
        for k, v in st["by_cat"].items():
            r[f"slo_{k}"] = v[1] / max(v[0], 1)
            r[f"cslo_{k}"] = v[2] / max(v[0], 1)
        r["bcslo"] = float(np.mean([v[2] / max(v[0], 1) for v in st["by_cat"].values()]))
        r.update({k: v / n for k, v in self.dc.items()})
        r["n_counted"] = st["n"]
        if self.vage_n:
            r["view_age_eff_s"] = self.vage_sum / self.vage_n
        if self.age_hist:
            r["view_age_hist"] = {str(k): v for k, v in sorted(self.vage_bins.items())}
        for c, v in self.cat_shed.items():
            r[f"shed_{c}"] = v
            r[f"recov_{c}"] = self.cat_recov.get(c, 0)
            r[f"kmax_{c}"] = self.cat_kmax.get(c, 0)
        r["bf_switch"] = self.bf_switch
        if self.eon:
            for j in range(self.n):
                self._refill(j, self.T)
            r.update({f"led_{k}": v for k, v in self.ledger.items()})
            r["led_final"] = float(self.level.sum())
            r["level_min_frac"] = float((self.level / self.bcap).min())
        r["shed_recoverable"] = self.shed_feas / max(self.shed_n, 1)
        r["degraded"] = self.degraded / n
        if self.record:
            for cat, v in list(self.rec.items()) + [("all", [x for q in self.rec.values() for x in q])]:
                a = np.array(v)
                if len(a):
                    r[f"lat_mean_{cat}"] = float(a[:, 0].mean())
                    r[f"lat_p50_{cat}"] = float(np.median(a[:, 0]))
                    r[f"net_mean_{cat}"] = float(a[:, 2].mean())
                    r[f"lat_p95_{cat}"] = float(np.quantile(a[:, 0], .95))
                    r[f"lat_p99_{cat}"] = float(np.quantile(a[:, 0], .99))
                    r[f"wait_mean_{cat}"] = float(a[:, 1].mean())
            r["edge_util"] = float((self.busy.sum()) / (self.S.sum() * Tm))
        if self.ring:
            r["ring_time_s"] = self.ring_time
            r["view_age_mean_s"] = self.age_sum / max(self.age_n, 1)
        if self.bin_s:
            r["bins"] = {str(k): v for k, v in sorted(self.bins.items())}
        fin = self.F[np.isfinite(self.F)]
        r["tail_slot_s"] = float(np.maximum(fin - self.T, 0).sum())    # committed work past the run end
        if self.trace_energy:
            e = self.en
            f = e["first"]
            r["h_mean"] = e["hsum"] / max(e["n"], 1)
            r["frac_low"] = e["low"] / max(e["n"], 1)
            r["frac_empty"] = e["empty"] / max(e["n"], 1)
            r["srv_ever_low"] = float(np.mean(~np.isnan(f)))
            r["t_first_low"] = float(np.nanmin(f)) if (~np.isnan(f)).any() else None
            r["t_median_low"] = float(np.nanmedian(f)) if (~np.isnan(f)).any() else None
            r["series"] = e["series"]
        return r
