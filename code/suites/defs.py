"""Suite definitions. Each suite is a function returning job dicts. See docs/protocol.md for seeds and windows."""
import json, os
from common import J, DEF, CLOUD, ROOT, mix

LOADS = [.5, .8, 1., 1.2]
TUNE = range(1001, 1021); STUDY = range(1101, 1161); VAL2 = range(3101, 3131); HELD2 = range(8001, 8031)
BRIDGE = range(4001, 4031); ROB = range(5001, 5021); SCALE = range(6001, 6021); LONG = range(7001, 7013)
W2 = dict(T=120, warm=20); W3 = dict(T=220, warm=20); W4 = dict(T=420, warm=20)
LJ = dict(large_jsq=True)
OLD = [("TRACE", "trace", {}), ("TF", "tf", {}), ("TF-JSQ", "tf_jsq", {}), ("soft-JSQ", "tf_sjsq", {}), ("TF-P2C", "tf_p2c", {}),
       ("TF-RR", "tf_rr", {}), ("Static eq", "static", {}), ("Static sized", "static_sized", {}),
       ("Oracle compliant", "oracle_c", {}), ("Oracle unconstrained", "oracle_u", {}), ("JSQ oblivious", "jsq", {}),
       ("EPARA-style", "epara", {}), ("Local", "local", {}), ("TRACE fit0", "trace", dict(fitfac=0.0)),
       ("large_jsq", "tracex", dict(vflags=LJ))]
NEW = [("TF-P3C", "tf_p3c", {}), ("rand-JSQ", "tf_rjsq", {}), ("PASHE-a", "pashe_a", {}), ("Singh-a", "singh_a", {})]
CAND = {"large8": dict(large_jsq="8"), "large+frag": dict(large_jsq=True, frag=True), "frag": dict(frag=True),
        "adm_big.05": dict(adm_big=.05), "adm_big.1": dict(adm_big=.1), "adm_big.2": dict(adm_big=.2), "adm_big.3": dict(adm_big=.3),
        "adm_small.05": dict(adm_small=.05), "adm_small.1": dict(adm_small=.1), "adm_small.2": dict(adm_small=.2),
        "large+adm_small.1": dict(large_jsq=True, adm_small=.1), "large+adm_big.1": dict(large_jsq=True, adm_big=.1),
        "trunk.1": dict(trunk=.1), "trunk.25": dict(trunk=.25), "trunk.5": dict(trunk=.5), "trunk.25h": dict(trunk=.25, trunk_hard=True),
        "local_bf": dict(local_bf=True)}


def frozen():
    return json.load(open(os.path.join(ROOT, "registry", "frozen.json")))


def rjsq_rows(f):
    return [(n, "tf_rjsq", dict(rjsq_eps=e)) for n, e in f["carried_rjsq"].items()]


def rows_fin():
    f = frozen()
    return OLD + NEW + [(n, "tracex", dict(vflags=v)) for n, v in f["carried"].items()] + rjsq_rows(f)


def bridge():
    return [J("bridge", n, p, s, rho=r, **kw, **W3) for s in BRIDGE for r in LOADS for n, p, kw in OLD]


def tune():
    j = [J("tune", n, p, s, rho=r, **kw, **W2) for s in TUNE for r in LOADS for n, p, kw in OLD[:6] + OLD[13:] + NEW]
    j += [J("tune", f"rand-JSQ e{e}", "tf_rjsq", s, rho=r, rjsq_eps=e, **W2) for s in TUNE for r in LOADS for e in (.002, .05)]
    j += [J("tune", n, "tracex", s, rho=r, vflags=f, **W2) for s in TUNE for r in LOADS for n, f in CAND.items()]
    return j


def gamma():
    return [J("gamma", f"g{g}", "tera" if g < 1 else "tf", s, rho=r, gamma=g, **W2) for s in STUDY for r in (.8, 1.) for g in (.1, .3, .5, .7, 1.)]


