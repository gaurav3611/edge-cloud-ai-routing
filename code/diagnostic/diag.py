"""Large-job diagnostic (doc 05). Logs per-request decisions through a Sim subclass; the simulator file is only imported.

python diag.py run [--workers N]   all 210 runs, skips finished keys
python diag.py check               logged vs unlogged equality on 3 short jobs
"""
import argparse, gzip, hashlib, json, os, sys, time
from multiprocessing import Pool
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REV = os.path.abspath(os.path.join(HERE, "..", "..", "TRACE_revision"))
sys.path.insert(0, os.path.join(REV, "suites"))
from common import J, KW, key, topo_for, job as plain_job  # noqa: E402  (also puts sim/ on sys.path)
import ecsim_exact as E  # noqa: E402

SIM_SHA = "01f9cfe62954d887a6a3a73f0d535c40af2b2ea4c4d4a9335124a0c8fe4b5676"
RAW = os.path.join(HERE, "raw")
SEEDS = range(1001, 1011)
LOADS = (0.8, 1.0, 1.2)
W4 = dict(T=420, warm=20)
ARMS = [("A1 TRACE", "trace", {}), ("A2 TF-JSQ", "tf_jsq", {}), ("A3 large_jsq", "tracex", dict(vflags=dict(large_jsq=True))),
        ("A4 Oracle compliant", "oracle_c", {}), ("P1 TRACE hsync0.1", "trace", dict(hsync=0.1)),
        ("P2 TRACE no early stop", "trace", dict(p2=True)), ("P3 TRACE kmax4", "trace", dict(kmax=4))]


def sim_sha():
    return hashlib.sha256(open(E.__file__, "rb").read()).hexdigest()


class DiagSim(E.Sim):
    """Read-only logging; P2 is the only behaviour change and only when p2=True."""

    def __init__(self, *a, p2=False, log=True, **kw):
        super().__init__(*a, **kw)
        self.p2, self.log, self._req, self.reqs = p2, log, None, []

    def _handle(self, t0, o, l, s, dur, odom=None):
        cat, m = E.SERVICES[l][1], E.SERVICES[l][2]
        rec = dict(cat=cat, m=m, s=s, o=o, t0=round(t0, 4), hops=[]) if self.log and cat != "LS<1" else None
        g = super()._handle(t0, o, l, s, dur, odom)
        while True:                      # requests interleave in exact mode, so re-point _req on every resume
            self._req = rec
            try:
                t = next(g)
            except StopIteration:
                self._req = None
                return
            yield t

    def try_local(self, j, t, m, run, deadline, stream):
        out = super().try_local(j, t, m, run, deadline, stream)
        if self._req is not None:
            self._req["hops"].append(dict(at=int(j), local_ok=bool(out[0]), wait=round(float(out[1] - t), 4)))
        return out

    def _pick(self, cur, m, s, odom, l, visited, stream, run, t, dry=False):
        r, c = self._req, None
        if r is not None or self.p2:
            c = self._cand(cur, s, odom, l, visited)
        if r is not None:
            ids = np.flatnonzero(c)
            view = self.sp[cur, ids].copy()
            true = (self.F[ids] <= t).sum(axis=1)
        p = super()._pick(cur, m, s, odom, l, visited, stream, run, t, dry)
        fb = False
        if p is None and self.p2 and not dry and c.any():
            ids2 = np.flatnonzero(c)
            p = int(ids2[np.argmin(self.bk[cur, ids2, self.mi(m)] + self.Lv[cur, ids2])])
            self._debit(cur, p, m, stream, run)
            fb = True
        if r is not None:
            h = dict(pick_at=int(cur), ncand=int(len(ids)), p=p, fallback=fb,
                     max_true=int(true.max()) if len(ids) else 0)
            if p is not None and p in set(ids.tolist()):
                k = int(np.flatnonzero(ids == p)[0])
                h.update(view=round(float(view[k]), 2), true=int(true[k]))
            r["hops"].append(h)
        return p

    def _shed_check(self, t0, m, run, slo, stream, s, odom, l):
        rec = super()._shed_check(t0, m, run, slo, stream, s, odom, l)
        if self._req is not None:
            self._req["recov"] = bool(rec)
        return rec

    def _count(self, cat, res, viol, hops, incloud, dropped=False):
        r = self._req
        if r is not None and self.counting:
            r.update(res=bool(res), cloud=bool(incloud), dropped=bool(dropped), nhops=int(hops))
            if dropped:
                picks = [h for h in r["hops"] if "pick_at" in h]
                last = picks[-1] if picks else None
                r["reason"] = ("hop limit" if hops >= self.kmax else
                               "no eligible" if last is None or last["ncand"] == 0 else "early stop")
            self.reqs.append(r)
        super()._count(cat, res, viol, hops, incloud, dropped)


