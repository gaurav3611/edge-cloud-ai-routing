"""Implementation tests for the revision simulator. Run: pytest -q tests"""
import json, os, sys
import numpy as np
import pytest
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "sim"), os.path.join(ROOT, "suites"), os.path.join(ROOT, "analysis")]
import ecsim_exact as V
from common import J, job, topo_for, mix

AUDIT = os.path.join(ROOT, "research_audit_20261031_142228")
SKIP = {"dec_us", "dec_per_req_us", "_k", "wall_s", "n_counted", "tail_slot_s", "event_mode"}


def sim(pol="trace", T=30, seed=11, rho=0.8, N=20, **kw):
    t = V.build_topology(N, np.random.default_rng(seed))
    if "phi" in kw:
        f = kw.pop("phi") * rho * t["slots"].sum() / (t["capfrac"] * t["slots"]).sum()
        t["capfrac"] = np.clip(t["capfrac"] * f, 0.05, 2.0)
    kw.setdefault("late", "drop"); kw.setdefault("warm", 5.0); kw.setdefault("energy", False)
    return V.Sim(t, pol, rho, T, seed + 100, **kw)


@pytest.mark.parametrize("raw,exp", [("12_variant_implementations/raw/held.jsonl", "held"), ("12_variant_implementations/raw/net.jsonl", "ring"),
                                     ("12_variant_implementations/raw/energy.jsonl", "energy")])
def test_batch_reproduces_stored_runs(raw, exp):
    """Regression gate: batch mode must equal stored raw rows on every stored field."""
    rows = [json.loads(l) for l in open(os.path.join(AUDIT, raw))]
    rows = [r for r in rows if r["exp"] == exp]
    rows = sorted(rows, key=lambda r: r["T"])[:2]
    for o in rows:
        d = json.loads(o["_k"]); d["event_mode"] = "batch"
        r = job(d)
        for k, v in o.items():
            if k in SKIP or k == "cloud":
                continue
            if isinstance(v, float):
                assert r[k] == pytest.approx(v, rel=1e-9, abs=1e-9), k
            else:
                assert r[k] == v, k


def test_tracex_defaults_equal_trace():
    a, b = sim("trace").run(), sim("tracex").run()
    assert a["cslo"] == b["cslo"] and a["bcslo"] == b["bcslo"]


def test_exact_events_are_time_ordered():
    s = sim(event_mode="exact")
    seen = []
    orig = s.commit
    def spy(j, idx, st, fin, m):
        seen.append(s.now_e); orig(j, idx, st, fin, m)
    s.commit = spy
    s.run()
    assert np.all(np.diff(seen) >= 0)
    b = sim()
    seen2 = []
    orig2 = b.commit
    def spy2(j, idx, st, fin, m):
        seen2.append(b.now_e); orig2(j, idx, st, fin, m)
    b.commit = spy2
    b.run()
    assert np.any(np.diff(seen2) < 0)    # the batch model reserves out of order


def test_exact_refresh_grid():
    s = sim(event_mode="exact", hsync=0.5)
    ts = []
    o = s.refresh
    s.refresh = lambda t: (ts.append(t), o(t))
    s.run()
    assert ts[:4] == [0.0, 0.5, 1.0, 1.5]


@pytest.mark.parametrize("seed", [1, 2])
@pytest.mark.parametrize("mode", ["batch", "exact"])
def test_seed_reproducible(seed, mode):
    a = sim(seed=seed, event_mode=mode).run(); b = sim(seed=seed, event_mode=mode).run()
    for k in ("cslo", "bcslo", "hops", "drop"):
        assert a[k] == b[k]


@pytest.mark.parametrize("phi", [0.6, 0.9, 1.2])
@pytest.mark.parametrize("outage", [False, True])
def test_energy_conservation(phi, outage):
    r = sim("tf", T=120, phi=phi, outage=outage, energy=True, energy_model="bounded", event_mode="exact", buf_s=20.0, init="rand").run()
    lhs = r["led_init"] + r["led_income"]
    rhs = r["led_charged"] + r["led_spill"] + r["led_final"]
    assert lhs == pytest.approx(rhs, rel=1e-9)


