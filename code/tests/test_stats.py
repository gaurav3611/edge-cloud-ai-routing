import os, sys
import numpy as np
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
from lib import holm, compare, family, drift, stability, bin_rate


def test_holm_known_values():
    assert list(holm([.01, .04, .03])) == pytest.approx([.03, .06, .06])


def test_holm_monotone_and_ignores_nan():
    h = holm([.001, np.nan, .5, .02])
    assert np.isnan(h[1]) and h[0] == pytest.approx(.003) and h[3] == pytest.approx(.04) and h[2] == pytest.approx(.5)


def test_compare_points_and_tost():
    rng = np.random.default_rng(0)
    y = rng.random(30); x = y + 0.0001 + rng.normal(0, 1e-5, 30)
    r = compare(x, y)
    assert r["diff"] == pytest.approx(.01, abs=1e-3) and r["tost0.5"] < 1e-6 and r["tost1.0"] < 1e-6 and r["p"] < 1e-6


def test_significant_and_equivalent_can_both_hold():
    y = np.linspace(.5, .9, 30); x = y + 0.002 + np.linspace(-1e-4, 1e-4, 30)
    f = family([compare(x, y)])
    assert f.label[0] == "S+E0.5+E1"


def test_neither_is_inconclusive():
    rng = np.random.default_rng(1)
    y = rng.random(6); x = y + rng.normal(0, .05, 6)
    assert family([compare(x, y)]).label[0] == "inconclusive"


def test_drift_is_fitted_change_over_window():
    assert drift([0, 1, 2, 3]) == pytest.approx(3)


def mk(trend, seed, close=True):
    rng = np.random.default_rng(seed)
    b = {str(i): [10000, int(10000 * (.9 + trend * i + rng.normal(0, 1e-4)))] for i in range(20)}
    return dict(bins=b, warm=0, series=[(i * 30.0, .5 + rng.normal(0, 1e-4), .1) for i in range(60)], led_init=10., led_income=90., led_charged=60., led_spill=30., led_final=10. if close else 50.)


def test_stability_passes_flat_runs():
    assert stability([mk(0, s) for s in range(12)], 0)["steady"]


def test_stability_fails_drift():
    assert not stability([mk(.002, s) for s in range(12)], 0)["stable"]


def test_stability_fails_open_ledger():
    r = stability([mk(0, s, close=False) for s in range(12)], 0)
    assert r["stable"] and not r["steady"]


def test_compare_stores_bootstrap_and_shapiro():
    rng = np.random.default_rng(2)
    y = rng.random(30); x = y + 0.01 + rng.normal(0, 1e-3, 30)
    r = compare(x, y)
    assert r["boot_lo"] < r["diff"] < r["boot_hi"] and 0 <= r["shapiro_p"] <= 1