def qstar():
    j = []
    for s in list(STUDY)[:20]:
        for hi in (.1, .2, .3, .4, .5, .6):
            for q in (0., .1, .2, .25, .3, .35, .4, .5, .6, 2.):
                for qm in ("count", "slotsec"):
                    j.append(J("qstar", f"q{q} {qm}", "trace", s, bf_thresh=q, q_mode=qm, sens=mix(hi), **W2))
            if hi in (.2, .3, .4):
                for h in (.02, .05, .1):
                    j.append(J("qstar", f"hyst{h}", "trace", s, bf_thresh=.3, q_hyst=h, sens=mix(hi), **W2))
    return j


def val2():
    f = frozen()
    return [J("val2", n, p, s, rho=r, **kw, **W2) for s in VAL2 for r in LOADS
            for n, p, kw in [("TRACE", "trace", {}), ("TF-JSQ", "tf_jsq", {})] + [(a, "tracex", dict(vflags=v)) for a, v in f["shortlist"].items()] + rjsq_rows(f)]


def main():
    return [J("main", n, p, s, rho=r, **kw, **W4) for s in HELD2 for r in LOADS for n, p, kw in rows_fin()]


def abl():
    j = []
    for s in HELD2:
        for r in LOADS:
            for tag, base in (("TRACE", {}), ("large_jsq", LJ)):
                j.append(J("abl", tag + " | no load", "tracex", s, rho=r, vflags={**base, "no_load": True}, **W4))
                j.append(J("abl", tag + " | no net", "tracex", s, rho=r, vflags={**base, "no_net": True}, **W4))
                j.append(J("abl", tag + " | no best-fit", "tracex", s, rho=r, vflags=base, bf_thresh=2.0, **W4))
                j.append(J("abl", tag + " | serve late", "tracex", s, rho=r, vflags=base, late="serve", **W4))
            for n, p, kw in (("TF-JSQ", "tf_jsq", {}), ("Static sized", "static_sized", {}), ("soft-JSQ", "tf_sjsq", {}), ("TF-RR", "tf_rr", {}),
                             ("Oracle compliant", "oracle_c", {})):
                j.append(J("abl", n + " | serve late", p, s, rho=r, late="serve", **kw, **W4))
    return j


FIVE = [("TRACE", "trace", {}), ("TF-JSQ", "tf_jsq", {}), ("rand-JSQ", "tf_rjsq", {}), ("TF-P3C", "tf_p3c", {}), ("large_jsq", "tracex", dict(vflags=LJ))]


def stale():
    return [J("stale", n, p, s, rho=r, N=N, hsync=h, ring=ri, age_hist=True, **kw, **W2) for s in ROB for r in (.8, 1.) for N in (30, 120)
            for h in (.1, .5, 1., 2.) for ri in (False, True) for n, p, kw in FIVE]


def scale():
    return [J("scale", n, p, s, rho=r, N=N, gpu_scale=g, hsync=h, **kw, **W2) for s in SCALE for r in (.8, 1.)
            for N, g in ((30, 1.), (60, 1.), (120, 1.), (30, 2.)) for h in (1., .1) for n, p, kw in FIVE]


