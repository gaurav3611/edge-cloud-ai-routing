"""
experiments_v2.py - full experiment suite for the paper (resumable).

Writes one JSON line per run to runs_v2.jsonl and the merged table to results_v2.csv.
Run:  .venv/bin/python experiments_v2.py      (about 5-10 min on an 8-core Apple M3)
"""
import json, os
import numpy as np, pandas as pd
from multiprocessing import Pool
import ecsim
from ecsim import build_topology, Sim

SEEDS = list(range(1, 11))
T = 30
BASE_SENS = [0.60, 0.25, 0.15]
OUT = "runs_v2.jsonl"

# job tuple: (exp, policy, rho, seed, capscale, sens, beta, theta, outage, hsync, gamma, N)
def J(exp, pol, rho=0.8, seed=1, cs=1.0, sens=BASE_SENS, beta=1.0, theta=0.25,
      outage=False, hsync=1.0, gamma=0.3, N=30):
    return (exp, pol, rho, seed, cs, list(sens), beta, theta, outage, hsync, gamma, N)


def key(a):
    return json.dumps(a)


def job(a):
    exp, pol, rho, seed, cs, sens, beta, theta, outage, hsync, gamma, N = a
    ecsim.SENS_P[:] = sens
    topo = build_topology(N, np.random.default_rng(seed))
    topo["capfrac"] = np.clip(topo["capfrac"] * cs, 0.05, 1.0)
    r = Sim(topo, pol, rho, T, 100 + seed, beta=beta, theta=theta,
            outage=outage, hsync=hsync, gamma=gamma).run()
    r.update(exp=exp, variant=pol, seed=seed, capscale=cs, sens_hi=sens[1] + sens[2],
             beta=beta, theta=theta, outage=outage, hsync=hsync, gamma=gamma, N=N)
    r["_k"] = key(a)
    return r


def all_jobs():
    jobs = []
    for s in SEEDS:
        for rho in [0.4, 0.6, 0.8, 0.9, 1.0]:                                # A: load
            for p in ["local", "rr", "rr_g", "epara", "epara_priv", "tera", "ours"]:
                jobs.append(J("A_load", p, rho, s))
        for cs in [1.0, 0.7, 0.5, 0.35]:                                     # B: energy
            for out in [False, True]:
                for p in ["epara_priv", "energy", "ours", "ours_b", "ours_c"]:
                    th = 0.0 if p == "ours_c" else 0.25
                    jobs.append(J("B_energy", p, 0.8, s, cs, theta=th, outage=out))
        for hi in [0.0, 0.2, 0.4, 0.6, 0.8]:                                 # C: privacy
            sp = [1 - hi, hi * 0.6, hi * 0.4]
            for p in ["epara", "epara_priv", "tera"]:
                jobs.append(J("C_privacy", p, 0.8, s, sens=sp))
        for b, th in [(0, 0), (0, 0.25), (0.5, 0), (1, 0), (1, 0.25), (2, 0.25), (1, 0.4)]:
            for out in [False, True]:                                        # D: energy ablation
                jobs.append(J("D_ablate", "ours", 0.8, s, 0.5, beta=b, theta=th, outage=out))
        for g in [1.0, 0.5, 0.3, 0.1]:                                       # D2: best-fit ablation
            jobs.append(J("D_gamma", "tera", 0.8, s, sens=[0.4, 0.36, 0.24], gamma=g))
        for h in [0.1, 0.25, 0.5, 1.0, 2.0]:                                 # E: sync staleness
            for rho in [0.8, 1.0]:
                for p in ["rr", "epara", "epara_priv"]:
                    jobs.append(J("E_stale", p, rho, s, hsync=h))
        for h in [0.1, 0.25, 0.5, 1.0, 2.0]:                                 # G: energy herding
            for out in [False, True]:
                for p in ["epara_priv", "ours", "ours_c"]:
                    th = 0.0 if p == "ours_c" else 0.25
                    jobs.append(J("G_estale", p, 0.8, s, 0.5, theta=th, outage=out, hsync=h))
    for s in SEEDS[:5]:
        for N in [10, 30, 60, 120]:                                          # F: scale
            for p in ["rr", "epara_priv", "tera"]:
                jobs.append(J("F_scale", p, 0.8, s, N=N))
    return jobs


if __name__ == "__main__":
    jobs = all_jobs()
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)["_k"] for l in open(OUT)}
    todo = [a for a in jobs if key(a) not in done]
    # heavy (large-N) runs first so the pool stays busy at the end
    todo.sort(key=lambda a: -a[-1])
    print(len(jobs), "runs;", len(todo), "to do", flush=True)
    with Pool(max(1, os.cpu_count() - 1)) as pool, open(OUT, "a") as f:
        for i, r in enumerate(pool.imap_unordered(job, todo), 1):
            f.write(json.dumps(r, default=float) + "\n"); f.flush()
            if i % 100 == 0:
                print(i, "/", len(todo), flush=True)
    rows = [json.loads(l) for l in open(OUT)]
    pd.DataFrame(rows).drop(columns="_k").to_csv("results_v2.csv", index=False)
    print("done", flush=True)
