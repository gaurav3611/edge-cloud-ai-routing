"""
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
TRUST = {"tf", "trace", "tera", "tf_rr", "tf_p2c", "tf_jsq", "static", "oracle_c",
         "ew", "eb", "ec", "ewd", "ef"}
ENERGY = {"ew", "eb", "ec", "ewd", "ef", "ew_only"}
CAPPROP = {"epara", "tf", "trace", "tera", "static", "ew", "eb", "ec", "ewd", "ef", "ew_only"}


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
                 bf_thresh=0.30, bf_alpha=0.002, sens_p=None, energy=True, okey='eft', late='serve'):
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
        self.counting = False
        self.t_dec = 0.0
        self.n_dec = 0
        self.busy = np.zeros(n)             # committed slot-seconds per server (measured)
        self.avs = []
        self.n_down = 0
        self.st = dict(n=0, good=0, cgood=0, viol=0, thr=0, energy=0.0, hops=0, cloud=0,
                       drop=0, by_cat={})

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
        floor = (0.05 if not self.outage else 0.01) * self.bcap[j]
        return self.level[j] - need >= floor

    # ---------------- state sync ----------------
    def refresh(self, t):
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
        self.sp[:] = sp; self.esp[:] = es; self.hd[:] = hd; self.bk[:] = bk
        self.tsync = t
        if self.counting:
            self.avs.append(~self.offl)

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
        thr = self.head(j, start) < 0.05
        r = run * (1.6 if (thr and not stream) else 1.0)
        fin = start + r
        ok = ((start - t) <= deadline and not thr) if stream else (fin <= deadline)
        return ok, start, fin, thr, idx

    def commit(self, j, idx, start, fin, m):
        self.F[j, idx] = fin
        e = m * P_SLOT * (fin - start)
        self._refill(j, start)
        self.level[j] -= e          # energy charged at commit; in-flight jobs always complete
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

    def _p2c(self, cur, c, m, stream, run):
        ids = np.flatnonzero(c)
        if len(ids) == 0:
            return None
        k = self.rng.choice(ids, size=min(2, len(ids)), replace=False)
        mi = self.mi(m)
        p = int(k[np.argmin(self.bk[cur, k, mi])])
        self._debit(cur, p, m, stream, run)
        return p

    def _pick(self, cur, m, s, odom, l, visited, stream, run, t, dry=False):
        pol = self.pol
        n = self.n
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
        if pol == "tf_jsq":
            c = self._cand(cur, s, odom, l, visited)
            ids = np.flatnonzero(c)
            if len(ids) == 0:
                return None
            b = self.bk[cur, ids, self.mi(m)] + self.t["lat"][cur, ids]
            p = int(ids[np.argmin(b)])
            self._debit(cur, p, m, stream, run)
            return p
        # capacity-proportional family
        c = self._cand(cur, s, odom, l, visited)
        if pol == "ec":
            w = np.minimum(self.sp[cur], self.esp[cur])
        else:
            w = self.sp[cur].copy()
        fits = (w >= m) & c
        w = np.where(w >= m, w, w * self.fitfac)
        w = w / (1.0 + self.t["lat"][cur] / self.l0)
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
        bf = (pol == "tera") or (pol == "trace" and self.sshare[cur] >= self.bf_thresh)
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

    # ---------------- centralized oracle ----------------
    def oracle(self, t0, o, l, m, run, slo, stream, s, odom):
        n = self.n
        c = self.host[:, l].copy()
        if self.pol == "oracle_c":
            c &= self.EL[(s, odom)]
        if self.outage:
            for j in np.flatnonzero(c):
                if self.down(j, t0):
                    c[j] = False
        ids = np.flatnonzero(c)
        lat = self.t["lat"][o, ids].copy()
        lat[ids == o] = 0.0
        best = None
        if len(ids):
            kth = np.partition(self.F[ids], m - 1, axis=1)[:, m - 1]
            start = np.maximum(t0 + lat, kth)
            h = np.array([self.head(j, st) for j, st in zip(ids, start)])
            thr = h < 0.05
            fin = start + run * np.where(thr & (not stream), 1.6, 1.0)
            if stream:
                ok = ((start - t0) <= slo) & ~thr
            else:
                ok = fin <= t0 + slo
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
            ok, start, fin, thr, idx = self.try_local(j, t0 + self.t["lat"][o, j], m, run,
                                                      (slo - self.t["lat"][o, j] if stream else t0 + slo), stream)
        self.commit(j, idx, start, fin, m)
        viol = not self.EL[(s, odom)][j]
        if thr and self.counting:
            self.st["thr"] += 1
        return ok, viol, int(j != o), False

    # ---------------- request handling ----------------
    def serve_at(self, j, t, m, run, deadline, stream, s, odom):
        ok, start, fin, thr, idx = self.try_local(j, t, m, run, deadline, stream)
        self.commit(j, idx, start, fin, m)
        if thr and self.counting:
            self.st["thr"] += 1
        return ok, (not self.EL[(s, odom)][j])

    def to_cloud(self, t, m, run, deadline, stream, s, force=False):
        if not self.cloud:
            return None
        if self.trust and s > self.cloud["clear"]:
            return None
        ok, start, fin, idx = self.cloud_try(t, m, run, deadline, stream)
        if ok or force:
            self.cF[idx] = fin - self.cloud["lat"]
            return ok, s > self.cloud["clear"]
        return None

    def handle(self, t0, o, l, s, dur):
        name, cat, m, run, slo, stream, _ = SERVICES[l]
        if stream:
            run = dur
        odom = self.t["dom"][o]
        if self.pol == "trace":
            self.sshare[o] += self.bf_alpha * ((s > 0) - self.sshare[o])
        incloud = False
        if self.pol in ("oracle_c", "oracle_u"):
            ok, viol, hops, incloud = self.oracle(t0, o, l, m, run, slo, stream, s, odom)
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
        while True:
            dl = (slo - (t - t0)) if stream else (t0 + slo)
            can_here = route[cur] and self.host[cur, l] and not self.down(cur, t)
            if can_here and self.pol == "ef" and not self.efeasible(cur, t, m, run):
                can_here_e = False
            else:
                can_here_e = can_here
            ok = False
            if can_here_e:
                ok, start, fin, thr, idx = self.try_local(cur, t, m, run, dl, stream)
                if ok and self.pol == "ew" and self.theta > 0 and hops < self.kmax \
                        and self.head(cur, t) < self.theta:
                    slack = (t0 + slo - fin) if not stream else (dl - (start - t))
                    if slack > 0.05:
                        p = self._pick(cur, m, s, odom, l, visited, stream, run, t, dry=True)
                        if p is not None and self.hd[cur][p] > 0.5 and self.sp[cur][p] >= m:
                            ok = False
                            handover = p
            if ok:
                self.commit(cur, idx, start, fin, m)
                if thr and self.counting:
                    self.st["thr"] += 1
                res, viol = True, (not self.EL[(s, odom)][cur])
                break
            p = None
            if self.pol != "local" and hops < self.kmax:
                if handover is not None:
                    p, handover = handover, None
                    self._debit(cur, p, m, stream, run)
                else:
                    p = self.pick(cur, m, s, odom, l, visited, stream, run, t)
            if p is None:
                c = self.to_cloud(t, m, run, dl, stream, s)
                if c is not None:
                    res, viol = c
                    incloud = True
                elif can_here and self.late == "serve":
                    res, viol = self.serve_at(cur, t, m, run, dl, stream, s, odom)
                elif can_here:
                    dropped = True
                else:
                    c = self.to_cloud(t, m, run, dl, stream, s, force=True)
                    if c is not None:
                        res, viol = c
                        incloud = True
                    else:
                        dropped = True
                break
            t += self.t["lat"][cur][p]
            cur = p
            visited.add(p)
            hops += 1
        self._count(cat, res, viol, hops, incloud, dropped)

    def _count(self, cat, res, viol, hops, incloud, dropped=False):
        if not self.counting:
            return
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
        clear = self.t["clear"]
        out = []
        for l, sv in enumerate(SERVICES):
            name, cat, m, run, slo, stream, share = sv
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
                W = base[None] * (1 + 0.8 * np.sin(2 * np.pi * ts[a:b, None] / 20.0 + phase[None]))
                # aligned requests originate only at servers whose clearance covers them
                W = np.where(al[a:b, None] & (clear[None] < sens[a:b, None]), 0.0, W)
                cw = np.cumsum(W, 1)
                org[a:b] = np.minimum((cw < (u[a:b] * cw[:, -1])[:, None]).sum(1), n - 1)
            out.append(np.rec.fromarrays([ts, org, np.full(k, l), sens, dur],
                                         names="t,o,l,s,d"))
        arr = np.concatenate(out)
        arr.sort(order="t")
        return arr

    def run(self):
        arr = self.gen_arrivals()
        nxt = 0.0
        warm = self.warm
        T_, O, L, Sx, D = (arr["t"].tolist(), arr["o"].tolist(), arr["l"].tolist(),
                           arr["s"].tolist(), arr["d"].tolist())
        for i in range(len(T_)):
            t = T_[i]
            self.counting = t >= warm
            if t >= nxt:
                self.refresh(t)
                nxt = t + self.hsync
            self.handle(t, O[i], L[i], Sx[i], D[i])
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
        return r
