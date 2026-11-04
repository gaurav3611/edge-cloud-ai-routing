#!/bin/sh
cd "$(dirname "$0")/.."
for s in estim val2 main abl stale scale robust place viol mix fallback topovar crypto owner eshort elong exlong; do nice -n 5 .venv/bin/python suites/run.py $s --workers 8 > logs/$s.log 2>&1 || exit 1; done
