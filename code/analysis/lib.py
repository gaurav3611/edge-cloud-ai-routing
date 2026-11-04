"""Statistics used by every analysis. Differences are in points (fraction x 100). Paired by seed."""
import json, os
import numpy as np, pandas as pd
from scipy import stats
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CATS = ["LS<1", "LS>1", "FS<1", "FS>1"]
WEIGHTS = dict(zip(CATS, (.2, .3, .3, .2)))
MET = dict(cslo="C-SLO", bcslo="C-SLObal", wcslo="Work-weighted")
DROP = ("series", "bins", "sens", "vflags", "cloud", "_k", "clear_p", "svc_share")


def load(suite, keep=()):
    """Raw rows as a DataFrame, with the work-weighted metric added. Raw files are only read."""
    rows = []
    for l in open(os.path.join(ROOT, "raw", suite + ".jsonl")):
        r = json.loads(l)
        w = dict(zip(CATS, r["svc_share"])) if r.get("svc_share") else WEIGHTS      # demand shares of this run
        r["wcslo"] = sum(w[c] * r.get("cslo_" + c, 0.0) for c in CATS)
        for k in DROP:
            if k not in keep:
                r.pop(k, None)
        rows.append(r)
    return pd.DataFrame(rows)


def holm(p):
    """Holm step-down adjusted p-values, nan entries are left out of the family."""
    p = np.asarray(p, float); out = np.full(len(p), np.nan)
    idx = np.flatnonzero(~np.isnan(p)); m = len(idx)
    run = 0.0
    for k, i in enumerate(idx[np.argsort(p[idx], kind="stable")]):
        run = max(run, min(1.0, (m - k) * p[i]))
        out[i] = run
    return out


def compare(x, y, margins=(0.5, 1.0)):
    """x - y paired, in points. x and y are fractions aligned by seed."""
    d = (np.asarray(x, float) - np.asarray(y, float)) * 100
    n = len(d); m = d.mean(); sd = d.std(ddof=1) if n > 1 else 0.0; se = sd / np.sqrt(n)
    tc = stats.t.ppf(.975, n - 1)
    out = dict(n=n, diff=m, sd=sd, ci95=tc * se, dz=(m / sd if sd > 0 else 0.0), wins=int((d > 0).sum()), losses=int((d < 0).sum()))
    out["p"] = 1.0 if np.all(d == 0) else float(stats.wilcoxon(d).pvalue)
    out["p_t"] = 1.0 if se == 0 else float(2 * stats.t.sf(abs(m / se), n - 1))
    boot = np.random.default_rng(0).choice(d, (2000, n)).mean(1) if n > 1 else np.full(1, m)
    out["boot_lo"], out["boot_hi"] = (float(q) for q in np.quantile(boot, [.025, .975]))
    out["shapiro_p"] = float(stats.shapiro(d).pvalue) if n >= 3 and sd > 0 else np.nan
    for mg in margins:
        out[f"tost{mg}"] = (0.0 if abs(m) < mg else 1.0) if se == 0 else float(max(stats.t.sf((m + mg) / se, n - 1), stats.t.cdf((m - mg) / se, n - 1)))
    return out


def label(r, alpha=0.05):
    """Independent labels: S significant after Holm, E05 and E10 equivalent at each margin. Both may hold."""
    t = []
    if r["p_h"] < alpha:
        t.append("S")
    if r.get("tost0.5_h", 1) < alpha:
        t.append("E0.5")
    if r.get("tost1.0_h", 1) < alpha:
        t.append("E1")
    return "+".join(t) or "inconclusive"


def family(rows):
    """Add Holm-adjusted p and TOST within one declared family, then labels."""
    f = pd.DataFrame(rows)
    f["p_h"] = holm(f["p"])
    for mg in ("tost0.5", "tost1.0"):
        f[mg + "_h"] = holm(f[mg])
    f["label"] = [label(r) for r in f.to_dict("records")]
    return f


def pairs(df, a, b, metric, by="name", on="seed"):
    x = df[df[by] == a].set_index(on)[metric]; y = df[df[by] == b].set_index(on)[metric]
    ix = x.index.intersection(y.index)
    return x.loc[ix].sort_index(), y.loc[ix].sort_index()


def ci(x):
    x = np.asarray(x, float)
    return stats.t.ppf(.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))


def drift(values):
    """OLS change across a window of bins, as first-to-last fitted difference."""
    y = np.asarray(values, float); t = np.arange(len(y))
    return float(np.polyfit(t, y, 1)[0] * (len(y) - 1))


def bin_rate(bins):
    return [v[1] / max(v[0], 1) for k, v in sorted(bins.items(), key=lambda z: int(z[0]))]


def stability(rows, warm_bins):
    """Protocol v2 rules for one router in one cell. rows: dicts with `bins`, `series`, ledger. Returns the rule outcomes."""
    dr, half, buf = [], [], []
    for r in rows:
        y = bin_rate(r["bins"])[warm_bins:]
        dr.append(drift(y) * 100)
        h = len(y) // 2
        half.append((np.mean(y[h:]) - np.mean(y[:h])) * 100)
        s = [v[1] for v in r["series"] if v[0] >= r["warm"]]
        k = len(s) // 3
        buf.append(np.mean(s[2 * k:]) - np.mean(s[k:2 * k]))
    def inside(v, m):
        v = np.asarray(v); c = ci(v)
        return bool(abs(v.mean()) + c <= m), float(v.mean()), float(c)
    a, b, c = inside(dr, 1.0), inside(half, 1.0), inside(buf, .02)
    close = all(abs(r["led_init"] + r["led_income"] - r["led_charged"] - r["led_spill"] - r["led_final"]) <= 1e-6 * max(r["led_init"] + r["led_income"], 1) for r in rows)
    return dict(drift_ok=a[0], drift=a[1], drift_ci=a[2], half_ok=b[0], half=b[1], half_ci=b[2], buf_ok=c[0], buf=c[1], buf_ci=c[2], closes=close,
                stable=a[0] and b[0] and c[0], steady=a[0] and b[0] and c[0] and close)