SETTINGS = {
    "default": {}, "N=15": dict(N=15), "N=60": dict(N=60), "burst 0": dict(burst_amp=0.0), "burst 0.4": dict(burst_amp=.4),
    "burst period 10": dict(burst_period=10.0), "burst period 40": dict(burst_period=40.0),
    "small-heavy mix": dict(svc_share=[.4, .2, .2, .2]), "large-heavy mix": dict(svc_share=[.1, .4, .1, .4]),
    "sensitive 20%": dict(sens=mix(.2)), "sensitive 60%": dict(sens=mix(.6)), "clear .5/.3/.2": dict(clear_p=(.5, .3, .2)),
    "clear .2/.4/.4": dict(clear_p=(.2, .4, .4)), "latency x0.5": dict(lat_scale=.5), "latency x2": dict(lat_scale=2.0),
    "net var .3": dict(net_var=.3), "slots x0.5": dict(gpu_scale=.5), "slots x2": dict(gpu_scale=2.0), "Kmax 1": dict(kmax=1),
    "Kmax 3": dict(kmax=3), "T=60": dict(T=60, warm=10), "T=420": dict(T=420, warm=20), "cloud 40ms": dict(cloud=CLOUD),
    "cloud 80ms": dict(cloud={**CLOUD, "lat": .08}), "attested x1.2": dict(run_mult=1.2, ov_scope="sens"),
    "crypto 5 ms": dict(ov_proc=.005, ov_scope="sens"), "l0 5 ms": dict(l0=.005), "l0 80 ms": dict(l0=.08), "horizon .25": dict(horizon=.25), "horizon 1": dict(horizon=1.),
    "fit 0": dict(fitfac=0.), "fit .2": dict(fitfac=.2), "domains 2": dict(n_dom=2), "domains 5": dict(n_dom=5)}


def robust():
    return [J("robust", n, p, s, rho=r, setting=name, **kw, **{**W2, **c}) for s in ROB for r in (.8, 1.) for name, c in SETTINGS.items()
            for n, p, kw in (FIVE[0], FIVE[1], FIVE[4])]


def place():
    return [J("place", n, p, s, rho=r, place=pl, **({"cloud": c} if c else {}), cl=cn, **kw, **W2) for s in ROB for r in (.8, 1.) for pl in (1., .5)
            for cn, c in (("none", None), ("40", CLOUD), ("80", {**CLOUD, "lat": .08})) for n, p, kw in (FIVE[0], FIVE[1], FIVE[4], ("TF", "tf", {}))]


def viol():
    return [J("viol", n, p, s, corr=c, **W3) for s in HELD2 for c in (0., .25, .5, .75, 1.)
            for n, p in (("EPARA-style", "epara"), ("JSQ oblivious", "jsq"), ("Oracle unconstrained", "oracle_u"), ("RR", "rr"), ("TRACE", "trace"))]


def mixs():
    j = []
    for s in HELD2:
        for hi in (0., .2, .4, .6, .8):
            m = mix(hi)
            j += [J("mix", n, p, s, sens=m, **kw, **W3) for n, p, kw in (FIVE[0], FIVE[1], FIVE[4], ("Oracle compliant", "oracle_c", {}),
                  ("Static sized", "static_sized", {}), ("Static sized40", "static_sized", dict(pool_mix=DEF)), ("TRACE no best-fit", "trace", dict(bf_thresh=2.0)))]
    return j


def fallback():
    return [J("fallback", f"TF {f}", "tf", s, rho=r, fallback=f, **W3) for s in HELD2 for r in LOADS for f in ("none", "uniform", "p2c")]


def topovar():
    return [J("topovar", n, p, s, wseed=w, **W2) for s in range(5001, 5011) for w in (9001, 9002, 9003, 9004, 9005) for n, p in (("EPARA-style", "epara"), ("TRACE", "trace"))]


def crypto():
    j = []
    for s in ROB:
        for r in (.8, 1.):
            for n, p, kw in (FIVE[0], FIVE[1], FIVE[4]):
                C = dict(rho=r, ov_scope="sens", **kw, **W2)
                j.append(J("crypto", n, p, s, design="none", x=0., mode="wait", **C))
                j.append(J("crypto", n, p, s, design="D1", x=.05, mode="wait", ov_proc=.05e-3, **C))
                for ms in (2, 5, 10, 20, 40):
                    j.append(J("crypto", n, p, s, design="D2", x=ms, mode="wait", ov_proc=ms / 1e3, **C))
                    j.append(J("crypto", n, p, s, design="D2", x=ms, mode="slot", ov_proc=ms / 1e3, ov_slot=True, **C))
                for ms in (5, 10, 20, 40, 60):
                    j.append(J("crypto", n, p, s, design="D3", x=ms, mode="wait", ov_fwd=ms / 1e3, **C))
                for x in (1.05, 1.1, 1.3, 1.5):
                    j.append(J("crypto", n, p, s, design="D4", x=x, mode="slot", run_mult=x, **C))
    return j


