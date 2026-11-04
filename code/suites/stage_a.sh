#!/bin/sh
cd "$(dirname "$0")/.."
for s in bridge eventcmp tune gamma qstar; do nice -n 5 .venv/bin/python suites/run.py $s --workers 8 > logs/$s.log 2>&1 || exit 1; done
