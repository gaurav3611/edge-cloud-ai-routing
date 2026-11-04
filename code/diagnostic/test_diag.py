"""Short checks of the diagnostic harness: python -m pytest -q test_diag.py"""
from diag import J, run_job, sim_sha, SIM_SHA, jobs


def short(pol="trace", **kw):
    return run_job(J("diag", "t", pol, 1001, rho=1.2, T=40, warm=20, **kw))


def test_simulator_unchanged():
    assert sim_sha() == SIM_SHA


def test_design_counts():
    js = jobs()
    assert len(js) == 210 and all(1001 <= d["seed"] <= 1010 for d in js)


def test_shed_reasons_cover_every_shed():
    r, reqs = short()
    for cat, c in r["diag"].items():
        assert cat != "LS<1"
        assert c["hop_limit"] + c["early_stop"] + c["no_eligible"] == c["shed"]
    assert all(q["cat"] != "LS<1" for q in reqs)


def test_p2_only_replaces_early_stops():
    base, _ = short()
    p2, reqs = short(p2=True)
    assert sum(c["early_stop"] for c in p2["diag"].values()) == 0
    assert all(h["fallback"] is False or h["p"] is not None for q in reqs for h in q["hops"] if "pick_at" in h)
    if sum(c["early_stop"] for c in base["diag"].values()) == 0:
        assert base["by_cat"] == p2["by_cat"]