def test_legacy_soft_overdraws_bounded_does_not():
    kw = dict(T=200, phi=0.6, energy=True, buf_s=20.0, init="rand", event_mode="exact")
    leg = sim("tf", **kw).run(); bou = sim("tf", energy_model="bounded", **kw).run()
    assert leg["level_min_frac"] < -1.0
    # bounded debt: at worst the income of the longest job, stored as a fraction of a 20 s buffer
    assert bou["level_min_frac"] >= -15.0 / 20.0 - 1e-9


def test_charged_power_never_exceeds_supply_plus_start_charge():
    r = sim("tf", T=200, phi=0.6, energy=True, energy_model="bounded", event_mode="exact", buf_s=20.0).run()
    assert r["led_charged"] <= r["led_init"] + r["led_income"] + 1e-6


def test_admission_floor_refuses_and_charges_nothing():
    s = sim("tf", energy=True, energy_model="bounded", buf_s=20.0)
    s.gen_arrivals(); s.now_e = 0.0; s._slowed = False
    s.level[:] = 0.0
    ok, *_ = s.try_local(0, 0.0, 8, 10.0, 1.0, True)
    assert not ok


def test_throttled_job_runs_slower_at_lower_power_same_energy():
    s = sim("tf", energy=True, energy_model="bounded", buf_s=20.0)
    s.now_e = 0.0; s._slowed = False
    s.level[:] = 0.03 * s.bcap
    ok, st, fin, thr, idx = s.try_local(0, 0.0, 1, 0.03, 1.0, False)
    assert thr and ok and fin - st == pytest.approx(0.03 * V.THROTTLE)
    b = s.level[0]
    s.commit(0, idx, st, fin, 1)
    assert b - s.level[0] == pytest.approx(0.03 * V.P_SLOT)


def test_slot_occupancy():
    a = sim("tf", ov_proc=0.02, ov_scope="all", record=True).run()
    b = sim("tf", ov_proc=0.02, ov_scope="all", ov_slot=True, record=True).run()
    c = sim("tf", record=True).run()
    assert b["edge_util"] > a["edge_util"]        # in-slot delay holds capacity
    assert a["edge_util"] == pytest.approx(c["edge_util"], rel=0.03)    # pre-service delay does not


def test_owner_domain_governs_eligibility():
    s = sim("tf", owner_cross=1.0, event_mode="exact", sens_p=[0, 0, 1.0])
    seen = []
    o = s.serve_at
    orig = s.commit
    def spy(j, idx, st, fin, m):
        seen.append((j, s._dc_ctx)); orig(j, idx, st, fin, m)
    s.commit = spy
    r = s.run()
    assert r["viol"] == 0 and len(seen) > 0
    dom = s.t["dom"]
    assert all(dom[j] == ctx[2] and s.t["clear"][j] >= 2 for j, ctx in seen)
    assert any(dom[ctx[0]] != ctx[2] for _, ctx in seen)      # ingress outside the owner domain still relays


def test_owner_stream_leaves_arrivals_unchanged():
    a = sim("tf").gen_arrivals(); b = sim("tf", owner_cross=0.5).gen_arrivals()
    assert np.array_equal(a["t"], b["t"]) and np.array_equal(a["o"], b["o"])


def test_effective_view_age_adds_refresh_and_ring():
    H = 1.0
    plain = sim("tf", T=40, hsync=H, event_mode="exact").run()
    assert plain["view_age_eff_s"] == pytest.approx(H / 2, abs=0.05)
    r = sim("tf", T=40, hsync=H, event_mode="exact", ring=True, N=60).run()
    assert r["view_age_eff_s"] == pytest.approx(H / 2 + r["ring_time_s"] / 2, abs=0.1)


def test_metric_aggregation():
    r = sim("tf", T=60).run()
    cats = ["LS<1", "LS>1", "FS<1", "FS>1"]
    assert r["bcslo"] == pytest.approx(np.mean([r["cslo_" + c] for c in cats]))


def test_hysteresis_counts_fewer_switches():
    kw = dict(pol="tracex", sens_p=mix(0.3), T=60, bf_thresh=0.30)
    a = sim(q_hyst=1e-9, **kw).run(); b = sim(q_hyst=0.05, **kw).run()
    assert b["bf_switch"] <= a["bf_switch"] and a["bf_switch"] > 0


