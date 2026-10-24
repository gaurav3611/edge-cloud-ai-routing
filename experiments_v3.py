"""
experiments_v3.py - revised experiment suite (response to review). Resumable.

  python3 experiments_v3.py tune      # gamma / threshold tuning on TUNING seeds 1001-1010
  python3 experiments_v3.py main      # trust experiments on TEST seeds 1-30 (energy unconstrained)
  python3 experiments_v3.py energy    # energy experiments (10 seeds, 180 s runs)

Every run appends one JSON line to runs_v3.jsonl. All policies use SLO-aware shedding
(late='drop') unless the experiment says otherwise.
"""
import json, os, sys
import numpy as np
from multiprocessing import Pool
from ecsim import build_topology, Sim

OUT = "runs_v3.jsonl"
TEST = list(range(1, 31))
TUNE = list(range(1001, 1011))
DEF_SENS = [0.60, 0.24, 0.16]
GAMMA = 0.3          # chosen on tuning seeds (see tune phase / STATS_v3.md)
BF_TH = 0.30


def mix(hi):
    return [1 - hi, 0.6 * hi, 0.4 * hi]


def J(exp, pol, seed, **kw):
    d = dict(exp=exp, pol=pol, seed=seed, rho=0.8, T=60, N=30, energy=False, late="drop",
             sens=DEF_SENS)
    d.update(kw)
    return d


def key(d):
    return json.dumps(d, sort_keys=True)


def job(d):
    d = dict(d)
    rng = np.random.default_rng(d["seed"])
    topo = build_topology(d["N"], rng, clear_p=d.get("clear_p", (0.30, 0.40, 0.30)),
                          n_dom=d.get("n_dom", 3))
    if "phi" in d:   # energy supply ratio: sum of mean supply / (rho * full power)
        f = d["phi"] * d["rho"] * topo["slots"].sum() / (topo["capfrac"] * topo["slots"]).sum()
        topo["capfrac"] = np.clip(topo["capfrac"] * f, 0.05, 2.0)
    kw = {k: d[k] for k in ("beta", "theta", "outage", "hsync", "gamma", "warm", "fallback",
                            "corr", "kmax", "l0", "horizon", "fitfac", "cloud", "place",
                            "buf_s", "init", "solar_amp", "solar_period", "bf_thresh",
                            "energy", "okey", "late") if k in d}
    kw.setdefault("gamma", GAMMA)
    kw.setdefault("bf_thresh", BF_TH)
    wseed = d.get("wseed", 100 + d["seed"])
    r = Sim(topo, d["pol"], d["rho"], d["T"], wseed, sens_p=d["sens"], **kw).run()
    r.update({k: v for k, v in d.items() if k not in ("cloud",)})
    r["cloud_on"] = bool(d.get("cloud"))
    r["sens_hi"] = round(d["sens"][1] + d["sens"][2], 3)
    r["_k"] = key(d)
    return r


CLOUD = dict(slots=96, lat=0.04, clear=1)


def tune_jobs():
    j = []
    for s in TUNE:
        for hi in [0.0, 0.2, 0.4, 0.6, 0.8]:
            for g in [1.0, 0.5, 0.3, 0.1]:
                j.append(J("T_tune", "tera", s, sens=mix(hi), gamma=g))
    return j


