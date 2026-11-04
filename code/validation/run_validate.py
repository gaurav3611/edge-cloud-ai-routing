"""Read-only wrapper: runs TRACE_revision/analysis/validate_suite.check and writes results here, not into TRACE_revision/processed."""
import json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "TRACE_revision"))
sys.path.insert(0, os.path.join(ROOT, "analysis"))
from validate_suite import check
OUT = os.path.dirname(os.path.abspath(__file__))
for s in sys.argv[1:]:
    r = check(s); print(s, r["rows"], "/", r["planned"], "routers", r["routers"], "commits", r["commits"], "FAIL" if r["failures"] else "ok", r["failures"], flush=True)
    json.dump(r, open(os.path.join(OUT, f"validate_{s}.json"), "w"), indent=1)
