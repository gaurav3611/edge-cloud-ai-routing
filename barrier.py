import numpy as np, pandas as pd, ecsim
from ecsim import *
from multiprocessing import Pool
def job(a):
    pol,cs,seed=a
    ecsim.SENS_P[:]=[0.60,0.25,0.15]
    topo=build_topology(30,np.random.default_rng(seed)); topo["capfrac"]=np.clip(topo["capfrac"]*cs,0.05,1.0)
    r=Sim(topo,pol,0.8,30,100+seed).run(); r.update(variant=pol,capscale=cs,seed=seed); return r
if __name__=="__main__":
    jobs=[(p,cs,s) for cs in [0.35,0.5,0.7,1.0] for p in ["ours_b"] for s in [1,2,3,4,5]]
    with Pool(2) as p: rows=p.map(job,jobs)
    pd.DataFrame(rows).to_csv("results_barrier.csv",index=False)
    d=pd.DataFrame(rows); print(d.groupby("capscale")[["slo","cslo","viol","cgoodput","energy_per_good","throttled"]].mean().round(3))