@pytest.mark.parametrize("pol", ["tf_rjsq", "tf_p3c", "pashe_a", "singh_a"])
def test_new_baselines_compliant(pol):
    assert sim(pol, event_mode="exact").run()["viol"] == 0


@pytest.mark.parametrize("fl", [dict(local_bf=True), dict(trunk=.25), dict(trunk=.25, trunk_hard=True), dict(adm_big=.2), dict(adm_small=.2), dict(large_jsq="8")])
def test_flags_compliant(fl):
    assert sim("tracex", vflags=fl, event_mode="exact").run()["viol"] == 0


def test_serve_late_cannot_overdraw():
    r = sim("tf", T=200, late="serve", phi=0.6, energy=True, energy_model="bounded", event_mode="exact", buf_s=20.0).run()
    assert r["level_min_frac"] >= -15.0 / 20.0 - 1e-9


def test_stored_v3_rows_reproduce_in_batch_mode():
    """Stand-in for the audit-folder gate: uses the original runs file, which stays readable."""
    path = os.path.expanduser("~/Desktop/sim/runs_v3.jsonl")
    rows = {}
    for l in open(path):
        o = json.loads(l)
        rows.setdefault(o["exp"], o) if o["T"] == 60 and o["exp"] in ("A_load", "R_cloud", "K_corr") else None
    for o in rows.values():
        r = job(json.loads(o["_k"]))
        for k in ("cslo", "bcslo", "viol", "hops", "drop"):
            assert r[k] == pytest.approx(o[k], rel=1e-9, abs=1e-9), (o["exp"], k)


def _late_cloud(strict):
    s = sim("tf", cloud=dict(slots=8, lat=0.04, clear=2, strict=strict))
    s.now = 0.0
    s.cF[:] = 100.0                     # cloud full, so its deadline is lost
    return s, s.to_cloud(0.0, 1, 0.03, 0.15, False, 0, force=True)


def test_strict_cloud_sheds_a_lost_deadline():
    s, out = _late_cloud(True)
    assert out is None and (s.cF == 100.0).all()
    s, out = _late_cloud(False)
    assert out == (False, False)        # legacy path kept, so stored rows still replay


def test_cloud_constant_is_strict():
    from common import CLOUD
    assert CLOUD["strict"]


def test_bounded_series_logs_true_level():
    s = sim("tf", energy=True, energy_model="bounded", trace_energy=True, buf_s=20.0)
    s.level[:] = -0.2 * s.bcap
    s._trace_energy(0.0)
    assert s.en["series"][0][1] == pytest.approx(-0.2)
    s = sim("tf", energy=True, trace_energy=True, buf_s=20.0)
    s.level[:] = -0.2 * s.bcap
    s._trace_energy(0.0)
    assert s.en["series"][0][1] == 0.0  # legacy rows unchanged


def test_view_age_histogram_counts_every_decision():
    r = sim("tf", T=30, hsync=1.0, event_mode="exact", age_hist=True).run()
    b = r["view_age_hist"]
    assert max(int(k) for k in b) <= 10 and sum(b.values()) > 0


def test_age_flags_default_to_stored_behaviour():
    a, b = sim("tf_jsq").run(), sim("tf_jsq", vflags=dict(age_jsq=False)).run()
    assert a["cslo"] == b["cslo"]
    a, b = sim("tf_jsq").run(), sim("tf_jsq", vflags=dict(age_jsq=True)).run()
    assert a["cslo"] != b["cslo"]
    a, b = sim("tracex", vflags=dict(large_jsq=True)).run(), sim("tracex", vflags=dict(large_jsq=True, age_large=False)).run()
    assert a["bcslo"] != b["bcslo"]


def test_work_weights_follow_the_run_mix(tmp_path, monkeypatch):
    import lib
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "x.jsonl").write_text(json.dumps({"svc_share": [.4, .2, .2, .2], "cslo_LS<1": 1.0, "cslo_LS>1": 0.0, "cslo_FS<1": 0.0, "cslo_FS>1": 0.0}) + "\n")
    monkeypatch.setattr(lib, "ROOT", str(tmp_path))
    assert lib.load("x").wcslo[0] == pytest.approx(.4)