def owner():
    return [J("owner", n, p, s, rho=r, owner_cross=c, **kw, **W2) for s in ROB for r in (.8, 1.) for c in (0., .25, .5, 1.) for n, p, kw in (FIVE[0], FIVE[1])]


EN = [("TF", "tf", {}), ("TF+EW", "ew", {}), ("TF+EB", "eb", {}), ("TF+EC", "ec", {}), ("TF+EWD", "ewd", {}), ("TF+EF", "ef", {}),
      ("TRACE", "trace", {}), ("TF-JSQ", "tf_jsq", {}), ("large_jsq", "tracex", dict(vflags=LJ)), ("large+ewd", "tracex", dict(vflags=dict(large_jsq=True, ewd=True))),
      ("TRACE+ewd", "tracex", dict(vflags=dict(ewd=True)))]
BE = dict(energy=True, energy_model="bounded", init="rand", buf_s=120.0, record=False)


def energy_short():
    j = []
    for s in range(1, 41):
        for n, p, kw in EN:
            for phi in (.6, .9, 1.2):
                for o in (False, True):
                    j.append(J("eshort", n, p, s, phi=phi, outage=o, supply="const", T=180, warm=60, **kw, **BE))
                    if phi > .6:
                        j.append(J("eshort", n, p, s, phi=phi, outage=o, supply="solar", solar_amp=1.0, T=180, warm=60, **kw, **BE))
    return j


def energy_long():
    j = []
    L7 = [EN[i] for i in (0, 1, 4, 6, 7, 8, 9)]
    for s in LONG:
        for n, p, kw in L7:
            for phi in (.6, .9, 1.2):
                for o in (False, True):
                    j.append(J("elong", n, p, s, phi=phi, outage=o, T=3600, warm=1200, bin_s=300, trace_energy=True, **kw, **BE))
    return j


def energy_xlong():
    j = []
    for s in list(LONG)[:8]:
        for n, p, kw in [EN[i] for i in (0, 1, 4, 6, 7)]:
            for phi in (.6, .9):
                for o in (False, True):
                    j.append(J("exlong", n, p, s, phi=phi, outage=o, T=14400, warm=7200, bin_s=1200, trace_energy=True, **{**kw, **BE, "buf_s": 600.0}))
    return j


def estim():
    """Exploratory, tuning seeds: does the view-age term in a backlog read change a JSQ result? Audit finding N01."""
    R = [("TF-JSQ", "tf_jsq", {}), ("TF-JSQ aged", "tf_jsq", dict(vflags=dict(age_jsq=True))),
         ("large_jsq", "tracex", dict(vflags=LJ)), ("large_jsq unaged", "tracex", dict(vflags=dict(large_jsq=True, age_large=False)))]
    return [J("estim", n, p, s, rho=r, **kw, **W2) for s in TUNE for r in LOADS for n, p, kw in R]


def eventcmp():
    """Same seeds, batch against exact, with forwards, for the event-order table."""
    return [J("eventcmp", n, p, s, rho=r, event_mode=m, **kw, **W3) for s in range(5001, 5021) for r in (.8, 1.) for m in ("batch", "exact")
            for n, p, kw in (FIVE[0], FIVE[1], ("TF-RR", "tf_rr", {}), ("TF", "tf", {}), FIVE[4], ("EPARA-style", "epara", {}))]


SUITES = dict(estim=estim, bridge=bridge, tune=tune, gamma=gamma, qstar=qstar, val2=val2, main=main, abl=abl, stale=stale, scale=scale, robust=robust, place=place,
              viol=viol, mix=mixs, fallback=fallback, topovar=topovar, crypto=crypto, owner=owner, eventcmp=eventcmp,
              eshort=energy_short, elong=energy_long, exlong=energy_xlong)
