"""
ecsim.py - event-driven edge-cloud inference routing simulator (Phase-1 prototype).

Scope: compares *routing / offloading policies* on a fixed set of edge servers.
The EPARA-style parallelism allocator (BS/MT/MP/MF/DP) is treated as a common,
already-applied layer: each service is described by the GPU "slots" it occupies and
its effective service time AFTER operator selection. All profile numbers below are
ASSUMED parameters (to be replaced by measured profiles in Phase 2).

Policies
  local      : never offload (lower bound)
  rr         : round-robin offload, InterEdge-style (privacy/energy oblivious)
  epara      : EPARA-style, offload prob. ~ idle capacity (privacy/energy oblivious)
  epara_priv : epara + hard trust-domain filter
  energy     : epara + energy-headroom weighting, no privacy filter
  ours       : hard trust-domain filter + energy-headroom weighting + energy-aware local
               retention (offload away from a nearly drained server when slack allows)
"""
import time
import numpy as np

SLOTS_PER_GPU = 4
P_SLOT = 60.0          # W per active slot (250 W GPU / 4)
H_SYNC = 1.0           # s, state-sync staleness
HORIZON = 0.5          # s, capacity horizon for 'spare' estimate
MAX_HOPS = 2

# service table: name, category, slots m, run time s (s), SLO (s), is_stream, slot-sec share
SERVICES = [
    # name,   cat,    m, run,  slo,  stream, share
    ("cls",  "LS<1",  1, 0.030, 0.15, False, 0.20),
    ("llm",  "LS>1",  8, 0.800, 3.00, False, 0.30),
    ("det",  "FS<1",  2, None,  0.20, True,  0.30),   # stream, duration U(5,15)
    ("big",  "FS>1",  8, None,  0.30, True,  0.20),   # stream, duration U(5,10)
]
STREAM_DUR = {"det": (5, 15), "big": (5, 10)}
SENS_P = [0.60, 0.25, 0.15]       # request sensitivity level 0/1/2


def build_topology(n, rng):
    gpus = rng.choice([2, 4], size=n)
    slots = gpus * SLOTS_PER_GPU
    clear = rng.choice([0, 1, 2], size=n, p=[0.30, 0.40, 0.30])
    dom = rng.integers(0, 3, size=n)
    # energy cap as fraction of full power (battery / solar / power-capped sites)
    capfrac = rng.choice([0.45, 0.7, 1.0], size=n, p=[0.35, 0.35, 0.30])
    pos = rng.random((n, 2))
    lat = 0.002 + 0.020 * np.sqrt(((pos[:, None] - pos[None]) ** 2).sum(-1))  # s
    return dict(n=n, slots=slots, clear=clear, dom=dom, capfrac=capfrac, lat=lat)


