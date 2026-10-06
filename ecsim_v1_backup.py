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
    def __init__(self, topo, policy, rho, T, seed, beta=1.0, theta=0.25):
        self.t = topo
        self.barrier = (policy == 'ours_b')
        self.pol = 'ours' if policy == 'ours_b' else policy
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
        self.sp = np.tile(np.array(topo["slots"], float), (n, 1))   # observer x target
        self.hd = np.ones((n, n))
        self.rr_ptr = 0
        self.counting = False
        self.stats = dict(n=0, good=0, cgood=0, viol=0, thr=0, energy=0.0, hops=0,
                          by_cat={})

    # ---- energy bucket -------------------------------------------------
    def _refill(self, j, t):
        dt = t - self.lastu[j]
        if dt > 0:
            self.level[j] = min(self.bcap[j], self.level[j] + self.pcap[j] * dt)
            self.lastu[j] = t

    def head(self, j, t):
        self._refill(j, t)
        return self.level[j] / self.bcap[j]

    # ---- state snapshot (ring sync) -------------------------------------
    def refresh(self, t):
        n = self.t["n"]
        sp = np.zeros(n); hd = np.zeros(n)
        for j in range(n):
            back = np.clip(self.free[j] - t, 0, HORIZON).sum()
            sp[j] = max(0.0, self.t["slots"][j] - back / HORIZON)
            hd[j] = self.head(j, t)
        self.sp[:] = sp; self.hd[:] = hd

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

    def pick_peer(self, cur, m, sens, odom, t_now, exclude, stream=False, run=0.0):
        n = self.t["n"]
        pol = self.pol
        if pol == "rr":
            for _ in range(n):
                self.rr_ptr = (self.rr_ptr + 1) % n
                if self.rr_ptr not in exclude:
                    return self.rr_ptr
            return None
        w = self.sp[cur].copy()
        w = np.where(w >= m, w, w * 0.05)               # prefer peers that fit
        w = w / (1.0 + self.t["lat"][cur] / 0.02)       # network proximity (all policies)
        if pol in ("energy", "ours"):
            if self.barrier:
                w = w * np.clip(self.hd[cur] / 0.3, 0.05, 1.0)
            else:
                w = w * np.power(np.maximum(self.hd[cur], 1e-3), self.beta)
        if pol in ("epara_priv", "ours"):
            elig = np.array([self.eligible(j, sens, odom) for j in range(n)])
            w = np.where(elig, w, 0.0)
        for e in exclude:
            w[e] = 0.0
        s = w.sum()
        if s <= 0:
            return None
        p = int(self.rng.choice(n, p=w / s))
        self.sp[cur][p] = max(0.0, self.sp[cur][p] - (m if stream else m * run / HORIZON))
        return p

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
        while True:
            can_here = (not priv) or self.eligible(cur, sens, odom)
            ok = False
            if can_here and self.pol != "none":
                ok, start, fin, thr, idx = self.try_local(
                    cur, t, m, run, (slo if stream else t0 + slo), stream)
                # energy-aware retention: avoid draining a nearly empty server if slack allows
                if ok and self.pol == "ours" and hops < MAX_HOPS and self.head(cur, t) < self.theta:
                    slack = (t0 + slo) - fin if not stream else slo - (start - t)
                    if slack > 0.05:
                        p = self.pick_peer(cur, m, sens, odom, t, visited, stream, run)
                        if p is not None and self.hd[cur][p] > 0.5 and self.sp[cur][p] >= m:
                            ok = False   # try to hand over
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
        c = s["by_cat"].setdefault(cat, [0, 0])
        c[0] += 1
        c[1] += int(res_ok)
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
            if t >= next_sync:
                self.refresh(t)
                next_sync = t + H_SYNC
            self.counting = t >= warm
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
            **{f"slo_{k}": v[1] / max(v[0], 1) for k, v in s["by_cat"].items()},
        )
