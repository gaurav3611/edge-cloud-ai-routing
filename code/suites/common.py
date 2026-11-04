"""Job runner shared by all suites. One job is one simulation; every run is stamped with the code commit."""
import json, os, subprocess, sys, time
import numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "sim"))
from ecsim_exact import build_topology, Sim, TRUST
RAW = os.path.join(ROOT, "raw")
DEF = [0.60, 0.24, 0.16]
CLOUD = dict(slots=96, lat=0.04, clear=1, strict=True)
KW = ("beta", "theta", "outage", "hsync", "gamma", "warm", "fallback", "corr", "kmax", "l0", "horizon", "fitfac",
      "cloud", "place", "buf_s", "init", "solar_amp", "solar_period", "bf_thresh", "energy", "okey", "late",
      "pool_mix", "adm_util", "ov_proc", "ov_fwd", "ov_scope", "run_mult", "burst_sync", "ring", "trace_energy",
      "bin_s", "vflags", "burst_amp", "burst_period", "svc_share", "net_var", "net_kappa", "record",
      "event_mode", "energy_model", "e_floor", "ov_slot", "owner_cross", "q_mode", "q_hyst", "rjsq_eps", "age_hist")


def mix(hi):
    return [1 - hi, 0.6 * hi, 0.4 * hi]


def J(exp, name, pol, seed, **kw):
    """Protocol defaults: exact events, no energy, shed late work."""
    d = dict(exp=exp, name=name, pol=pol, seed=seed, rho=0.8, N=30, energy=False, late="drop", sens=DEF, record=True,
             event_mode="exact")
    d.update(kw)
    return d


def key(d):
    return json.dumps(d, sort_keys=True)


def topo_for(d):
    rng = np.random.default_rng(d["seed"])
    topo = build_topology(d["N"], rng, clear_p=d.get("clear_p", (0.30, 0.40, 0.30)), n_dom=d.get("n_dom", 3))
    if d.get("lat_scale"):
        topo["lat"] = topo["lat"] * d["lat_scale"]
    if d.get("gpu_scale"):
        topo["slots"] = np.maximum(8, (topo["slots"] * d["gpu_scale"]).astype(int))
    if "phi" in d:
        f = d["phi"] * d["rho"] * topo["slots"].sum() / (topo["capfrac"] * topo["slots"]).sum()
        topo["capfrac"] = np.clip(topo["capfrac"] * f, 0.05, 2.0)
    return topo


def job(d):
    d = dict(d); t0 = time.time()
    topo = topo_for(d)
    kw = {k: d[k] for k in KW if k in d}
    kw.setdefault("gamma", 0.3); kw.setdefault("bf_thresh", 0.30)
    r = Sim(topo, d["pol"], d["rho"], d["T"], d.get("wseed", 100 + d["seed"]), sens_p=d["sens"], **kw).run()
    if d["pol"] in TRUST and r["viol"] > 0:
        raise RuntimeError(f"trust violation in compliant run: {d}")
    r.update({k: v for k, v in d.items() if k != "cloud"})
    r["cloud_on"] = bool(d.get("cloud")); r["sens_hi"] = round(d["sens"][1] + d["sens"][2], 3)
    r["supply_kw"] = float((topo["capfrac"] * topo["slots"]).sum() * 60.0 / 1e3)
    r["wall_s"] = time.time() - t0; r["_k"] = key(d)
    return r


def commit():
    return subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
