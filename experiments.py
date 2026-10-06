import sys, itertools, numpy as np, pandas as pd
from multiprocessing import Pool
import ecsim
from ecsim import *

POLS = ["local","rr","epara","epara_priv","energy","ours"]
SEEDS = [1,2,3,4,5]
T, N = 30, 30

def wrap(a):
    r = job(a)
    r['_k'] = __import__('json').dumps([a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7]])
    return r

def job(a):
    exp, pol, rho, seed, capscale, sensp, beta, theta = a
    ecsim.SENS_P[:] = sensp
    topo = build_topology(N, np.random.default_rng(seed))
    topo["capfrac"] = np.clip(topo["capfrac"]*capscale, 0.05, 1.0)
    r = Sim(topo, pol, rho, T, 100+seed, beta=beta, theta=theta).run()
    r.update(exp=exp, seed=seed, capscale=capscale, sens_hi=sensp[1]+sensp[2], beta=beta, theta=theta)
    return r

if __name__ == "__main__":
    base_sens = [0.60,0.25,0.15]
    jobs = []
    for rho in [0.4,0.6,0.8,1.0]:                       # A: load sweep
        for p in POLS:
            for s in SEEDS: jobs.append(("A_load",p,rho,s,1.0,base_sens,1.0,0.25))
    for cs in [1.0,0.7,0.5,0.35]:                       # B: energy scarcity
        for p in ["epara_priv","energy","ours"]:
            for s in SEEDS: jobs.append(("B_energy",p,0.8,s,cs,base_sens,1.0,0.25))
    for hi in [0.0,0.2,0.4,0.6,0.8]:                    # C: privacy strictness
        sp = [1-hi, hi*0.6, hi*0.4]
        for p in ["epara","epara_priv","ours"]:
            for s in SEEDS: jobs.append(("C_privacy",p,0.8,s,1.0,sp,1.0,0.25))
    for beta,theta in [(0,0.0),(0.5,0.25),(1,0.25),(2,0.25),(1,0.0),(1,0.4)]:   # D: ablation, scarce energy
        for s in SEEDS: jobs.append(("D_ablate","ours",0.8,s,0.5,base_sens,beta,theta))
    import json, os
    key = lambda a: json.dumps([a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7]])
    done = {}
    if os.path.exists("runs.jsonl"):
        for l in open("runs.jsonl"):
            d = json.loads(l); done[d["_k"]] = d
    todo = [a for a in jobs if key(a) not in done]
    print(len(jobs),"runs;",len(todo),"to do", flush=True)
    with Pool(2) as pool, open("runs.jsonl","a") as f:
        for r in pool.imap_unordered(wrap, todo):
            f.write(json.dumps(r, default=float)+"\n"); f.flush()
    rows = [json.loads(l) for l in open("runs.jsonl")]
    pd.DataFrame(rows).drop(columns="_k").to_csv("results.csv", index=False)
    print("done", flush=True)