class Sim:
    def __init__(self, topo, policy, rho, T, seed, beta=1.0, theta=0.25,
                 outage=False, hsync=H_SYNC, gamma=0.3):
        self.t = topo
        self.outage = outage      # hard battery model: drained server goes offline
        self.hsync = hsync        # state-sync period (staleness of peer view)
        self.offl = np.zeros(topo["n"], bool)
        self.avail = []           # sampled fraction of servers online
        self.n_down = 0           # number of drain (offline) events
        self.t_dec = 0.0          # wall-clock time spent in routing decisions
        self.barrier = (policy == 'ours_b')
        self.capmin = (policy == 'ours_c')   # energy as a capacity dimension
        self.bestfit = (policy == 'tera')    # trust filter + best-fit clearance, no energy term
        self.gamma = gamma
        self.pol = 'ours' if policy in ('ours_b', 'ours_c') else (
            'epara_priv' if policy == 'tera' else policy)
        self.rho = rho
        self.T = T
        self.rng = np.random.default_rng(seed)
        self.beta = beta
        self.theta = theta
        n = topo["n"]
        self.free = [np.zeros(int(s)) for s in topo["slots"]]
        self.pcap = topo["capfrac"] * topo["slots"] * P_SLOT          # W budget
        self.bcap = self.pcap * 20.0                                  # J (20 s bucket)
        self.level = self.bcap * 0.6
        self.lastu = np.zeros(n)
        self.spill = 0.0          # energy income lost because the bucket was full
        self.income = 0.0
        self.sp = np.tile(np.array(topo["slots"], float), (n, 1))   # observer x target
        self.hd = np.ones((n, n))
        self.esp = np.tile(np.array(topo["slots"], float), (n, 1))  # energy-spare slots
        self.rr_ptr = 0
        self.rr_ptrs = np.arange(n)
        self.counting = False
        self.stats = dict(n=0, good=0, cgood=0, viol=0, thr=0, energy=0.0, hops=0,
                          by_cat={})

    # ---- energy bucket -------------------------------------------------
    def _refill(self, j, t):
        dt = t - self.lastu[j]
        if dt > 0:
            inc = self.pcap[j] * dt
            new = self.level[j] + inc
            if self.counting:
                self.income += inc
                self.spill += max(0.0, new - self.bcap[j])
            self.level[j] = min(self.bcap[j], new)
            self.lastu[j] = t

    def head(self, j, t):
        self._refill(j, t)
        return self.level[j] / self.bcap[j]

    def down(self, j, t):
        """Hard-outage model: offline when drained, back online at 30% charge."""
        if not self.outage:
            return False
        h = self.head(j, t)
        if self.offl[j] and h >= 0.30:
            self.offl[j] = False
        elif not self.offl[j] and h <= 0.01:
            self.offl[j] = True
            if self.counting:
                self.n_down += 1
        return bool(self.offl[j])

    # ---- state snapshot (ring sync) -------------------------------------
    def refresh(self, t):
        n = self.t["n"]
        sp = np.zeros(n); hd = np.zeros(n); es = np.zeros(n)
        for j in range(n):
            back = np.clip(self.free[j] - t, 0, HORIZON).sum()
            sp[j] = max(0.0, self.t["slots"][j] - back / HORIZON)
            hd[j] = 0.0 if self.down(j, t) else self.head(j, t)
            # slots the energy budget can power over the horizon, minus those already busy
            e_slots = (self.level[j] + self.pcap[j] * HORIZON) / (P_SLOT * HORIZON)
            es[j] = 0.0 if hd[j] == 0.0 else max(0.0, e_slots - back / HORIZON)
        self.sp[:] = sp; self.hd[:] = hd; self.esp[:] = es
        if self.counting:
            self.avail.append(1.0 - self.offl.mean())

    # ---- helpers ---------------------------------------------------------
    def eligible(self, j, sens, odom):
        if self.t["clear"][j] < sens:
            return False
        if sens >= 2 and self.t["dom"][j] != odom:
            return False
        return True

    def try_local(self, j, t, m, run, slo_t, stream):
        """Return (ok, start, finish, throttled)."""
        f = self.free[j]
        idx = np.argpartition(f, m - 1)[:m] if m < len(f) else np.arange(len(f))
        start = max(t, f[idx].max())
        thr = self.head(j, start) < 0.05
        r = run * (1.6 if (thr and not stream) else 1.0)
        fin = start + r
        if stream:
            ok = (start - t) <= slo_t and not thr
        else:
            ok = fin <= slo_t
        return ok, start, fin, thr, idx

    def commit(self, j, idx, start, fin, m):
        self.free[j][idx] = fin
        e = m * P_SLOT * (fin - start)
        self._refill(j, start)
        self.level[j] = max(0.0, self.level[j] - e)
        if self.counting:
            self.stats["energy"] += e
        return e

    def pick_peer(self, *a, **k):
        t0 = time.perf_counter()
        r = self._pick_peer(*a, **k)
        self.t_dec += time.perf_counter() - t0
        return r

    def _pick_peer(self, cur, m, sens, odom, t_now, exclude, stream=False, run=0.0, dry=False):
        n = self.t["n"]
        pol = self.pol
        if pol == "rr":
            # decentralized round-robin: each server cycles through peers with its own pointer
            for _ in range(n):
                self.rr_ptrs[cur] = (self.rr_ptrs[cur] + 1) % n
                if self.rr_ptrs[cur] not in exclude:
                    return int(self.rr_ptrs[cur])
            return None
        if pol == "rr_g":
            # reference only: one pointer shared by all servers (implicit global coordination)
            for _ in range(n):
                self.rr_ptr = (self.rr_ptr + 1) % n
                if self.rr_ptr not in exclude:
                    return self.rr_ptr
            return None
        w = np.minimum(self.sp[cur], self.esp[cur]) if self.capmin else self.sp[cur].copy()
        w = np.where(w >= m, w, w * 0.05)               # prefer peers that fit
        w = w / (1.0 + self.t["lat"][cur] / 0.02)       # network proximity (all policies)
        if pol in ("energy", "ours") and not self.capmin:
            if self.barrier:
                w = w * np.clip(self.hd[cur] / 0.3, 0.05, 1.0)
            else:
                w = w * np.power(np.maximum(self.hd[cur], 1e-3), self.beta)
        if pol in ("epara_priv", "ours"):
            elig = np.array([self.eligible(j, sens, odom) for j in range(n)])
            w = np.where(elig, w, 0.0)
            if self.bestfit:
                # best-fit clearance: keep high-clearance capacity for sensitive requests
                w = w * np.power(self.gamma, np.maximum(self.t["clear"] - sens, 0))
        for e in exclude:
            w[e] = 0.0
        s = w.sum()
        if s <= 0:
            return None
        p = int(self.rng.choice(n, p=w / s))
        if dry:              # probe only: do not reserve capacity in the local view
            return p
        self.reserve(cur, p, m, stream, run)
        return p

    def reserve(self, cur, p, m, stream, run):
        d = m if stream else m * run / HORIZON
        self.sp[cur][p] = max(0.0, self.sp[cur][p] - d)
        self.esp[cur][p] = max(0.0, self.esp[cur][p] - d)

    # ---- request handling -------------------------------------------------
    def handle(self, t0, origin, sv, sens, dur):
        name, cat, m, run, slo, stream, _ = sv
        if stream:
            run = dur
        odom = self.t["dom"][origin]
        priv = self.pol in ("epara_priv", "ours")
        cur, t, hops, viol = origin, t0, 0, False
        visited = {origin}
        done = False
        res_ok = False
        handover = None
        while True:
            can_here = ((not priv) or self.eligible(cur, sens, odom)) and not self.down(cur, t)
            ok = False
            if can_here and self.pol != "none":
                ok, start, fin, thr, idx = self.try_local(
                    cur, t, m, run, (slo if stream else t0 + slo), stream)
                # energy-aware retention: avoid draining a nearly empty server if slack allows
                if ok and self.pol == "ours" and hops < MAX_HOPS and self.head(cur, t) < self.theta:
                    slack = (t0 + slo) - fin if not stream else slo - (start - t)
                    if slack > 0.05:
                        p = self.pick_peer(cur, m, sens, odom, t, visited, stream, run, dry=True)
                        if p is not None and self.hd[cur][p] > 0.5 and self.sp[cur][p] >= m:
                            ok = False   # hand over to the probed peer
                            handover = p
            if ok:
                self.commit(cur, idx, start, fin, m)
                if self.t["clear"][cur] < sens or (sens >= 2 and self.t["dom"][cur] != odom):
                    viol = True
                if thr and self.counting:
                    self.stats["thr"] += 1
                res_ok = True
                break
            if self.pol == "local" or hops >= MAX_HOPS:
                # forced serve at last server if eligible (late) else drop
                if can_here and self.pol != "local":
                    ok2, start, fin, thr, idx = self.try_local(
                        cur, t, m, run, (slo if stream else t0 + slo), stream)
                    self.commit(cur, idx, start, fin, m)
                    if self.t["clear"][cur] < sens or (sens >= 2 and self.t["dom"][cur] != odom):
                        viol = True
                elif can_here and self.pol == "local":
                    ok2, start, fin, thr, idx = self.try_local(
                        cur, t, m, run, (slo if stream else t0 + slo), stream)
                    self.commit(cur, idx, start, fin, m)
                    if self.t["clear"][cur] < sens or (sens >= 2 and self.t["dom"][cur] != odom):
                        viol = True
                break
            if handover is not None:
                p, handover = handover, None
                self.reserve(cur, p, m, stream, run)
            else:
                p = self.pick_peer(cur, m, sens, odom, t, visited, stream, run)
            if p is None:
                if can_here:
                    ok2, start, fin, thr, idx = self.try_local(
                        cur, t, m, run, (slo if stream else t0 + slo), stream)
                    self.commit(cur, idx, start, fin, m)
                    if self.t["clear"][cur] < sens or (sens >= 2 and self.t["dom"][cur] != odom):
                        viol = True
                break
            t += self.t["lat"][cur][p]
            cur = p
            visited.add(p)
            hops += 1
        if not self.counting:
            return res_ok, viol
        s = self.stats
        s["cgood"] += int(res_ok and not viol)
        s["n"] += 1
        s["hops"] += hops
        s["viol"] += int(viol)
        s["good"] += int(res_ok)
        c = s["by_cat"].setdefault(cat, [0, 0, 0])
        c[0] += 1
        c[1] += int(res_ok)
        c[2] += int(res_ok and not viol)
        return res_ok, viol

    # ---- workload ---------------------------------------------------------
    def gen_arrivals(self):
        n = self.t["n"]
        total_slots = self.t["slots"].sum()
        rng = self.rng
        # hotspot weights per origin, with slow burst modulation
        base = rng.lognormal(0, 0.8, n)
        base /= base.sum()
        phase = rng.random(n) * 2 * np.pi
        arr = []
        for sv in SERVICES:
            name, cat, m, run, slo, stream, share = sv
            if stream:
                lo, hi = STREAM_DUR[name]
                slotsec = m * (lo + hi) / 2
            else:
                slotsec = m * run
            rate = self.rho * total_slots * share / slotsec
            k = rng.poisson(rate * self.T)
            ts = np.sort(rng.random(k) * self.T)
            # burst modulation by thinning-like origin choice
            for t in ts:
                wts = base * (1 + 0.8 * np.sin(2 * np.pi * t / 20.0 + phase))
                wts = wts / wts.sum()
                o = rng.choice(n, p=wts)
                sens = rng.choice(3, p=SENS_P)
                dur = rng.uniform(*STREAM_DUR[name]) if stream else 0.0
                arr.append((t, o, sv, sens, dur))
        arr.sort(key=lambda x: x[0])
        return arr

    def run(self, warm=5.0):
        arr = self.gen_arrivals()
        next_sync = 0.0
        for (t, o, sv, sens, dur) in arr:
            self.counting = t >= warm
            if t >= next_sync:
                self.refresh(t)
                next_sync = t + self.hsync
            self.handle(t, o, sv, sens, dur)
        return self.summary(warm)

    def summary(self, warm):
        s = self.stats
        n = max(s["n"], 1)
        # compliant goodput: good AND no privacy violation (approximated as good - viol-overlap)
        return dict(
            policy=self.pol, rho=self.rho,
            slo=s["good"] / n,
            viol=s["viol"] / n,
            goodput=s["good"] / (self.T - warm),
            cgoodput=s["cgood"] / (self.T - warm),
            cslo=s["cgood"] / n,
            energy_per_good=s["energy"] / max(s["good"], 1),
            throttled=s["thr"] / n,
            hops=s["hops"] / n,
            avail=float(np.mean(self.avail)) if self.avail else 1.0,
            drains=self.n_down / (self.T - warm) * 60.0,      # drain events per minute
            dec_us=self.t_dec / max(s["n"], 1) * 1e6,         # routing time per request
            energy_kj=s["energy"] / 1e3 / (self.T - warm),    # kJ per second (= avg kW)
            spill=self.spill / max(self.income, 1e-9),         # fraction of energy income wasted
            **{f"slo_{k}": v[1] / max(v[0], 1) for k, v in s["by_cat"].items()},
            **{f"cslo_{k}": v[2] / max(v[0], 1) for k, v in s["by_cat"].items()},
            # category-balanced compliant SLO: each of the four categories weighted equally
            bcslo=float(np.mean([v[2] / max(v[0], 1) for v in s["by_cat"].values()])),
        )
