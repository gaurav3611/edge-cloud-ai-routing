"""Event-order analysis on synthetic rows. Run: pytest -q tests/test_event_order.py"""
import os, sys
import numpy as np, pandas as pd
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
from event_order import guarded, shifts, gaps


def rows(shift):
    rng = np.random.default_rng(0); out = []
    base = rng.uniform(.8, .9, 12)
    for seed, b in zip(range(4001, 4013), base):
        for name, d in (("TRACE", .01), ("TF", 0.)):
            out.append(dict(seed=seed, rho=.8, name=name, cslo=b + d + shift.get(name, 0) + rng.normal(0, 1e-4)))
    return pd.DataFrame(out)


def test_shift_is_exact_minus_batch_per_router():
    s = shifts(rows({}), rows({"TRACE": -.02}), metrics=["cslo"]).set_index("name")["diff"]
    assert s["TRACE"] == pytest.approx(-2, abs=.01) and s["TF"] == pytest.approx(0, abs=.01)


def test_gap_reports_a_sign_flip():
    g = gaps(rows({}), rows({"TRACE": -.02}), metrics=("cslo",)).iloc[0]
    assert g.gap_batch == pytest.approx(1, abs=.02) and g.gap_exact == pytest.approx(-1, abs=.02) and g.sign_flip
    assert g.change == pytest.approx(-2, abs=.01)


def test_held_out_seeds_are_refused():
    with pytest.raises(ValueError):
        guarded(pd.DataFrame(dict(seed=[4001, 8001])), "bridge")