def main_jobs():
    j = []
    A = ["local", "rr", "epara", "oracle_u", "tf", "trace", "tf_rr", "tf_p2c", "tf_jsq",
         "static", "oracle_c"]
    for s in TEST:
        for rho in [0.5, 0.8, 1.0, 1.2]:                                   # A: load
            for p in A:
                j.append(J("A_load", p, s, rho=rho))
        for rho in [0.8, 1.0]:
            j.append(J("A_load", "rr_g", s, rho=rho))
        for hi in [0.0, 0.2, 0.4, 0.6, 0.8]:                               # C: sensitive share
            for p in ["epara", "tf", "tera", "trace", "static", "oracle_c", "oracle_u"]:
                j.append(J("C_sens", p, s, sens=mix(hi)))
        for lam in [0.0, 0.5, 1.0]:                                        # K: correlation
            for p in ["local", "epara", "oracle_u", "tf", "trace", "oracle_c"]:
                j.append(J("K_corr", p, s, corr=lam))
        for rho in [1.0, 1.2]:                                             # O: overload
            for p in ["epara", "tf", "trace", "tf_rr", "tf_p2c", "oracle_c"]:
                j.append(J("O_over", p, s, rho=rho, late="serve"))
            for fb in ["uniform", "p2c"]:
                j.append(J("O_over", "tf", s, rho=rho, late="serve", fallback=fb))
                j.append(J("O_over", "tf", s, rho=rho, late="drop", fallback=fb))
    for s in TEST[:20]:
        for h in [0.1, 1.0, 2.0]:                                          # E: staleness
            for rho in [0.8, 1.0]:
                for p in ["epara", "tf", "trace", "tf_jsq", "tf_p2c"]:
                    j.append(J("E_stale", p, s, rho=rho, hsync=h))
        for pl in [1.0, 0.5]:                                              # R: placement / cloud
            for cl in [None, CLOUD]:
                for p in ["epara", "tf", "trace"]:
                    j.append(J("R_cloud", p, s, place=pl, cloud=cl))
    for t in range(1, 11):                                                 # V: variance decomposition
        for w in range(5):
            for p in ["epara", "tf", "trace"]:
                j.append(J("V_var", p, t, wseed=5000 + 10 * t + w))
    for s in TEST[:10]:                                                    # P: parameter sensitivity
        P = [("kmax", [1, 3, 4]), ("l0", [0.005, 0.08]), ("horizon", [0.1, 0.25, 1.0]),
             ("fitfac", [0.0, 0.2, 1.0]), ("n_dom", [1, 2, 5]),
             ("clear_p", [(0.5, 0.3, 0.2), (0.2, 0.4, 0.4)])]
        for p in ["tf", "trace"]:
            j.append(J("P_param", p, s, param="default"))
            for name, vals in P:
                for v in vals:
                    j.append(J("P_param", p, s, param=name, **{name: v}))
        for N in [10, 30, 60, 120]:                                        # F: scale
            for p in ["tf_rr", "tf", "trace", "tf_p2c"]:
                j.append(J("F_scale", p, s, N=N))
    return j


EP = ["tf", "ew", "eb", "ec", "ewd", "ef"]


def energy_jobs():
    j = []
    base = dict(energy=True, T=180, warm=60, buf_s=120.0, init="rand")
    for s in TEST[:10]:
        for phi in [0.6, 0.9, 1.2]:                                        # B: constant supply
            for out in [False, True]:
                for p in EP:
                    j.append(J("B_energy", p, s, phi=phi, outage=out, **base))
        for phi in [0.9, 1.2]:                                             # S: solar, phased
            for out in [False, True]:
                for p in EP:
                    j.append(J("S_solar", p, s, phi=phi, outage=out, solar_amp=1.0, **base))
        for buf in [20.0, 600.0]:                                          # U: buffer timescale
            for out in [False, True]:
                for p in ["tf", "ew", "ec"]:
                    b = dict(base); b["buf_s"] = buf
                    j.append(J("U_buf", p, s, phi=0.9, outage=out, **b))
        for h in [0.1, 2.0]:                                               # G: energy staleness
            for p in ["tf", "ew", "ec"]:
                j.append(J("G_estale", p, s, phi=0.9, outage=True, solar_amp=1.0, hsync=h, **base))
    return j


if __name__ == "__main__":
    phase = sys.argv[1]
    jobs = {"tune": tune_jobs, "main": main_jobs, "energy": energy_jobs}[phase]()
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)["_k"] for l in open(OUT)}
    todo = [d for d in jobs if key(d) not in done]
    todo.sort(key=lambda d: -(d["N"] * d["T"]))
    print(phase, len(jobs), "runs;", len(todo), "to do", flush=True)
    with Pool(max(1, os.cpu_count())) as pool, open(OUT, "a") as f:
        for i, r in enumerate(pool.imap_unordered(job, todo, chunksize=1), 1):
            f.write(json.dumps(r, default=float) + "\n"); f.flush()
            if i % 50 == 0:
                print(i, "/", len(todo), flush=True)
    print("done", phase, flush=True)
