# TRACE prototype: trust-constrained, category-aware routing for edge AI inference

Event-driven simulator plus experiment and analysis pipeline behind the paper draft in `paper/`.

## Setup (macOS, tested on Apple M3, Python 3.14)
The system Python has no scientific libraries, so use the bundled virtual environment:

```bash
cd ~/Desktop/sim
python3 -m venv .venv                       # already done once
.venv/bin/pip install numpy pandas matplotlib scipy
```

## Reproduce every number in the paper
```bash
.venv/bin/python experiments_v2.py   # ~1,400 runs, ~25 min on 8 cores; resumable (runs_v2.jsonl)
.venv/bin/python analyze.py          # figures/, tables/, STATS.md
cd paper && tectonic main.tex        # builds paper/main.pdf (brew install tectonic)
```

## Quick test of a single configuration
```python
import numpy as np
from ecsim import build_topology, Sim
topo = build_topology(30, np.random.default_rng(1))
print(Sim(topo, "tera", rho=0.8, T=30, seed=101).run())
```

## Policies (`Sim(..., policy=...)`)
| name | meaning |
|---|---|
| `local` | never offload |
| `rr` | decentralized round-robin (one pointer per server) |
| `rr_g` | round-robin with one pointer shared by all servers (reference; implicit global coordination) |
| `epara` | EPARA-style capacity-proportional offloading (no trust, no energy) |
| `epara_priv` | TF: EPARA-style + hard trust-domain filter |
| `tera` | **TRACE**: TF + best-fit clearance (`gamma`) |
| `energy` | energy-headroom weighting, no trust filter |
| `ours` | TF + energy weight `hd**beta` + retention (`theta`) |
| `ours_b` | TF + barrier energy weight |
| `ours_c` | TF + energy as a capacity dimension |

Options: `outage=True` (hard battery outage instead of soft throttling), `hsync` (state-sync period, s),
`beta`, `theta`, `gamma`.

## Files
- `ecsim.py` simulator; `ecsim_v1_backup.py` the Phase-1 version
- `experiments_v2.py` experiment suite A-F; `analyze.py` statistics and figures
- `results.csv`, `results_barrier.csv`, `runs_v2_superseded.jsonl`: earlier runs, kept for the record only
- `paper/main.tex` the complete paper in one self-contained file (TikZ/pgfplots figures, embedded references): upload it alone to Overleaf (pdfLaTeX)
- `paper/main_modular.tex` + `paper/gen/` the same paper with figures/tables as separate inputs; `make_tikz.py` regenerates `paper/gen/` from `results_v2.csv`
- `paper/main_with_images_backup.tex` earlier version using the matplotlib figures in `paper/figures/`

## Changes since Phase 1 (all affect reported numbers; the paper uses only v2 results)
1. Retention probe no longer debits the probed peer's spare capacity (side-effect bug), and a hand-over goes to the probed peer.
2. Round-robin baseline is decentralized (per-server pointer). The old shared pointer explained most of the
   "round-robin wins at saturation" anomaly; it is kept as `rr_g`.
3. Added: hard-outage energy model, energy-as-capacity variant, best-fit clearance (TRACE), sync-period
   parameter, per-category compliant SLO and the category-balanced metric `bcslo`, routing-time measurement.

All service times, power figures and topology distributions are **assumed** parameters, not measurements.