def jobs():
    return [J("diag", n, p, s, rho=r, **kw, **W4) for n, p, kw in ARMS for r in LOADS for s in SEEDS]


def tally(reqs):
    """Per-category counts for the summary row; full records go to the gz file."""
    out = {}
    for q in reqs:
        c = out.setdefault(q["cat"], dict(n=0, served=0, shed=0, recov=0, hop_limit=0, early_stop=0, no_eligible=0,
                                          picks=0, view_over=0, fallback=0))
        c["n"] += 1; c["served"] += q["res"]; c["shed"] += q["dropped"]
        if q["dropped"]:
            c["recov"] += q.get("recov", False)
            c[q["reason"].replace(" ", "_")] += 1
        for h in q["hops"]:
            if "pick_at" in h:
                c["picks"] += 1; c["fallback"] += h["fallback"]
                c["view_over"] += int("view" in h and h["view"] >= q["m"] and h["true"] < q["m"])
    return out


def run_job(d, log=True):
    d = dict(d); t0 = time.time()
    topo = topo_for(d)
    kw = {k: d[k] for k in KW if k in d}
    kw.setdefault("gamma", 0.3); kw.setdefault("bf_thresh", 0.30)
    sim = DiagSim(topo, d["pol"], d["rho"], d["T"], d.get("wseed", 100 + d["seed"]), sens_p=d["sens"],
                  p2=d.get("p2", False), log=log, **kw)
    r = sim.run()
    if d["pol"] in E.TRUST and r["viol"] > 0:
        raise RuntimeError(f"trust violation in compliant run: {d}")
    r.update({k: v for k, v in d.items() if k != "cloud"})
    r["cloud_on"] = bool(d.get("cloud")); r["sens_hi"] = round(d["sens"][1] + d["sens"][2], 3)
    r["supply_kw"] = float((topo["capfrac"] * topo["slots"]).sum() * 60.0 / 1e3)
    r["diag"] = tally(sim.reqs); r["wall_s"] = time.time() - t0; r["_k"] = key(d)
    return r, sim.reqs


def work(d):
    r, reqs = run_job(d)
    name = hashlib.sha1(r["_k"].encode()).hexdigest()[:16]
    with gzip.open(os.path.join(RAW, "req", name + ".jsonl.gz"), "wt") as f:
        for q in reqs:
            f.write(json.dumps(q) + "\n")
    r["req_file"] = name
    return r


def check():
    """Logging must not change any summary value; P2 must equal TRACE where TRACE never stops early."""
    assert sim_sha() == SIM_SHA, "simulator changed"
    for pol, kw in (("trace", {}), ("tf_jsq", {}), ("tracex", dict(vflags=dict(large_jsq=True)))):
        d = J("diag", "check", pol, 1001, rho=1.0, T=60, warm=20, **kw)
        a = plain_job(d); b, _ = run_job(d)
        diff = [k for k in a if json.dumps(a[k], sort_keys=True) != json.dumps(b.get(k), sort_keys=True)]
        timing = [k for k in diff if k == "wall_s" or k.endswith("_us")]    # wall-clock timings differ by nature
        assert diff == timing, (pol, [k for k in diff if k not in timing])
        print("equal:", pol, len(a) - len(diff), "fields; timing only differs:", timing, "| by_cat", a.get("by_cat"))
    print("check passed")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=("run", "check")); ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    if a.cmd == "check":
        return check()
    assert sim_sha() == SIM_SHA, "simulator changed"
    os.makedirs(os.path.join(RAW, "req"), exist_ok=True)
    out = os.path.join(RAW, "diag.jsonl")
    done = {json.loads(x)["_k"] for x in open(out)} if os.path.exists(out) else set()
    todo = [d for d in jobs() if key(d) not in done]
    print(len(jobs()), "runs;", len(todo), "to do;", time.ctime(), flush=True)
    with Pool(a.workers) as pool, open(out, "a") as f:
        for i, r in enumerate(pool.imap_unordered(work, todo), 1):
            f.write(json.dumps(r) + "\n"); f.flush()
            print(i, r["name"], r["rho"], r["seed"], round(r["wall_s"], 1), flush=True)
    assert sim_sha() == SIM_SHA, "simulator changed during run"
    print("done", time.ctime())


if __name__ == "__main__":
    main()
